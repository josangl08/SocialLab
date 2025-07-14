import os
from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form
from starlette.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
from jose import JWTError, jwt
from datetime import datetime, timedelta
import uuid # Importar para generar UUIDs
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted # Importar para manejar errores de cuota

# Cargar variables de entorno
load_dotenv()

# --- Configuración de Supabase ---
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise Exception("Error: Las variables de entorno SUPABASE_URL y SUPABASE_KEY son necesarias.")

supabase: Client = create_client(url, key)

# --- Configuración de Seguridad (JWT) ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Modelos de Datos (Pydantic) ---
class UserRegister(BaseModel):
    email: str
    password: str

class User(BaseModel):
    id: str
    email: str
    created_at: datetime | None = None

class Token(BaseModel):
    access_token: str
    token_type: str

# --- Modelos de Datos para Publicaciones ---
class PostBase(BaseModel):
    content: str
    post_type: str # "post", "reel", "story"
    status: str = "draft" # "draft", "scheduled", "published"
    scheduled_at: datetime | None = None

class PostCreate(PostBase):
    pass

class Post(PostBase):
    id: int
    user_id: str
    media_url: str | None = None # Añadir de nuevo para el modelo de respuesta
    created_at: datetime

# --- Inicialización de la Aplicación FastAPI ---
app = FastAPI(
    title="SocialLab API",
    description="La API para el planificador de publicaciones con IA.",
    version="0.1.0"
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Permite el origen de tu frontend
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Permite todos los encabezados
)

# --- Dependencia para obtener el usuario actual ---
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_response = supabase.auth.get_user(token)
        user_data = user_response.user

        if not user_data:
            raise credentials_exception
        
        return User(id=user_data.id, email=user_data.email, created_at=user_data.created_at)
    except Exception as e:
        print(f"Error al obtener usuario: {e}")
        raise credentials_exception

# --- Endpoints de la API ---

@app.get("/")
def read_root():
    """Endpoint raíz para verificar que la API está funcionando."""
    return {"status": "ok", "message": "Bienvenido a la API de SocialLab"}

@app.post("/register", response_model=User)
async def register_user(user_data: UserRegister):
    """
    Registra un nuevo usuario utilizando la autenticación de Supabase.
    """
    try:
        response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password
        })
        
        if response.user:
            return User(id=response.user.id, email=response.user.email, created_at=response.user.created_at)
        else:
            raise HTTPException(status_code=500, detail="No se pudo registrar el usuario.")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al registrar el usuario: {e}")

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Inicia sesión y devuelve un token de acceso JWT utilizando la autenticación de Supabase.
    """
    try:
        response = supabase.auth.sign_in_with_password({
            "email": form_data.username,
            "password": form_data.password
        })

        if response.session and response.session.access_token:
            return {"access_token": response.session.access_token, "token_type": "bearer"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email o contraseña incorrectos"
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al iniciar sesión: {e}")

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Obtiene la información del usuario autenticado actualmente.
    """
    return current_user

@app.post("/posts", response_model=Post)
async def create_post(
    content: str = Form(...),
    post_type: str = Form(...),
    status: str = Form(...),
    scheduled_at: datetime | None = Form(None),
    media_file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user)
):
    """
    Crea una nueva publicación para el usuario autenticado, con opción de subir un archivo multimedia.
    """
    media_url = None
    if media_file:
        try:
            file_extension = media_file.filename.split(".")[-1]
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            file_content = await media_file.read()

            # La función upload lanza una excepción si falla, no devuelve un status_code
            supabase.storage.from_("post-media").upload(unique_filename, file_content, {"content-type": media_file.content_type})
            
            media_url = supabase.storage.from_("post-media").get_public_url(unique_filename)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al procesar archivo multimedia: {str(e)}")

    try:
        response = supabase.table('posts').insert({
            'user_id': current_user.id,
            'content': content,
            'media_url': media_url,
            'post_type': post_type,
            'status': status,
            'scheduled_at': scheduled_at.isoformat() if scheduled_at else None
        }).execute()

        if response.data:
            new_post = response.data[0]
            return new_post
        else:
            raise HTTPException(status_code=500, detail="No se pudo crear la publicación.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear la publicación: {str(e)}")

@app.get("/posts", response_model=list[Post])
async def get_posts(current_user: User = Depends(get_current_user)):
    """
    Obtiene todas las publicaciones del usuario autenticado.
    """
    try:
        response = supabase.table('posts').select('*').eq('user_id', current_user.id).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener las publicaciones: {str(e)}")

