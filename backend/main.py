import os
import sys
import logging
from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form
from starlette.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Literal
import uuid
import requests
from starlette.responses import RedirectResponse
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Asegurar que los logs se muestren inmediatamente
sys.stdout.flush()

# --- Configuración de Supabase ---
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

# --- Configuración de Instagram OAuth ---
INSTAGRAM_APP_ID = os.environ.get("INSTAGRAM_APP_ID")
INSTAGRAM_APP_SECRET = os.environ.get("INSTAGRAM_APP_SECRET")
INSTAGRAM_REDIRECT_URI = os.environ.get("REDIRECT_URI")

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
    status: Literal["draft", "scheduled", "published"] = "draft" # Restringir a draft, scheduled o published
    scheduled_at: datetime | None = None

class PostCreate(PostBase):
    pass

class Post(PostBase):
    id: int
    user_id: str
    media_url: str | None = None
    created_at: datetime
    publication_date: datetime | None = None

# --- Inicialización de la Aplicación FastAPI ---
app = FastAPI(
    title="SocialLab API",
    description="La API para el planificador de publicaciones con IA.",
    version="0.1.0"
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],  # Permite el origen de tu frontend
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

# Nueva dependencia para obtener el usuario desde un token en el query parameter
async def get_current_user_from_query_token(token: str):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales desde el query token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_response = supabase.auth.get_user(token)
        user_data = user_response.user

        if not user_data:
            raise credentials_exception
        
        return User(id=user_data.id, email=user_data.email, created_at=user_data.created_at)
    except Exception as e:
        print(f"Error al obtener usuario desde query token: {e}")
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
    Obtiene todas las publicaciones del usuario autenticado ordenadas por fecha.
    """
    try:
        response = (
            supabase.table('posts')
            .select('*')
            .eq('user_id', current_user.id)
            .order('publication_date', desc=True)
            .order('created_at', desc=True)
            .execute()
        )
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar la publicación: {str(e)}")

# --- Endpoints de Instagram OAuth ---
@app.get("/instagram/login")
async def instagram_login(token: str, current_user: User = Depends(get_current_user_from_query_token)):
    if not INSTAGRAM_APP_ID:
        raise HTTPException(status_code=500, detail="INSTAGRAM_APP_ID no configurado.")
    
    # Codificar el user_id en el parámetro 'state'
    state_param = current_user.id
    
    # Construir la URL de autorización de Facebook Graph API
    auth_url = (
        f"https://graph.facebook.com/oauth/authorize?client_id={INSTAGRAM_APP_ID}"
        f"&redirect_uri={INSTAGRAM_REDIRECT_URI}"
        "&scope=instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,instagram_manage_insights"
        "&response_type=code"
        f"&state={state_param}"
    )
    return RedirectResponse(auth_url)

@app.get("/callback/instagram")
async def instagram_callback(
    code: str | None = None,
    error: str | None = None,
    state: str | None = None # Para recibir el user_id
):
    if error:
        raise HTTPException(status_code=400, detail=f"Error de Instagram OAuth: {error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="No se recibió el código de autorización de Instagram.")

    if not state:
        raise HTTPException(status_code=400, detail="No se recibió el ID de usuario en el parámetro state.")

    # El user_id de SocialLab se pasa en el parámetro state
    sociallab_user_id = state

    if not INSTAGRAM_APP_ID or not INSTAGRAM_APP_SECRET or not INSTAGRAM_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Credenciales de Instagram no configuradas.")

    # Intercambiar el código de autorización por un token de acceso de corta duración
    token_exchange_url = "https://graph.facebook.com/oauth/access_token"
    data = {
        'client_id': INSTAGRAM_APP_ID,
        'client_secret': INSTAGRAM_APP_SECRET,
        'grant_type': 'authorization_code',
        'redirect_uri': INSTAGRAM_REDIRECT_URI,
        'code': code,
    }
    
    try:
        response = requests.post(token_exchange_url, data=data)
        response.raise_for_status() # Lanza una excepción para códigos de estado HTTP erróneos
        token_data = response.json()
        
        short_lived_access_token = token_data.get('access_token')

        if not short_lived_access_token:
            raise HTTPException(status_code=500, detail="No se pudo obtener el token de acceso de corta duración de Instagram.")

        # Intercambiar el token de corta duración por uno de larga duración
        long_lived_token_exchange_url = "https://graph.facebook.com/oauth/access_token"
        long_lived_data = {
            'grant_type': 'fb_exchange_token',
            'client_id': INSTAGRAM_APP_ID,
            'client_secret': INSTAGRAM_APP_SECRET,
            'fb_exchange_token': short_lived_access_token
        }

        long_lived_response = requests.get(long_lived_token_exchange_url, params=long_lived_data)
        long_lived_response.raise_for_status()
        long_lived_token_data = long_lived_response.json()

        long_lived_access_token = long_lived_token_data.get('access_token')
        long_lived_expires_in = long_lived_token_data.get('expires_in') # Obtener expires_in del token de larga duración

        if not long_lived_access_token:
            raise HTTPException(status_code=500, detail="No se pudo obtener el token de acceso de larga duración de Instagram.")

        # Si expires_in no está presente, usar un valor por defecto (60 días en segundos)
        if long_lived_expires_in is None:
            long_lived_expires_in = 60 * 24 * 60 * 60  # 60 días en segundos
            print("Advertencia: 'expires_in' no recibido para el token de larga duración. Usando 60 días por defecto.")

        # Calcular la fecha de expiración
        expires_at = datetime.utcnow() + timedelta(seconds=long_lived_expires_in)

        # Obtener el ID de la página de Facebook asociada al token
        pages_url = f"https://graph.facebook.com/v19.0/me/accounts?access_token={long_lived_access_token}"
        pages_response = requests.get(pages_url)
        pages_response.raise_for_status()
        pages_data = pages_response.json()

        facebook_page_id = None
        if pages_data and pages_data.get('data'):
            # Asumimos que la primera página es la que nos interesa o que el usuario solo tiene una
            facebook_page_id = pages_data['data'][0].get('id')

        if not facebook_page_id:
            raise HTTPException(status_code=500, detail="No se pudo obtener el ID de la página de Facebook.")

        # Obtener el ID de la cuenta de Instagram Business
        instagram_business_account_url = f"https://graph.facebook.com/v19.0/{facebook_page_id}?fields=instagram_business_account&access_token={long_lived_access_token}"
        instagram_account_response = requests.get(instagram_business_account_url)
        instagram_account_response.raise_for_status()
        instagram_account_data = instagram_account_response.json()

        instagram_business_account_id = None
        if instagram_account_data.get('instagram_business_account'):
            instagram_business_account_id = instagram_account_data['instagram_business_account'].get('id')

        if not instagram_business_account_id:
            raise HTTPException(status_code=500, detail="No se pudo obtener el ID de la cuenta de Instagram Business.")

        # Guardar en Supabase usando el sociallab_user_id
        try:
            supabase.table('instagram_accounts').upsert({
                'user_id': sociallab_user_id,
                'instagram_business_account_id': instagram_business_account_id,
                'long_lived_access_token': long_lived_access_token,
                'expires_at': expires_at.isoformat() + 'Z' # Supabase espera formato ISO con Z para UTC
            }).execute()
            print("Instagram account details saved to Supabase.")
        except Exception as e:
            print(f"Error saving Instagram account details to Supabase: {e}")
            raise HTTPException(status_code=500, detail=f"Error al guardar los detalles de la cuenta de Instagram: {str(e)}")

        # Redirigir al frontend, quizás a una página de éxito o al dashboard
        return RedirectResponse(url="http://localhost:5173/dashboard?instagram_connected=true")

    except requests.exceptions.RequestException as e:
        print(f"Error durante el intercambio de tokens o la obtención de IDs: {e.response.text if e.response else e}")
        raise HTTPException(status_code=500, detail=f"Error durante el proceso de autenticación de Instagram: {e}")

@app.get("/instagram/sync")
async def instagram_sync(current_user: User = Depends(get_current_user)):
    """
    Sincroniza publicaciones desde Instagram a SocialLab.
    Obtiene las últimas publicaciones de la cuenta Instagram Business
    y las almacena en la base de datos.
    """
    logger.info(f"[SYNC] Iniciando sincronización para usuario: {current_user.id}")

    try:
        # 1. Obtener el token de acceso del usuario
        logger.info("[SYNC] Obteniendo token de Instagram desde Supabase...")
        response = supabase.table('instagram_accounts').select('long_lived_access_token, instagram_business_account_id').eq('user_id', current_user.id).single().execute()

        if not response.data or not response.data.get('long_lived_access_token'):
            logger.error(f"[SYNC ERROR] No se encontraron credenciales para usuario: {current_user.id}")
            raise HTTPException(
                status_code=404,
                detail="No se encontraron credenciales de Instagram para este usuario."
            )

        access_token = response.data['long_lived_access_token']
        stored_ig_id = response.data.get('instagram_business_account_id')
        logger.info(f"[SYNC] Token encontrado. IG Business ID: {stored_ig_id}")

        # 2. Obtener el ID de la cuenta de Instagram Business
        logger.info("[SYNC] Obteniendo páginas de Facebook...")
        user_accounts_url = f"https://graph.facebook.com/v19.0/me/accounts?access_token={access_token}"
        user_accounts_response = requests.get(user_accounts_url)
        user_accounts_response.raise_for_status()
        user_accounts_data = user_accounts_response.json()

        logger.info(f"[SYNC] Respuesta de páginas FB: {user_accounts_data}")

        if not user_accounts_data.get('data'):
            logger.error("[SYNC ERROR] No se encontraron páginas de Facebook")
            raise HTTPException(
                status_code=500,
                detail="No se encontraron páginas de Facebook asociadas a esta cuenta."
            )

        facebook_page_id = user_accounts_data['data'][0]['id']
        facebook_page_name = user_accounts_data['data'][0].get('name', 'Sin nombre')
        logger.info(f"[SYNC] Página FB encontrada: {facebook_page_name} (ID: {facebook_page_id})")

        # 3. Obtener cuenta de Instagram Business asociada
        logger.info("[SYNC] Obteniendo cuenta Instagram Business...")
        ig_account_url = f"https://graph.facebook.com/v19.0/{facebook_page_id}?fields=instagram_business_account&access_token={access_token}"
        ig_account_response = requests.get(ig_account_url)
        ig_account_response.raise_for_status()
        ig_account_data = ig_account_response.json()

        logger.info(f"[SYNC] Respuesta de IG Business: {ig_account_data}")

        if not ig_account_data.get('instagram_business_account'):
            logger.error("[SYNC ERROR] No se encontró instagram_business_account en respuesta")
            raise HTTPException(
                status_code=500,
                detail="No se encontró una cuenta de Instagram Business asociada. Verifica que tu cuenta sea tipo 'Business' y esté vinculada a la página de Facebook."
            )

        instagram_user_id = ig_account_data['instagram_business_account']['id']
        logger.info(f"[SYNC] Instagram Business Account ID: {instagram_user_id}")

        # 4. Obtener las publicaciones de la cuenta de Instagram
        logger.info("[SYNC] Obteniendo publicaciones de Instagram...")
        media_url = f"https://graph.facebook.com/v19.0/{instagram_user_id}/media?fields=id,caption,media_type,media_url,timestamp,permalink,media_product_type&access_token={access_token}"
        media_response = requests.get(media_url)
        media_response.raise_for_status()
        media_data = media_response.json().get('data', [])

        logger.info(f"[SYNC] Publicaciones obtenidas: {len(media_data)}")

        if not media_data:
            logger.warning("[SYNC WARNING] No se encontraron publicaciones en Instagram")
            return {
                "status": "ok",
                "message": "No se encontraron publicaciones en Instagram. Verifica que tu cuenta tenga posts publicados."
            }

        # 5. Preparar los datos para el upsert en Supabase
        posts_to_upsert = []
        for item in media_data:
            media_product_type = item.get('media_product_type', 'FEED')
            media_type = item.get('media_type', 'IMAGE').lower()

            # Determinar el tipo de post basado en media_product_type
            if media_product_type == 'REELS':
                post_type = 'reel'
            elif media_product_type == 'STORY':
                post_type = 'story'
            else:
                # FEED o AD, usar media_type
                post_type = media_type

            post_data = {
                'user_id': current_user.id,
                'instagram_post_id': item['id'],
                'content': item.get('caption', ''),
                'media_url': item.get('media_url'),
                'post_type': post_type,
                'media_product_type': media_product_type,
                'status': 'published',
                'publication_date': item.get('timestamp')
            }
            posts_to_upsert.append(post_data)
            logger.info(f"[SYNC] Post preparado: {item['id'][:15]}... - {media_product_type} ({media_type})")

        # 6. Realizar el upsert en la base de datos
        logger.info(f"[SYNC] Insertando {len(posts_to_upsert)} publicaciones en Supabase...")
        upsert_response = supabase.table('posts').upsert(
            posts_to_upsert,
            on_conflict='instagram_post_id'
        ).execute()

        logger.info(f"[SYNC SUCCESS] Sincronización completada. {len(posts_to_upsert)} publicaciones procesadas.")

        return {
            "status": "ok",
            "message": f"Sincronizadas {len(posts_to_upsert)} publicaciones.",
            "posts_synced": len(posts_to_upsert)
        }

    except requests.exceptions.RequestException as e:
        error_detail = str(e)
        if e.response:
            error_detail = f"Status {e.response.status_code}: {e.response.text}"
            logger.error(f"[SYNC ERROR] Error de API: {error_detail}")

        # Si el token ha expirado, la API de Facebook devolverá un error
        if e.response and e.response.status_code in [400, 401]:
            logger.error("[SYNC ERROR] Token expirado o inválido")
            raise HTTPException(
                status_code=401,
                detail="El token de acceso de Instagram ha expirado o es inválido. Por favor, vuelve a conectar tu cuenta."
            )

        logger.error(f"[SYNC ERROR] Error de comunicación con Instagram API: {error_detail}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al comunicarse con la API de Instagram: {error_detail}"
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[SYNC ERROR] Error inesperado: {str(e)}")
        import traceback
        logger.error(f"[SYNC ERROR] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Error durante la sincronización: {str(e)}"
        )


@app.get("/instagram/status")
async def instagram_status(current_user: User = Depends(get_current_user)):
    """
    Verifica si el usuario tiene Instagram conectado y devuelve el estado.
    Esto evita depender solo de localStorage en el frontend.
    """
    try:
        response = supabase.table('instagram_accounts').select(
            'instagram_business_account_id, expires_at, created_at'
        ).eq('user_id', current_user.id).single().execute()

        if not response.data:
            return {
                "connected": False,
                "message": "No se encontraron credenciales de Instagram"
            }

        expires_at_str = response.data.get('expires_at')
        created_at_str = response.data.get('created_at')

        # Verificar si el token ha expirado
        if expires_at_str:
            from datetime import datetime
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            now = datetime.now(expires_at.tzinfo)

            if expires_at < now:
                return {
                    "connected": False,
                    "expired": True,
                    "expires_at": expires_at_str,
                    "message": "El token de Instagram ha expirado. Vuelve a conectar tu cuenta."
                }

        return {
            "connected": True,
            "instagram_business_account_id": response.data.get('instagram_business_account_id'),
            "expires_at": expires_at_str,
            "created_at": created_at_str
        }

    except Exception as e:
        # Si la tabla no existe o hay error, asumimos no conectado
        return {
            "connected": False,
            "error": str(e)
        }


# --- Modelos de Datos para IA ---
class AIPostRequest(BaseModel):
    topic: str
    role: str = "content_manager" # Nuevo campo para el rol de la IA, con un valor por defecto

class AIPostResponse(BaseModel):
    generated_text: str

# --- Definición de roles para la IA ---
AI_ROLES = {
    "content_manager": {
        "name": "Content Manager Profesional",
        "prompt_template": """
