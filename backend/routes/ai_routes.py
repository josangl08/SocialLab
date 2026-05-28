import os
import logging
from fastapi import APIRouter, HTTPException, Depends
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
        
        # --- Creación del Prompt ---
        prompt = f"""
Eres 'SocialPro', un experto estratega de redes sociales y content manager con 10 años de experiencia. Tu objetivo es crear contenido para Instagram que sea auténtico, atractivo y que genere interacción.

**Instrucciones:**
1.  **Analiza el tema:** "{request.topic}"
2.  **Tono y Voz:** Utiliza un tono enérgico, positivo e inspirador.
3.  **Formato de Salida:** Genera un texto para la publicación (máximo 300 caracteres) y, en una nueva línea, una lista de 5 a 7 hashtags relevantes y específicos.
4.  **Llamada a la acción (CTA):** Incluye una pregunta o una frase que invite a los usuarios a comentar o visitar un enlace.

**Ejemplo de resultado:**
¡Dale un giro a tu estilo! 🌿✨ Descubre nuestra nueva colección hecha con materiales reciclados. Moda que cuida del planeta y de ti. ¿Cuál es tu pieza favorita? ¡Cuéntanos abajo!
#ModaSostenible #EcoFriendly #EstiloConsciente #Novedades #HechoAMano #SlowFashion

---

Ahora, genera el contenido para el tema proporcionado.
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
