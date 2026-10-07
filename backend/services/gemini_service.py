import os
import json
import re
import asyncio
import logging
from google import genai
from google.genai import types, errors

from typing import Optional, List

from config import GOOGLE_API_KEY
from models.schemas import VisualAnalysisResult

logger = logging.getLogger(__name__)

PREFERRED_GEMINI_MODELS = [
    'gemini-pro-latest',
    'gemini-flash-latest',
]

# Single-tool edits (Hermes run_edit_session) — high call frequency (every Telegram
# reply / drawer chat message) but low reasoning depth, so skip the scarce Pro quota
# and go straight to Flash, falling back to Flash-Lite's much larger free-tier RPD.
EDIT_GEMINI_MODELS = [
    'gemini-flash-latest',
    'gemini-flash-lite-latest',
]

# Per-image vision analysis — called once per new Drive image within a single weekly
# session, the highest-volume call site in the app. Flash-Lite's free-tier RPD is an
# order of magnitude larger than Flash's, so it goes first here.
VISION_GEMINI_MODELS = [
    'gemini-flash-lite-latest',
    'gemini-flash-latest',
]

# Resumen de correcciones pasadas (memoria persistente de Hermes) — llamada barata e
# infrecuente (solo cuando hay correcciones nuevas desde el último resumen), Flash-Lite
# es más que suficiente para condensar un puñado de filas en 2-4 frases.
SUMMARY_GEMINI_MODELS = [
    'gemini-flash-lite-latest',
    'gemini-flash-latest',
]

# Skills dinámicas (code_execution / google_search) — confirmado por spike real
# que 'gemini-flash-latest' soporta ambas herramientas en este SDK; no todos los
# modelos lo hacen, de ahí una lista dedicada en vez de reutilizar las de arriba.
SKILL_GEMINI_MODELS = [
    'gemini-flash-latest',
]

# Rationale/confidence de agent_decisions y clasificación de reglas de marca
# (Hermes Mind) — llamadas cortas y best-effort en el propio loop de dispatch de
# tools, mismo perfil de coste/latencia que SUMMARY_GEMINI_MODELS.
DECISION_GEMINI_MODELS = [
    'gemini-flash-lite-latest',
    'gemini-flash-latest',
]

_client: Optional[genai.Client] = None


def get_gemini_client() -> genai.Client:
    global _client
    if _client is None:
        if not GOOGLE_API_KEY:
            raise Exception("GOOGLE_API_KEY no configurada. Necesaria para interactuar con Gemini.")
        _client = genai.Client(api_key=GOOGLE_API_KEY)
    return _client


def _is_quota_exhausted(e: Exception) -> bool:
    return isinstance(e, errors.ClientError) and e.code == 429