Eres 'SocialPro', un experto estratega de redes sociales y content manager con 10 años de experiencia en marcas de moda y estilo de vida. Tu objetivo es crear contenido para Instagram que sea auténtico, que genere engagement y que impulse las ventas.

**Instrucciones:**
1.  **Analiza el tema:** {topic}
2.  **Tono y Voz:** El tono debe ser inspirador, enérgico y juvenil.
3.  **Formato de Salida:** Genera un texto para un post de Instagram (máximo 300 caracteres) y, en una nueva línea, una lista de 5-7 hashtags relevantes y específicos.
4.  **Llamada a la acción (CTA):** Incluye una pregunta o una frase que invite a los usuarios a comentar o visitar un enlace.

**Ejemplo de resultado:**
¡Dale un giro a tu estilo! 🌿✨ Descubre nuestra nueva colección hecha con materiales reciclados. Moda que cuida del planeta y de ti. ¿Cuál es tu pieza favorita? ¡Cuéntanos abajo!
#ModaSostenible #EcoFriendly #EstiloConsciente #Novedades #HechoAMano #SlowFashion

---

Ahora, genera el contenido para el tema proporcionado.
"""
    },
    "marketing_expert": {
        "name": "Experto en Marketing Digital",
        "prompt_template": """
Eres un experto en marketing digital especializado en campañas de redes sociales. Tu objetivo es crear contenido que maximice el alcance, la conversión y el ROI.

