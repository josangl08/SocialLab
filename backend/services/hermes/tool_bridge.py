import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from google.genai import types

logger = logging.getLogger(__name__)

# Argumentos de las tools que referencian un archivo de Drive
_DRIVE_FILE_ARGS = ("drive_file_id", "file_id")
_OUT_OF_FOLDER_ERROR = "La imagen no está en la carpeta de Drive de la cuenta; usa solo archivos de drive_list_files."


def _tool_schema(tool: Any, attr: str) -> Dict[str, Any]:
    schema = getattr(tool, attr, None)
    return schema if isinstance(schema, dict) else {}


def _unwrap_mcp_result(result: Any, output_schema: Optional[Dict[str, Any]] = None) -> Any:
    """MCPServer.call_tool() returns a CallToolResult (MCP wire format), even for
    in-process calls. Left unwrapped, it leaks into Gemini's function response and
    blows up with "Object of type TextContent is not JSON serializable". Reconstruct
    the original Python value the tool actually returned.

    structured_content is preferred: it is the only form that distinguishes a
    one-element list from a dict, and None from []. MCP wraps non-object return
    types as {"result": ...}, detectable from the tool's output_schema.
    """
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        if set((output_schema or {}).get("properties", {})) == {"result"}:
            return structured.get("result")
        return structured

    if hasattr(result, "content"):
        result = result.content

    if not isinstance(result, list):
        return result

    texts = []
    for item in result:
        text = getattr(item, "text", None)
        if text is None:
            return result  # non-text content (image, etc.) — nothing sensible to unwrap
        texts.append(text)

    def _parse(text: str) -> Any:
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    if len(texts) == 1:
        return _parse(texts[0])
    return [_parse(t) for t in texts]


