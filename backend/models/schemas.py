from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Literal, Optional, Any, Union

from utils.timezones import get_zone_info

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
    trial_graduation: Optional[Literal["MANUAL", "SS_PERFORMANCE"]] = None

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
    thumbnail_url_base: Optional[str] = None
    media_thumbnail_url: Optional[str] = None
    is_collaboration: bool = False
    content_format: Optional[str] = None
    content_structure: Optional[dict] = None
    quality_report: Optional[dict] = None
    matrix_role: Optional[str] = None
    trial_graduation: Optional[Literal["MANUAL", "SS_PERFORMANCE"]] = None

# --- Modelos de Inteligencia Artificial ---
class InstagramAccountConfigUpdate(BaseModel):
    telegram_chat_id: Optional[str] = None
    drive_folder_id: Optional[str] = None
    # Zonas IANA; un null explícito restablece el valor por defecto (AD-4)
    primary_timezone: Optional[str] = None
    secondary_timezone: Optional[str] = None
    detected_timezone: Optional[str] = None

    @field_validator('primary_timezone', 'secondary_timezone', 'detected_timezone')
    @classmethod
    def _validate_timezone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return get_zone_info(value).key

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

class TelegramDocument(BaseModel):
    file_id: str
    file_unique_id: str
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None

class TelegramMessage(BaseModel):
    message_id: int
    from_user: Optional[TelegramUser] = Field(None, alias="from")
    chat: TelegramChat
    date: int
    text: Optional[str] = None
    caption: Optional[str] = None
    photo: Optional[list[TelegramPhotoSize]] = None
    document: Optional[TelegramDocument] = None
    reply_to_message: Optional['TelegramMessage'] = None

    model_config = ConfigDict(populate_by_name=True)

class TelegramCallbackQuery(BaseModel):
    id: str
    from_user: TelegramUser = Field(..., alias="from")
    message: Optional[TelegramMessage] = None
    inline_message_id: Optional[str] = None
    chat_instance: Optional[str] = None
    data: Optional[str] = None
    game_short_name: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)

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
MAX_REFERENCE_ACCOUNTS = 5


class AgentConfig(BaseModel):
    account_type: Literal["personal", "professional"] = "personal"
    sector: Optional[str] = None
    purpose: Optional[str] = None
    target_audience: Optional[str] = None
    style_guide: Optional[str] = None
    default_tone: Literal["energetic", "professional", "casual", "inspirational"] = "energetic"
    default_language: Literal["es", "en"] = "es"
    # Ya no llega al agente (manda el mix); opcional e ignorada al guardar
    posting_frequency: Optional[Literal["daily", "few_times_week", "once_or_twice_week", "weekly"]] = None
    best_times: list[str] = ["09:00", "18:00"]
    content_pillars: list[str] = []
    hashtag_strategy: Literal["minimal", "moderate", "maximum"] = "moderate"
    caption_voice: Optional[Literal["personal", "professional"]] = None
    reference_accounts: list[str] = Field(default=[], max_length=MAX_REFERENCE_ACCOUNTS)
    posts_per_week: int = 3
    scheduling_mode: Literal["fixed", "flexible"] = "flexible"
    preferred_days: list[str] = []
    content_type_mix: dict = {"post": 2, "reel": 1, "carousel": 1, "story": 0}
    # Filtro anti-slop por cuenta (migración 033); None = no se modifica
    humanizer_enabled: Optional[bool] = None
    banned_phrases: Optional[list[str]] = None


class AgentConfigPatch(BaseModel):
    """Guardado por pestaña (AD-7): solo se escriben los campos enviados."""
    account_type: Optional[Literal["personal", "professional"]] = None
    sector: Optional[str] = None
    purpose: Optional[str] = None
    target_audience: Optional[str] = None
    style_guide: Optional[str] = None
    default_tone: Optional[Literal["energetic", "professional", "casual", "inspirational"]] = None
    default_language: Optional[Literal["es", "en"]] = None
    best_times: Optional[list[str]] = None
    content_pillars: Optional[list[str]] = None
    hashtag_strategy: Optional[Literal["minimal", "moderate", "maximum"]] = None
    caption_voice: Optional[Literal["personal", "professional"]] = None
    reference_accounts: Optional[list[str]] = Field(default=None, max_length=MAX_REFERENCE_ACCOUNTS)
    scheduling_mode: Optional[Literal["fixed", "flexible"]] = None
    preferred_days: Optional[list[str]] = None
    content_type_mix: Optional[dict] = None
    humanizer_enabled: Optional[bool] = None
    banned_phrases: Optional[list[str]] = None