**Instrucciones:**
1.  **Analiza el tema:** {topic}
2.  **Tono y Voz:** El tono debe ser persuasivo, profesional y orientado a resultados.
3.  **Formato de Salida:** Genera un texto para un post de Instagram (máximo 300 caracteres) y, en una nueva línea, una lista de 5-7 hashtags orientados a la conversión.
4.  **Llamada a la acción (CTA):** Incluye una llamada a la acción clara y directa que impulse una acción específica (ej. compra, registro).

**Ejemplo de resultado:**
¡No te quedes atrás! 📈 Descubre cómo nuestra solución puede transformar tu negocio. Oferta por tiempo limitado. ¡Regístrate hoy y obtén un 20% de descuento! #MarketingDigital #NegociosOnline #EstrategiaDigital #OfertaEspecial #TransformaTuNegocio

---

Ahora, genera el contenido para el tema proporcionado.
"""
    },
    "casual_friend": {
        "name": "Amigo Casual y Cercano",
        "prompt_template": """
Eres un amigo cercano y divertido que comparte noticias emocionantes en Instagram. Tu objetivo es sonar auténtico, amigable y generar una conversación relajada.

**Instrucciones:**
1.  **Analiza el tema:** {topic}
2.  **Tono y Voz:** El tono debe ser informal, amigable y conversacional.
3.  **Formato de Salida:** Genera un texto para un post de Instagram (máximo 300 caracteres) y, en una nueva línea, 3-5 hashtags populares y divertidos.
4.  **Llamada a la acción (CTA):** Haz una pregunta abierta o una invitación a compartir experiencias.