@app.put("/posts/{post_id}", response_model=Post)
async def update_post(
    post_id: int,
    content: str = Form(...),
    post_type: str = Form(...),
    status: str = Form(...),
    scheduled_at: datetime | None = Form(None),
    media_file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user)
):
    """
    Actualiza una publicación existente del usuario autenticado, con opción de subir un archivo multimedia.
    """
    response = supabase.table('posts').select('id', 'media_url').eq('id', post_id).eq('user_id', current_user.id).execute()
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publicación no encontrada")

    existing_media_url = response.data[0].get('media_url')
    media_url = existing_media_url # Mantener la URL existente por defecto

    if media_file:
        try:
            # Eliminar el archivo antiguo si existe
            if existing_media_url:
                old_filename = existing_media_url.split('/')[-1]
                supabase.storage.from_("post-media").remove([old_filename])

            file_extension = media_file.filename.split(".")[-1]
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            file_content = await media_file.read()

            # La función upload lanza una excepción si falla, no devuelve un status_code
            supabase.storage.from_("post-media").upload(unique_filename, file_content, {"content-type": media_file.content_type})
            
            media_url = supabase.storage.from_("post-media").get_public_url(unique_filename)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al procesar archivo multimedia: {str(e)}")
    
    # Si media_file es None y existing_media_url es None, media_url permanece None.
    # Si media_file es None y el usuario quiere eliminar el medio existente, necesitaríamos un campo adicional.
    # Por ahora, si no se proporciona un nuevo archivo, se mantiene el existente.

    try:
        update_data = {
            'content': content,
            'media_url': media_url,
            'post_type': post_type,
            'status': status,
            'scheduled_at': scheduled_at.isoformat() if scheduled_at else None
        }
        
        response = supabase.table('posts').update(update_data).eq('id', post_id).execute()
        if response.data:
            return response.data[0]
        else:
            raise HTTPException(status_code=500, detail="No se pudo actualizar la publicación.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar la publicación: {str(e)}")

@app.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: int, current_user: User = Depends(get_current_user)):
    """
    Elimina una publicación del usuario autenticado.
    """
    # Primero, verificar que la publicación existe y pertenece al usuario
    response = supabase.table('posts').select('id', 'media_url').eq('id', post_id).eq('user_id', current_user.id).execute()
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publicación no encontrada")

    existing_media_url = response.data[0].get('media_url')

    try:
        # Eliminar el archivo de Supabase Storage si existe
        if existing_media_url:
            filename_to_delete = existing_media_url.split('/')[-1]
            supabase.storage.from_("post-media").remove([filename_to_delete])

        supabase.table('posts').delete().eq('id', post_id).execute()
        return
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar la publicación: {str(e)}")

# --- Modelos de Datos para IA ---
class AIPostRequest(BaseModel):
    topic: str
    # En el futuro, podríamos añadir más campos como 'tone', 'style', etc.

class AIPostResponse(BaseModel):
    generated_text: str

    # --- Endpoint de IA con Google Gemini (con fallback de modelos) ---
@app.post("/ai/generate-post-content", response_model=AIPostResponse)
async def generate_ai_post_content(
    request: AIPostRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Genera contenido para una publicación utilizando la API de Google Gemini,
    intentando con modelos en orden de preferencia y con fallback en caso de cuota excedida.
    """
    # Lista de modelos de Gemini en orden de preferencia (del más potente al más ligero)
    PREFERRED_GEMINI_MODELS = [
        'gemini-1.5-pro-latest',
        'gemini-1.5-flash-latest',
        # Puedes añadir más modelos aquí si es necesario
    ]

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
1.  **Analiza el siguiente tema:** "{request.topic}"
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
                    print(f"Contenido generado exitosamente con el modelo: {model_name}")
                    break # Salir del bucle si se genera el contenido
                else:
                    last_error_detail = f"El modelo {model_name} no pudo generar una respuesta válida."
                    print(f"Advertencia: {last_error_detail}")

            except ResourceExhausted as e:
                last_error_detail = f"Cuota excedida para el modelo {model_name}. Intentando con el siguiente... Detalles: {str(e)}"
                print(f"Error de cuota: {last_error_detail}")
                continue # Intentar con el siguiente modelo
            except Exception as e:
                last_error_detail = f"Error inesperado con el modelo {model_name}: {str(e)}"
                print(f"Error general con el modelo: {last_error_detail}")
                # Si es un error diferente a cuota, no intentamos con otro modelo
                raise HTTPException(status_code=500, detail=f"Error al generar contenido con IA: {last_error_detail}")

        if generated_text:
            return {"generated_text": generated_text}
        else:
            raise HTTPException(status_code=500, detail=f"Error al generar contenido con IA: {last_error_detail}")

    except HTTPException:
        raise # Re-lanzar HTTPException ya manejada
    except Exception as e:
        print(f"Error general en el endpoint de IA: {e}")
        raise HTTPException(status_code=500, detail=f"Error al generar contenido con IA: {str(e)}")