def _sanitize_schema(schema: Dict[str, Any], defs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convierte un JSON Schema generado por Pydantic/FastMCP al subconjunto que soporta
    google.genai.types.FunctionDeclaration. FastMCP genera 'title'/'default' en cada
    propiedad y representa Optional[...] como anyOf: [{type: X}, {type: null}] — ninguno de
    los dos lo acepta el Schema de genai (falla con "Unknown field for Schema: title").
    Nested Pydantic models (e.g. a tool param typed List[SomeModel]) come through as
    {"$ref": "#/$defs/SomeModel"} — defs resolves those against the root schema's $defs,
    threaded through every recursive call so nested objects aren't silently flattened to
    an untyped STRING. required is propagated at every level (not just the top-level tool
    params) so the model actually sees which nested fields are mandatory.
    """
    if not isinstance(schema, dict):
        return {"type": "STRING"}

    defs = defs or {}

    if "$ref" in schema:
        ref_name = schema["$ref"].rsplit("/", 1)[-1]
        return _sanitize_schema(defs.get(ref_name, {}), defs)

    if "anyOf" in schema:
        real_branch = next(
            (s for s in schema["anyOf"] if isinstance(s, dict) and s.get("type") != "null"),
            {}
        )
        return _sanitize_schema(real_branch, defs)

    sanitized: Dict[str, Any] = {"type": schema.get("type", "string").upper()}
    if "description" in schema:
        sanitized["description"] = schema["description"]
    if "enum" in schema:
        sanitized["enum"] = schema["enum"]
    if "items" in schema:
        sanitized["items"] = _sanitize_schema(schema["items"], defs)
    if "properties" in schema:
        sanitized["properties"] = {k: _sanitize_schema(v, defs) for k, v in schema["properties"].items()}
    if "required" in schema:
        sanitized["required"] = schema["required"]
    return sanitized


class ToolBridge:
    def __init__(self, mcp_servers: List[Any], allowed_tools: Optional[List[str]] = None):
        self.mcp_servers = mcp_servers
        self.allowed_tools = set(allowed_tools) if allowed_tools is not None else None
        self.tools_map = {}
        # Alcance de Drive por cuenta: (user_id, drive_folder_id) e IDs ya verificados en la carpeta
        self._drive_scope: Dict[int, Tuple[Optional[str], Optional[str]]] = {}
        self._allowed_file_ids: Dict[int, Set[str]] = {}

    def _get_drive_scope(self, account_id: int) -> Tuple[Optional[str], Optional[str]]:
        if account_id not in self._drive_scope:
            from database.supabase_client import get_supabase_admin_client
            res = get_supabase_admin_client().table('instagram_accounts')\
                .select('user_id, drive_folder_id').eq('id', account_id).execute()
            row = res.data[0] if res.data else {}
            user_id = str(row['user_id']) if row.get('user_id') else None
            self._drive_scope[account_id] = (user_id, row.get('drive_folder_id'))
        return self._drive_scope[account_id]

    async def _file_in_folder(self, account_id: int, file_id: str) -> bool:
        """El archivo debe colgar directamente de la carpeta de Drive de la cuenta."""
        allowed = self._allowed_file_ids.setdefault(account_id, set())
        if file_id in allowed:
            return True
        user_id, folder_id = self._get_drive_scope(account_id)
        if not user_id or not folder_id:
            return False

        def _parents() -> List[str]:
            from services.google_drive_connector import get_drive_connector
            meta = get_drive_connector(user_id).service.files()\
                .get(fileId=file_id, fields="parents, trashed").execute()
            return [] if meta.get("trashed") else meta.get("parents", [])

        try:
            in_folder = folder_id in await asyncio.to_thread(_parents)
        except Exception as e:
            logger.warning(f"No se pudo verificar la carpeta del archivo de Drive {file_id}: {e}")
            return False
        if in_folder:
            allowed.add(file_id)
        return in_folder

    def _referenced_file_ids(self, arguments: Dict[str, Any]) -> List[str]:
        ids = [arguments[k] for k in _DRIVE_FILE_ARGS if arguments.get(k)]
        for slot in arguments.get("slots") or []:
            if isinstance(slot, dict) and slot.get("image_id"):
                ids.append(slot["image_id"])
        return [str(i) for i in ids]

    async def discover_tools(self) -> List[types.FunctionDeclaration]:
        declarations = []
        self.tools_map = {}
        for server in self.mcp_servers:
            tools = await server.list_tools()
            for tool in tools:
                if self.allowed_tools is not None and tool.name not in self.allowed_tools:
                    continue
                self.tools_map[tool.name] = (server, tool)

                # input_schema is a dict representing the JSON Schema
                schema_dict = _tool_schema(tool, "input_schema")
                defs = schema_dict.get("$defs", {})

                properties = schema_dict.get("properties", {})
                filtered_properties = {}
                for k, v in properties.items():
                    if k not in ["account_id", "instagram_account_id"]:
                        filtered_properties[k] = _sanitize_schema(v, defs)

                required = schema_dict.get("required", [])
                filtered_required = [r for r in required if r not in ["account_id", "instagram_account_id"]]

                parameters = {
                    "type": "OBJECT",
                    "properties": filtered_properties,
                }
                if filtered_required:
                    parameters["required"] = filtered_required

                decl = types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=parameters
                )
                declarations.append(decl)

        return declarations

    async def dispatch(self, name: str, arguments: Dict[str, Any], account_id: int) -> Any:
        if name not in self.tools_map:
            raise ValueError(f"Tool {name} not found")
        
        server, tool = self.tools_map[name]
        actual_args = dict(arguments)
        
        # Check if the original input schema had account_id or instagram_account_id
        properties = _tool_schema(tool, "input_schema").get("properties", {})
        
        if "account_id" in properties:
            actual_args["account_id"] = account_id
        if "instagram_account_id" in properties:
            actual_args["instagram_account_id"] = account_id

        # Drive: solo la carpeta configurada de la cuenta, nunca el Drive completo
        if name.startswith("drive_"):
            user_id, folder_id = self._get_drive_scope(account_id)
            if not user_id or not folder_id:
                return {"error": "La cuenta no tiene carpeta de Drive configurada."}
            actual_args["user_id"] = user_id
            if "folder_id" in properties:
                actual_args["folder_id"] = folder_id

        for file_id in self._referenced_file_ids(actual_args):
            if not await self._file_in_folder(account_id, file_id):
                logger.warning(f"Hermes intentó usar el archivo de Drive {file_id} fuera de la carpeta de la cuenta {account_id}")
                return {"error": _OUT_OF_FOLDER_ERROR}

        result = await server.call_tool(name, actual_args)
        unwrapped = _unwrap_mcp_result(result, _tool_schema(tool, "output_schema"))

        if name == "drive_list_files" and isinstance(unwrapped, list):
            self._allowed_file_ids.setdefault(account_id, set()).update(
                str(f["id"]) for f in unwrapped if isinstance(f, dict) and f.get("id")
            )
        return unwrapped