**Ejemplo de resultado:**
¡Adivina qué! 🎉 Acabamos de lanzar algo súper cool y creo que te va a encantar. ¿Ya lo probaste? ¡Cuéntame qué te parece! 👇 #Novedad #Amigos #VibraPositiva #QueEmocion

---

Ahora, genera el contenido para el tema proporcionado.
"""
    }
}

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


# --- Instagram Publishing API Endpoints ---

@app.post("/instagram/publish/{post_id}")
async def publish_to_instagram(
    post_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Publica un post local a Instagram.

    Proceso:
    1. Verifica que el post existe y pertenece al usuario
    2. Obtiene credenciales de Instagram del usuario
    3. Sube la media a Supabase Storage (servidor público)
    4. Crea contenedor de media en Instagram
    5. Publica el contenedor
    6. Actualiza el post con instagram_post_id
    """
    try:
        logger.info(f"Iniciando publicación a Instagram para post_id={post_id}")

        # 1. Verificar que el post existe y pertenece al usuario
        post_response = (
            supabase.table('posts')
            .select('*')
            .eq('id', post_id)
            .eq('user_id', current_user.id)
            .single()
            .execute()
        )

        if not post_response.data:
            raise HTTPException(
                status_code=404,
                detail="Post no encontrado"
            )

        post = post_response.data

        # Verificar que no esté ya publicado en Instagram
        if post.get('instagram_post_id'):
            raise HTTPException(
                status_code=400,
                detail="Este post ya está publicado en Instagram"
            )

        # 2. Obtener credenciales de Instagram
        ig_response = (
            supabase.table('instagram_accounts')
            .select('instagram_business_account_id, long_lived_access_token')
            .eq('user_id', current_user.id)
            .single()
            .execute()
        )

        if not ig_response.data:
            raise HTTPException(
                status_code=400,
                detail="No hay cuenta de Instagram conectada"
            )

        ig_account_id = ig_response.data['instagram_business_account_id']
        access_token = ig_response.data['long_lived_access_token']

        # 3. Verificar que hay media_url (debe estar en servidor público)
        media_url = post.get('media_url')
        if not media_url:
            raise HTTPException(
                status_code=400,
                detail="El post debe tener una imagen o video"
            )

        # 4. Crear contenedor de media en Instagram
        logger.info(f"Creando contenedor de media en Instagram")

        # Determinar tipo de media
        post_type = post.get('post_type', 'image').lower()
        media_type = 'VIDEO' if post_type in ['video', 'reel'] else 'IMAGE'

        container_params = {
            'access_token': access_token,
            'caption': post.get('content', ''),
        }

        if media_type == 'IMAGE':
            container_params['image_url'] = media_url
        else:
            container_params['video_url'] = media_url
            container_params['media_type'] = 'REELS' if post_type == 'reel' else 'VIDEO'

        # Crear contenedor
        container_url = f"https://graph.facebook.com/v19.0/{ig_account_id}/media"
        container_response = requests.post(container_url, data=container_params)

        if container_response.status_code != 200:
            logger.error(
                f"Error al crear contenedor: {container_response.text}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Error al crear contenedor en Instagram: {container_response.json().get('error', {}).get('message', 'Error desconocido')}"
            )

        container_id = container_response.json().get('id')
        logger.info(f"Contenedor creado: {container_id}")

        # 5. Verificar estado del contenedor
        status_url = f"https://graph.facebook.com/v19.0/{container_id}"
        status_params = {
            'fields': 'status_code',
            'access_token': access_token
        }

        # Esperar a que el contenedor esté listo
        import time
        max_attempts = 10
        for attempt in range(max_attempts):
            status_response = requests.get(status_url, params=status_params)
            if status_response.status_code == 200:
                status_code = status_response.json().get('status_code')
                if status_code == 'FINISHED':
                    break
                elif status_code == 'ERROR':
                    raise HTTPException(
                        status_code=500,
                        detail="Error al procesar media en Instagram"
                    )
            time.sleep(2)

        # 6. Publicar el contenedor
        logger.info(f"Publicando contenedor {container_id}")
        publish_url = f"https://graph.facebook.com/v19.0/{ig_account_id}/media_publish"
        publish_params = {
            'creation_id': container_id,
            'access_token': access_token
        }

        publish_response = requests.post(publish_url, data=publish_params)

        if publish_response.status_code != 200:
            logger.error(
                f"Error al publicar: {publish_response.text}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Error al publicar en Instagram: {publish_response.json().get('error', {}).get('message', 'Error desconocido')}"
            )

        instagram_post_id = publish_response.json().get('id')
        logger.info(f"Post publicado exitosamente: {instagram_post_id}")

        # 7. Actualizar post en base de datos
        update_response = (
            supabase.table('posts')
            .update({
                'instagram_post_id': instagram_post_id,
                'status': 'published',
                'publication_date': datetime.utcnow().isoformat()
            })
            .eq('id', post_id)
            .execute()
        )

        return {
            "success": True,
            "instagram_post_id": instagram_post_id,
            "message": "Post publicado exitosamente en Instagram"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al publicar en Instagram: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al publicar en Instagram: {str(e)}"
        )


