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
    post_type: Optional[str] = None  # "post", "reel", "story", "image", "video"
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
    is_ai_generated: Optional[bool] = None
    drive_file_id: Optional[str] = None

# --- Modelos de Inteligencia Artificial ---
class InstagramAccountConfigUpdate(BaseModel):
    telegram_chat_id: Optional[str] = None
    drive_folder_id: Optional[str] = None

class AIPostRequest(BaseModel):
    topic: str
    role: str = "content_manager"
    account_type: Optional[Literal["personal", "professional"]] = None
    default_tone: Optional[str] = None
    style_guide: Optional[str] = None
    target_audience: Optional[str] = None
    hashtag_strategy: Optional[Literal["minimal", "moderate", "maximum"]] = None
    default_language: Optional[Literal["es", "en"]] = None

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

class TelegramPhotoSize(BaseModel):
    file_id: str
    file_unique_id: str
    width: int
    height: int
    file_size: Optional[int] = None

class TelegramMessage(BaseModel):
    message_id: int
    from_user: Optional[TelegramUser] = Field(None, alias="from")
    chat: TelegramChat
    date: int
    text: Optional[str] = None
    photo: Optional[list[TelegramPhotoSize]] = None
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


# --- Modelos de Agente Autónomo ---
class AgentConfig(BaseModel):
    account_type: Literal["personal", "professional"] = "personal"
    sector: Optional[str] = None
    purpose: Optional[str] = None
    target_audience: Optional[str] = None
    style_guide: Optional[str] = None
    default_tone: Literal["energetic", "professional", "casual", "inspirational"] = "energetic"
    default_language: Literal["es", "en"] = "es"
    posting_frequency: Literal["daily", "few_times_week", "once_or_twice_week", "weekly"] = "few_times_week"
    best_times: list[str] = ["09:00", "18:00"]
    content_pillars: list[str] = []
    hashtag_strategy: Literal["minimal", "moderate", "maximum"] = "moderate"
    caption_voice: Optional[Literal["personal", "professional"]] = None
    reference_accounts: list[str] = []
    posts_per_week: int = 3
    scheduling_mode: Literal["fixed", "flexible"] = "flexible"
    preferred_days: list[str] = []
    content_type_mix: dict = {"post": 2, "reel": 1, "carousel": 1, "story": 0}

class VisualAnalysis(BaseModel):
    drive_file_id: str
    gemini_description: dict
    suggested_caption: Optional[str] = None

class CalendarSlot(BaseModel):
    day: str
    post_id: Optional[int] = None
    image_id: Optional[str] = None
    theme: str
    caption: str
    post_type: Optional[str] = None  # "post" | "reel" | "carousel" | "story"

class ContentProposal(BaseModel):
    id: str
    account_id: str
    week_start: str
    slots: list[CalendarSlot]
    status: Literal["pending_approval", "approved", "rejected"] = "pending_approval"

class AgentLog(BaseModel):
    account_id: str
    images_scanned: int = 0
    images_analyzed: int = 0
    posts_drafted: int = 0
    error: Optional[str] = None
    duration_ms: Optional[int] = None

class MonthlyCampaign(BaseModel):
    id: Optional[str] = None
    account_id: int
    month_date: str
    strategy_mode: Literal["commercial_campaign", "personal_storyline"]
    title: str
    description: Optional[str] = None
    milestones: list[dict] = []
    weekly_focus: dict = {}
    status: Literal["pending_approval", "approved", "rejected"] = "approved"
    generated_by: Literal["manual", "hermes"] = "manual"
    resolved_at: Optional[datetime] = None


class BrandRule(BaseModel):
    id: Optional[int] = None
    account_id: int
    rule_type: Literal["tone", "frequency", "format", "topic", "brand_safety", "other"]
    rule_text: str
    source_correction_id: Optional[int] = None
    confidence: float = 1.0
    is_active: bool = True
    times_applied: int = 0
    previous_version_id: Optional[int] = None
    conflicts_with_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AgentDecision(BaseModel):
    id: Optional[int] = None
    account_id: int
    session_id: Optional[str] = None
    decision_type: str
    related_post_id: Optional[int] = None
    related_proposal_id: Optional[str] = None
    campaign_id: Optional[str] = None
    applied_rule_ids: list[int] = []
    applied_rule_labels: list[str] = []
    confidence_score: float = 0.5
    rationale: Optional[str] = None
    tool_args: Optional[dict] = None
    tool_result: Optional[dict] = None
    status: Literal["active", "overridden", "suggested", "accepted"] = "active"
    overridden_at: Optional[datetime] = None
    override_correction_id: Optional[int] = None
    accepted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None




# --- Modelos de Google Drive ---
class DriveToken(BaseModel):
    user_id: str
    connected: bool
    scopes: Optional[list[str]] = None
    connected_at: Optional[datetime] = None



