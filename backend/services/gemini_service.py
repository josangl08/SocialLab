import os
import json
import re
import asyncio
import logging
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from typing import Optional, List

from config import GOOGLE_API_KEY

logger = logging.getLogger(__name__)

PREFERRED_GEMINI_MODELS = [
    'gemini-2.5-pro',
    'gemini-2.5-flash',
]

def _configure_genai():
    api_key = GOOGLE_API_KEY
    if not api_key:
        raise Exception("GOOGLE_API_KEY no configurada. Necesaria para interactuar con Gemini.")
    genai.configure(api_key=api_key)

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
    _configure_genai()
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    if not response or not response.text:
        raise Exception(f"El modelo {model_name} no pudo generar una respuesta válida.")
    return response.text.strip()

async def generate_gemini_content(
    prompt: str,
    model_names: Optional[List[str]] = None,
) -> str:
    """
    Configura genai, intenta cada modelo en orden ante ResourceExhausted, retorna response.text.strip().
    Re-lanza la última excepción si todos los modelos fallan.
    """
    models = model_names or PREFERRED_GEMINI_MODELS
    last_exception = None

    for model_name in models:
        try:
            logger.info(f"Intentando generar contenido con Gemini usando modelo: {model_name}")
            text = await asyncio.to_thread(_sync_generate_content, prompt, model_name)
            return text
        except ResourceExhausted as e:
            last_exception = e
            logger.warning(f"Cuota excedida para el modelo {model_name}. Intentando con el siguiente... Detalles: {e}")
            continue
        except Exception as e:
            last_exception = e
            logger.error(f"Error con el modelo {model_name}: {e}")
            raise e

    if last_exception:
        raise last_exception
    raise Exception("No se especificaron modelos para generar contenido.")

def _sync_analyze_image(image_path: str, mime_type: str, prompt: str) -> str:
    _configure_genai()
    uploaded = genai.upload_file(image_path, mime_type=mime_type)
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content([uploaded, prompt])
    if not response or not response.text:
        raise Exception("El modelo no pudo generar una respuesta válida para la imagen.")
    return response.text.strip()

async def analyze_image_vision(
    image_path: str,
    mime_type: str,
    strategy_context: Optional[str] = None,
) -> dict:
    """
    Sube el archivo con genai.upload_file, usa el prompt estructurado unificado y retorna el dict ya parseado.
    """
    strategy_part = f"siguiendo estas instrucciones: {strategy_context}" if strategy_context else "sugerido para Instagram (1-2 frases con hashtags relevantes)"
    prompt = f"""Analiza detalladamente esta imagen. Retorna SOLO un objeto JSON con esta estructura exacta:
{{
  "objects": ["lista de objetos o personas principales"],
  "text_visible": "texto visible en la imagen o cadena vacía",
  "mood": "uno de: energetic, calm, professional, fun, inspiring, nostalgic",
  "theme": "tema principal en 2-3 palabras",
  "raw_description": "descripción detallada en 2-3 frases",
  "suggested_caption": "caption {strategy_part}"
}}"""

    text = await asyncio.to_thread(_sync_analyze_image, image_path, mime_type, prompt)
    return await clean_and_parse_json(text)

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