class StrategyIssue(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    field: str
    tab: Literal["marca", "publicacion", "referentes"]
    message: str


class ReferenceTopPost(BaseModel):
    caption_first_line: str = ""
    media_type: str
    engagement_rate: float
    permalink: Optional[str] = None
    timestamp: Optional[str] = None
    hook_formula: Optional[str] = None


class ReferenceAnalysis(BaseModel):
    username: str
    status: Literal["ok", "not_professional", "not_found", "error"]
    error_message: Optional[str] = None
    followers: Optional[int] = None
    posts_per_week: Optional[float] = None
    format_mix: Optional[dict[str, int]] = None
    top_posts: Optional[list[ReferenceTopPost]] = None
    hook_formulas: Optional[list[str]] = None
    median_engagement_rate: Optional[float] = None
    fetched_at: Optional[str] = None


class ReferenceAccountsResponse(BaseModel):
    references: list[ReferenceAnalysis] = []
    summary: str = ""
    refreshed: bool = False


class StrategyDiagnosticsResponse(BaseModel):
    issues: list[StrategyIssue] = []
    context_preview: str
    profile_audit: "ProfileAuditResponse"

class VisualAnalysis(BaseModel):
    drive_file_id: str
    gemini_description: dict
    suggested_caption: Optional[str] = None

class VisualAnalysisResult(BaseModel):
    objects: list[str] = []
    text_visible: str = ""
    mood: str = ""
    theme: str = ""
    raw_description: str = ""
    suggested_caption: str = ""
    aesthetic_score: int = 5
    composition_type: Literal["primer_plano", "detalle", "paisaje", "producto", "accion", "retrato"] = "primer_plano"
    content_type_fit: Literal["feed_post", "carousel_slide", "story"] = "feed_post"
    suggested_hook: str = ""

class CalendarSlot(BaseModel):
    day: str
    post_id: Optional[int] = None
    image_id: Optional[str] = None
    media_url: Optional[str] = None  # foto adjuntada por Telegram (sustituye a image_id)
    theme: str
    caption: str
    post_type: Optional[str] = None  # "post" | "reel" | "carousel" | "story"
    matrix_role: Optional[str] = None
    hook_candidates: Optional[list[str]] = None

class ProposalSlot(CalendarSlot):
    scheduled_at: Optional[str] = None  # instante del post enlazado; solo en respuestas (AD-7)

class ContentProposal(BaseModel):
    id: str
    account_id: str
    week_start: str
    slots: list[ProposalSlot]
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


# --- Modelos de Motor de Calidad de Contenido (Content Quality Engine) ---

class LintRequest(BaseModel):
    caption: str
    keywords: Optional[list[str]] = None
    format: Optional[Literal["post", "reel", "carousel"]] = "post"


class SlopHit(BaseModel):
    term: str
    index: int
    suggestion: str


class SlopReport(BaseModel):
    score: int = 0
    hits: list[SlopHit] = []
    invisible_chars: int = 0
    em_dash_count: int = 0


class HookReport(BaseModel):
    formula_id: Optional[int] = None
    formula_name: Optional[str] = None
    score: int = 0
    dealbreakers: list[str] = []


class QualityWarning(BaseModel):
    code: str
    message: str


class QualityReport(BaseModel):
    visible_text: str
    visible_length: int
    truncated: bool
    hashtag_count: int
    hashtag_limit: int = 5
    hashtags_over_limit: list[str] = []
    keywords_missing_in_visible: list[str] = []
    slop: SlopReport = Field(default_factory=SlopReport)
    hook: HookReport = Field(default_factory=HookReport)
    warnings: list[QualityWarning] = []


class HumanizeRequest(BaseModel):
    text: str
    language: Optional[Literal["es", "en"]] = "es"
    extra_banned: Optional[list[str]] = None


class HumanizeChange(BaseModel):
    from_text: str = Field(..., alias="from")
    to: str
    rule: str

    model_config = ConfigDict(populate_by_name=True)


class HumanizeResponse(BaseModel):
    text: str
    changes: list[HumanizeChange] = []


class HookScoreRequest(BaseModel):
    hook: str
    strategy_mode: Optional[Literal["commercial_campaign", "personal_storyline"]] = None


class HookAlternative(BaseModel):
    formula_id: int
    name: str
    template: str


class HookFormula(BaseModel):
    id: int
    name: str
    template: str
    best_for: list[str] = []


class HookScoreResponse(BaseModel):
    formula_id: Optional[int] = None
    formula_name: Optional[str] = None
    score: int = 0
    dealbreakers: list[str] = []
    alternatives: list[HookAlternative] = []


class BeatItemInput(BaseModel):
    label: str
    text: str


class BeatsRequest(BaseModel):
    beats: list[BeatItemInput]
    wpm: Optional[int] = Field(165, gt=0, le=400)


class BeatItemOutput(BaseModel):
    label: str
    text: Optional[str] = None
    start_s: float
    end_s: float
    duration_s: float
    alert: Optional[Literal["OVER_4S"]] = None


class BeatsResponse(BaseModel):
    beats: list[BeatItemOutput] = []
    total_s: float = 0.0
    loops_to_hook: bool = False


class ProfileAuditItem(BaseModel):
    id: str
    label: str
    passed: bool
    weight: int
    tip: str


class ProfileAuditRequest(BaseModel):
    account_id: int


class ProfileAuditResponse(BaseModel):
    score: int
    items: list[ProfileAuditItem] = []
    bio_rewrite: Optional[str] = None


# --- Modelos de Generadores de Formato (Fase C) ---

class ReelHookCandidate(BaseModel):
    text: str
    score: int = 0
    formula_id: Optional[int] = None
    formula_name: Optional[str] = None


class ReelOut(BaseModel):
    hooks: list[ReelHookCandidate] = []
    beats: BeatsResponse = Field(default_factory=BeatsResponse)
    on_screen_text: list[str] = []
    caption: str
    report: QualityReport


class CarouselSlide(BaseModel):
    index: int
    role: Literal["cover", "stake", "idea", "recap", "cta"]
    text: str
    word_count: int = 0


class CarouselOut(BaseModel):
    slides: list[CarouselSlide] = []
    caption: str
    report: QualityReport
    warnings: list[str] = []


class StoryFrame(BaseModel):
    index: int
    role: str
    text: str
    sticker: Literal["poll", "question", "link", "dm_cta", "none"] = "none"
    sticker_payload: Optional[dict] = None


class StoryOut(BaseModel):
    frames: list[StoryFrame] = []
    caption: Optional[str] = None
    report: Optional[QualityReport] = None


class RepurposeOut(BaseModel):
    reels: list[ReelOut] = []
    carousels: list[CarouselOut] = []


class ReelRequest(BaseModel):
    account_id: int
    topic: str
    strategy_mode: Optional[Literal["commercial_campaign", "personal_storyline"]] = None
    language: Optional[Literal["es", "en"]] = "es"


class CarouselRequest(BaseModel):
    account_id: int
    topic: str
    slides: int = Field(default=7, ge=6, le=10)
    strategy_mode: Optional[Literal["commercial_campaign", "personal_storyline"]] = None
    language: Optional[Literal["es", "en"]] = "es"


class StoryRequest(BaseModel):
    account_id: int
    topic: Optional[str] = None
    strategy_mode: Optional[Literal["commercial_campaign", "personal_storyline"]] = None
    language: Optional[Literal["es", "en"]] = "es"


class RepurposeRequest(BaseModel):
    account_id: int
    transcript: str = Field(..., max_length=30000)
    strategy_mode: Optional[Literal["commercial_campaign", "personal_storyline"]] = None
    language: Optional[Literal["es", "en"]] = "es"


# --- Modelos de Profile Audit y Swipe File (Fase E) ---

class ProfileAuditRequest(BaseModel):
    account_id: int


class ProfileAuditItem(BaseModel):
    id: str
    label: str
    passed: bool
    weight: int
    tip: str


class ProfileAuditResponse(BaseModel):
    score: int
    items: list[ProfileAuditItem] = []
    bio_rewrite: Optional[str] = None


class SwipeFileItem(BaseModel):
    post_id: Any
    hook_text: str
    formula_id: Optional[int] = None
    formula_name: Optional[str] = None
    outlier_multiple: Optional[float] = None
    sends_per_reach: Optional[float] = None
    is_trial: bool = False
    reels_skip_rate: Optional[float] = None
    is_competitor: bool = False
    reference_username: Optional[str] = None
    permalink: Optional[str] = None


class SwipeFileByFormula(BaseModel):
    formula_id: int
    formula_name: Optional[str] = None
    count: int = 0
    avg_outlier: Optional[float] = None


class SwipeFileResponse(BaseModel):
    items: list[SwipeFileItem] = []
    by_formula: list[SwipeFileByFormula] = []


# --- Modelos de Conversión y Comunidad (Fase F) ---

CommentTriageLabel = Literal["lead", "question", "objection", "support", "noise"]


class CommentTriageItem(BaseModel):
    id: Union[str, int]
    text: str
    username: Optional[str] = None
    label: CommentTriageLabel
    suggested_reply: str


class CommentsTriageResponse(BaseModel):
    source: Literal["api", "unavailable", "manual"]
    comments: list[CommentTriageItem] = []
    # Solo con source="unavailable": por qué no se pudieron leer de Instagram
    unavailable_reason: Optional[Literal["not_published", "story", "collaboration", "api_error"]] = None


class CommentsTriageManualRequest(BaseModel):
    comments: list[str] = Field(..., min_length=1, max_length=100)
    account_id: Optional[int] = None
    strategy_mode: Optional[Literal["commercial_campaign", "personal_storyline"]] = None
    language: Optional[str] = "es"


class ProspectCommentItem(BaseModel):
    type: int = Field(..., ge=1, le=9)
    type_name: str
    text: str


class ProspectCommentsRequest(BaseModel):
    target_post_text: str = Field(..., min_length=1, max_length=5000)
    account_id: Optional[int] = None
    strategy_mode: Optional[Literal["commercial_campaign", "personal_storyline"]] = None
    language: Optional[str] = "es"


class ProspectCommentsResponse(BaseModel):
    suggestions: list[ProspectCommentItem] = []


class DmFunnelRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=50)
    resource_description: str = Field(..., min_length=1, max_length=500)
    account_id: Optional[int] = None
    language: Optional[str] = "es"


class DmFunnelResponse(BaseModel):
    delivery_dm: str = Field(..., min_length=1)
    follow_ups: list[str] = Field(..., min_length=2, max_length=2)


StrategyDiagnosticsResponse.model_rebuild()