async def clean_and_parse_json(raw_text: str) -> dict:
    """
    Quita fences ```json y parsea. Lanza json.JSONDecodeError si el texto no es JSON válido.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    else:
        text = re.sub(r'```(?:json)?\n?', '', text).strip().rstrip('`').strip()
    return json.loads(text)

def _sync_generate_content(prompt: str, model_name: str) -> str:
    client = get_gemini_client()
    response = client.models.generate_content(model=model_name, contents=prompt)
    if not response or not response.text:
        raise Exception(f"El modelo {model_name} no pudo generar una respuesta válida.")
    return response.text.strip()

async def generate_gemini_content(
    prompt: str,
    model_names: Optional[List[str]] = None,
) -> str:
    """
    Configura genai, intenta cada modelo en orden ante cuota agotada (429), retorna response.text.strip().
    Re-lanza la última excepción si todos los modelos fallan.
    """
    models = model_names or PREFERRED_GEMINI_MODELS
    last_exception = None

    for model_name in models:
        try:
            logger.info(f"Intentando generar contenido con Gemini usando modelo: {model_name}")
            text = await asyncio.to_thread(_sync_generate_content, prompt, model_name)
            return text
        except Exception as e:
            last_exception = e
            if _is_quota_exhausted(e):
                logger.warning(f"Cuota excedida para el modelo {model_name}. Intentando con el siguiente... Detalles: {e}")
                continue
            logger.error(f"Error con el modelo {model_name}: {e}")
            raise e

    if last_exception:
        raise last_exception
    raise Exception("No se especificaron modelos para generar contenido.")

def _sync_analyze_image(image_bytes: bytes, mime_type: str, prompt: str) -> str:
    client = get_gemini_client()
    last_exception = None

    for model_name in VISION_GEMINI_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt]
            )
            if not response or not response.text:
                raise Exception("El modelo no pudo generar una respuesta válida para la imagen.")
            return response.text.strip()
        except Exception as e:
            if _is_quota_exhausted(e):
                last_exception = e
                logger.warning(f"Cuota excedida para el modelo {model_name} (vision). Intentando con el siguiente...")
                continue
            raise

    raise last_exception

async def analyze_image_vision(
    image_bytes: bytes,
    mime_type: str,
    strategy_context: Optional[str] = None,
) -> dict:
    """
    Envía la imagen como inline data (sin genai.upload_file), usa el prompt estructurado unificado y retorna el dict ya parseado y validado.
    """
    strategy_part = f"siguiendo estas instrucciones: {strategy_context}" if strategy_context else "sugerido para Instagram (1-2 frases con hashtags relevantes)"
    prompt = f"""Analiza detalladamente esta imagen. Retorna SOLO un objeto JSON con esta estructura exacta:
{{
  "objects": ["lista de objetos o personas principales"],
  "text_visible": "texto visible en la imagen o cadena vacía",
  "mood": "uno de: energetic, calm, professional, fun, inspiring, nostalgic",
  "theme": "tema principal en 2-3 palabras",
  "raw_description": "descripción detallada en 2-3 frases",
  "suggested_caption": "caption {strategy_part}",
  "aesthetic_score": 7,
  "composition_type": "uno de: primer_plano, detalle, paisaje, producto, accion, retrato",
  "content_type_fit": "uno de: feed_post, carousel_slide, story",
  "suggested_hook": "gancho de primera línea sugerido para abrir el caption"
}}"""

    text = await asyncio.to_thread(_sync_analyze_image, image_bytes, mime_type, prompt)
    parsed = await clean_and_parse_json(text)
    try:
        valid_comp = {"primer_plano", "detalle", "paisaje", "producto", "accion", "retrato"}
        valid_fit = {"feed_post", "carousel_slide", "story"}
        if parsed.get("composition_type") not in valid_comp:
            parsed["composition_type"] = "primer_plano"
        if parsed.get("content_type_fit") not in valid_fit:
            parsed["content_type_fit"] = "feed_post"
        if "aesthetic_score" not in parsed or not isinstance(parsed.get("aesthetic_score"), (int, float)):
            parsed["aesthetic_score"] = 5
        else:
            parsed["aesthetic_score"] = max(1, min(10, int(parsed["aesthetic_score"])))
        if "suggested_hook" not in parsed:
            parsed["suggested_hook"] = ""

        validated = VisualAnalysisResult(**parsed)
        return validated.model_dump()
    except Exception:
        return parsed


async def regenerate_slot_caption(
    theme: str,
    visual_context: str,
    language: str = 'es',
) -> str:
    """
    Construye el prompt de regeneración en el idioma indicado y retorna el caption limpio.
    """
    if language == 'en':
        prompt = (
            f"Generate a new creative Instagram caption about the theme: '{theme}'. "
            f"Visual context: {visual_context or 'inspiring image'}. "
            f"Tone: authentic and inspiring. End with an engagement question. "
            f"Include 3-5 relevant hashtags. Only the caption, no explanations."
        )
    else:
        prompt = (
            f"Genera un nuevo caption creativo para Instagram sobre el tema: '{theme}'. "
            f"Contexto visual: {visual_context or 'imagen inspiradora'}. "
            f"Tono: auténtico e inspirador. Termina con una pregunta de engagement. "
            f"Incluye 3-5 hashtags relevantes. Solo el caption, sin explicaciones."
        )

    return await generate_gemini_content(prompt)


async def summarize_corrections(rows: List[dict]) -> str:
    """
    Condensa las últimas correcciones del usuario (respuestas de run_edit_session que
    resolvieron, ver services/hermes/memory.py) en 2-4 frases de patrones a tener en
    cuenta al planificar futuras sesiones. rows viene ordenado de más antigua a más
    reciente; cada fila trae edit_type/user_message/resolution.
    """
    lines = []
    for row in rows:
        content = row.get("content") or {}
        edit_type = content.get("edit_type", "")
        user_message = content.get("user_message", "")
        resolution = content.get("resolution", "")
        lines.append(f"- [{edit_type}] Usuario dijo: \"{user_message}\" → {resolution}")
    corrections_text = "\n".join(lines)

    prompt = (
        "Estas son correcciones que un usuario ha hecho manualmente sobre propuestas de "
        "contenido de Instagram generadas automáticamente:\n\n"
        f"{corrections_text}\n\n"
        "Resume en 2-4 frases, en español, los patrones o preferencias que se puedan "
        "inferir de estas correcciones (ej. horarios que prefiere, tipos de contenido "
        "que rechaza, tono que corrige). Sé concreto y accionable — esto se usará como "
        "contexto para que un agente de IA planifique mejor la próxima vez. Responde "
        "solo con el resumen, sin introducciones."
    )

    return await generate_gemini_content(prompt, model_names=SUMMARY_GEMINI_MODELS)
