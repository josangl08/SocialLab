from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal, Optional

# --- Modelos de Usuario ---
class UserRegister(BaseModel):
    email: str
    password: str

class User(BaseModel):
    id: str
    email: str
    created_at: Optional[datetime] = None

class Token(BaseModel):
    access_token: str
    token_type: str

# --- Modelos de Publicaciones (Posts) ---
class PostBase(BaseModel):
    content: str
    post_type: str  # "post", "reel", "story", "image", "video"
    status: Literal["draft", "scheduled", "published", "failed"] = "draft"
    scheduled_at: Optional[datetime] = None

class PostCreate(PostBase):
    pass

class Post(PostBase):
    id: int
    user_id: str
    media_url: Optional[str] = None
    created_at: datetime
    publication_date: Optional[datetime] = None

# --- Modelos de Inteligencia Artificial ---
class AIPostRequest(BaseModel):
    topic: str
    role: str = "content_manager"

class AIPostResponse(BaseModel):
    generated_text: str
