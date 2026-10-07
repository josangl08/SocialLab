from typing import Optional, Dict, Any
import base64
from mcp.server.mcpserver import MCPServer
from services.gemini_service import analyze_image_vision

mcp = MCPServer("Vision Server")

@mcp.tool()
async def vision_analyze_image(
    image_bytes: Any,  # Can be bytes or base64 encoded string
    mime_type: str,
    strategy_context: Optional[str] = None
) -> Dict[str, Any]:
    """Analyze an image using the vision model and return structured data (objects, text_visible, mood, theme, raw_description, suggested_caption)."""
    if isinstance(image_bytes, str):
        try:
            actual_bytes = base64.b64decode(image_bytes)
        except Exception:
            actual_bytes = image_bytes.encode('utf-8')
    else:
        actual_bytes = image_bytes
        
    return await analyze_image_vision(actual_bytes, mime_type, strategy_context)
