import json
import tempfile
import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from services.gemini_service import generate_gemini_content, analyze_image_vision

from models.schemas import AIPostRequest, AIPostResponse, User
from auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI Generation"])



@router.post("/generate-post-content", response_model=AIPostResponse)
async def generate_ai_post_content(
    request: AIPostRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Genera contenido para una publicación utilizando la API de Google Gemini,
    intentando con modelos en orden de preferencia y con fallback en caso de cuota excedida.
    """
    # --- Prompt estratégico según tipo de cuenta ---
    acct_type = request.account_type or "personal"
    language = request.default_language or "es"
    tone = request.default_tone or ("professional" if acct_type == "professional" else "energetic")
    style_note = f"Guía de estilo: {request.style_guide}" if request.style_guide else ""
    audience_note = f"Audiencia: {request.target_audience}" if request.target_audience else ""

    if acct_type == "professional":
        tone_block = (
            f"Tono {tone}, voz de marca semiformal, emojis mínimos (0-1). "
            f"Empieza directamente con el beneficio principal o propuesta de valor. "
            f"CTA de conversión al final ('Contáctanos', 'Reserva ahora', 'Más info en bio'). "
            f"Incluye 1-2 keywords SEO relevantes en el texto (Instagram indexado por Google desde 2025)."
        )
    else:
        tone_block = (
            f"Tono {tone}, primera persona, emojis moderados (1-3). "
            f"Cuenta brevemente una historia auténtica o comparte un momento real. "
            f"Termina con una pregunta que invite a comentar ('¿Qué opinas?', '¡Cuéntame!', '¿Te ha pasado?')."
        )

    prompt = f"""Eres 'SocialPro', experto en estrategia de Instagram con 10 años de experiencia.

**Tema:** "{request.topic}"
**Tipo de cuenta:** {acct_type}
**Idioma:** {"Español" if language == "es" else "English"}
**Tono y voz:** {tone_block}
{f"**{style_note}**" if style_note else ""}
{f"**{audience_note}**" if audience_note else ""}

**Formato de salida:**
- Texto principal: máximo 300 caracteres
- Nueva línea con 3-5 hashtags muy relevantes (máx. 5 — límite de Instagram desde dic. 2025)

Genera el contenido ahora.
"""

    try:
        generated_text = await generate_gemini_content(prompt)
        return {"generated_text": generated_text}
    except Exception as e:
        logger.error(f"Error al generar contenido con IA: {e}")
        raise HTTPException(status_code=500, detail=f"Error al generar contenido con IA: {str(e)}")


@router.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Analyzes an image using Gemini Vision and returns structured JSON with
    objects, mood, theme, raw description, and a suggested caption.
    """
    content = await file.read()
    try:
        result = await analyze_image_vision(
            image_bytes=content,
            mime_type=file.content_type or "image/jpeg"
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned non-JSON response: {e}")
        raise HTTPException(status_code=500, detail="La IA devolvió una respuesta inválida")
    except Exception as e:
        logger.error(f"Error en analyze-image: {e}")
        raise HTTPException(status_code=500, detail=f"Error al analizar imagen: {str(e)}")

