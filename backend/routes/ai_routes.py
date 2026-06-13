import os
import json
import tempfile
import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from models.schemas import AIPostRequest, AIPostResponse, User
from auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI Generation"])

# Lista de modelos de Gemini en orden de preferencia (del más potente al más ligero)
PREFERRED_GEMINI_MODELS = [
    'gemini-2.5-pro',
    'gemini-2.5-flash',
]

@router.post("/generate-post-content", response_model=AIPostResponse)
async def generate_ai_post_content(
    request: AIPostRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Genera contenido para una publicación utilizando la API de Google Gemini,
    intentando con modelos en orden de preferencia y con fallback en caso de cuota excedida.
    """
    try:
        # --- Configuración de la API de Google ---
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="La clave de API de Google no está configurada.")
        
        genai.configure(api_key=api_key)
        
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

        generated_text = None
        last_error_detail = "No se pudo generar contenido con IA. Inténtalo de nuevo más tarde."

        for model_name in PREFERRED_GEMINI_MODELS:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                
                if response.text:
                    generated_text = response.text
                    logger.info(f"Contenido generado exitosamente con el modelo: {model_name}")
                    break  # Salir del bucle si se genera el contenido
                else:
                    last_error_detail = f"El modelo {model_name} no pudo generar una respuesta válida."
                    logger.warning(f"Advertencia: {last_error_detail}")

            except ResourceExhausted as e:
                last_error_detail = f"Cuota excedida para el modelo {model_name}. Intentando con el siguiente... Detalles: {str(e)}"
                logger.error(f"Error de cuota: {last_error_detail}")
                continue  # Intentar con el siguiente modelo
            except Exception as e:
                last_error_detail = f"Error inesperado con el modelo {model_name}: {str(e)}"
                logger.error(f"Error general con el modelo: {last_error_detail}")
                # Si es un error diferente a cuota, no intentamos con otro modelo
                raise HTTPException(status_code=500, detail=f"Error al generar contenido con IA: {last_error_detail}")

        if generated_text:
            return {"generated_text": generated_text}
        else:
            raise HTTPException(status_code=500, detail=f"Error al generar contenido con IA: {last_error_detail}")

    except HTTPException:
        raise  # Re-lanzar HTTPException ya manejada
    except Exception as e:
        logger.error(f"Error general en el endpoint de IA: {e}")
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
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY no configurado")

    genai.configure(api_key=api_key)
    content = await file.read()

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f"_{file.filename}", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        uploaded = genai.upload_file(tmp_path, mime_type=file.content_type or "image/jpeg")

        prompt = """Analiza detalladamente esta imagen. Retorna SOLO un objeto JSON con esta estructura exacta:
{
  "objects": ["lista de objetos o personas principales"],
  "text_visible": "texto visible en la imagen o cadena vacía",
  "mood": "uno de: energetic, calm, professional, fun, inspiring, nostalgic",
  "theme": "tema principal en 2-3 palabras",
  "raw_description": "descripción detallada en 2-3 frases",
  "suggested_caption": "caption sugerido para Instagram (1-2 frases con hashtags relevantes)"
}"""

        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content([uploaded, prompt])

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        return json.loads(text)

    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned non-JSON response: {e}")
        raise HTTPException(status_code=500, detail="La IA devolvió una respuesta inválida")
    except Exception as e:
        logger.error(f"Error en analyze-image: {e}")
        raise HTTPException(status_code=500, detail=f"Error al analizar imagen: {str(e)}")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
