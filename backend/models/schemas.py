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
    instagram_account_id: Optional[int] = None

class PostCreate(PostBase):
    pass

class Post(PostBase):
    id: int
    user_id: str
    media_url: Optional[str] = None
    created_at: datetime
    publication_date: Optional[datetime] = None

# --- Modelos de Inteligencia Artificial ---
class InstagramAccountConfigUpdate(BaseModel):
    telegram_chat_id: Optional[str] = None
    drive_folder_id: Optional[str] = None

class AIPostRequest(BaseModel):
    topic: str
    role: str = "content_manager"

class AIPostResponse(BaseModel):
    generated_text: str

# --- Modelos de Telegram ---
class TelegramUser(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None

class TelegramChat(BaseModel):
    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class TelegramMessage(BaseModel):
    message_id: int
    from_user: Optional[TelegramUser] = Field(None, alias="from")
    chat: TelegramChat
    date: int
    text: Optional[str] = None
    reply_to_message: Optional['TelegramMessage'] = None

    class Config:
        populate_by_name = True

class TelegramCallbackQuery(BaseModel):
    id: str
    from_user: TelegramUser = Field(..., alias="from")
    message: Optional[TelegramMessage] = None
    inline_message_id: Optional[str] = None
    chat_instance: Optional[str] = None
    data: Optional[str] = None
    game_short_name: Optional[str] = None

    class Config:
        populate_by_name = True

class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[TelegramMessage] = None
    edited_message: Optional[TelegramMessage] = None
    channel_post: Optional[TelegramMessage] = None
    edited_channel_post: Optional[TelegramMessage] = None
    callback_query: Optional[TelegramCallbackQuery] = None

class TelegramLinkTokenResponse(BaseModel):
    token: str
    expires_at: datetime

TelegramMessage.model_rebuild()