@app.post("/instagram/schedule/{post_id}")
async def schedule_instagram_post(
    post_id: int,
    scheduled_time: datetime,
    current_user: User = Depends(get_current_user)
):
    """
    Programa un post para ser publicado en Instagram en una fecha/hora específica.
    """
    try:
        logger.info(
            f"Programando post {post_id} para {scheduled_time}"
        )

        # Verificar que el post existe y pertenece al usuario
        post_response = (
            supabase.table('posts')
            .select('*')
            .eq('id', post_id)
            .eq('user_id', current_user.id)
            .single()
            .execute()
        )

        if not post_response.data:
            raise HTTPException(
                status_code=404,
                detail="Post no encontrado"
            )

        post = post_response.data

        # Verificar que no esté ya publicado
        if post.get('instagram_post_id'):
            raise HTTPException(
                status_code=400,
                detail="Este post ya está publicado en Instagram"
            )

        # Verificar que la fecha sea futura
        if scheduled_time <= datetime.utcnow():
            raise HTTPException(
                status_code=400,
                detail="La fecha programada debe ser en el futuro"
            )

        # Actualizar post con fecha programada
        update_response = (
            supabase.table('posts')
            .update({
                'scheduled_publish_time': scheduled_time.isoformat(),
                'status': 'scheduled'
            })
            .eq('id', post_id)
            .execute()
        )

        return {
            "success": True,
            "message": f"Post programado para {scheduled_time.isoformat()}",
            "scheduled_time": scheduled_time.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al programar post: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al programar post: {str(e)}"
        )


@app.get("/instagram/scheduled-posts")
async def get_scheduled_posts(current_user: User = Depends(get_current_user)):
    """
    Obtiene todos los posts programados del usuario.
    """
    try:
        response = (
            supabase.table('posts')
            .select('*')
            .eq('user_id', current_user.id)
            .eq('status', 'scheduled')
            .not_.is_('scheduled_publish_time', 'null')
            .order('scheduled_publish_time', desc=False)
            .execute()
        )

        return response.data

    except Exception as e:
        logger.error(f"Error al obtener posts programados: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener posts programados: {str(e)}"
        )