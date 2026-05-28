from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from database.supabase_client import get_supabase_client
from models.schemas import UserRegister, User, Token
from auth.dependencies import get_current_user

router = APIRouter(tags=["Authentication"])
supabase = get_supabase_client()

@router.post("/register", response_model=User)
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

@router.post("/token", response_model=Token)
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

@router.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Obtiene la información del usuario autenticado actualmente.
    """
    return current_user
