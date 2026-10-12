export interface Post {
  id: number;
  user_id: string;
  content: string;
  media_url: string | null;
  post_type: string;
  status: string;
  scheduled_at: string | null;
  created_at: string;
  publication_date?: string | null;
  is_ai_generated?: boolean | null;
  drive_file_id?: string | null;
  instagram_account_id?: number | null;
  content_format?: 'post' | 'reel' | 'carousel' | 'story' | null;
  content_structure?: ContentStructure | null;
  quality_report?: QualityReport | null;
  matrix_role?: string | null;
  trial_graduation?: 'MANUAL' | 'SS_PERFORMANCE' | null;
}

export interface InstagramAccount {
  id: number;
  username: string | null;
  account_name: string | null;
  profile_picture_url?: string | null;
  followers_count?: number | null;
  expires_at?: string | null;
  token_invalid?: boolean;
  is_active?: boolean;
  telegram_chat_id?: string | null;
  drive_folder_id?: string | null;
  account_type?: string;
  sector?: string;
  purpose?: string;
  target_audience?: string;
  style_guide?: string;
  default_tone?: string;
  default_language?: string;
  posting_frequency?: string;
  best_times?: string[];
  content_pillars?: string[];
  hashtag_strategy?: string;
  last_agent_sync?: string | null;
  humanizer_enabled?: boolean;
  banned_phrases?: string[];
}

export interface CalendarSlot {
  day: string;
  post_id?: number | null;
  image_id?: string | null;
  media_url?: string | null;
  theme: string;
  caption: string;
  post_type?: string;
  matrix_role?: string;
  hook_candidates?: string[];
}

export interface ContentProposal {
  id: string;
  account_id: string;
  week_start: string;
  slots: CalendarSlot[];
  status: 'pending_approval' | 'approved' | 'rejected';
  created_at?: string;
}

export interface AgentLog {
  id: string;
  account_id: number;
  run_at: string;
  images_scanned: number;
  images_analyzed: number;
  posts_drafted: number;
  error: string | null;
  duration_ms: number | null;
}

// --- Content Studio & Content Quality Types ---

export type StrategyMode = 'commercial_campaign' | 'personal_storyline';
export type ContentFormat = 'post' | 'reel' | 'carousel' | 'story';

export interface LintRequest {
  caption: string;
  keywords?: string[];
  format?: 'post' | 'reel' | 'carousel';
}

export interface SlopHit {
  term: string;
  index: number;
  suggestion: string;
}

export interface SlopReport {
  score: number;
  hits: SlopHit[];
  invisible_chars: number;
  em_dash_count: number;
}

export interface HookReport {
  formula_id?: number | null;
  formula_name?: string | null;
  score: number;
  dealbreakers: string[];
}

export interface QualityWarning {
  code: string;
  message: string;
}

export interface QualityReport {
  visible_text: string;
  visible_length: number;
  truncated: boolean;
  hashtag_count: number;
  hashtag_limit: number;
  hashtags_over_limit: string[];
  keywords_missing_in_visible: string[];
  slop: SlopReport;
  hook: HookReport;
  warnings: QualityWarning[];
}

export interface HumanizeRequest {
  text: string;
  language?: 'es' | 'en';
  extra_banned?: string[];
}

export interface HumanizeChange {
  from: string;
  to: string;
  rule: string;
}

export interface HumanizeResponse {
  text: string;
  changes: HumanizeChange[];
}

export interface HookScoreRequest {
  hook: string;
  strategy_mode?: StrategyMode;
}

export interface HookAlternative {
  formula_id: number;
  name: string;
  template: string;
}

export interface HookFormula {
  id: number;
  name: string;
  template: string;
  best_for: string[];
}

export interface HookScoreResponse {
  formula_id?: number | null;
  formula_name?: string | null;
  score: number;
  dealbreakers: string[];
  alternatives: HookAlternative[];
}

export interface BeatItemInput {
  label: string;
  text: string;
}

export interface BeatsRequest {
  beats: BeatItemInput[];
  wpm?: number;
}

export interface BeatItemOutput {
  label: string;
  text?: string;
  start_s: number;
  end_s: number;
  duration_s: number;
  alert?: 'OVER_4S' | null;
}

export interface BeatsResponse {
  beats: BeatItemOutput[];
  total_s: number;
  loops_to_hook: boolean;
}

export interface ProfileAuditItem {
  id: string;
  label: string;
  passed: boolean;
  weight: number;
  tip: string;
}

export interface ProfileAuditResponse {
  score: number;
  items: ProfileAuditItem[];
  bio_rewrite?: string | null;
}

// --- Generadores de Formato (Fase C) ---

export interface ReelHookCandidate {
  text: string;
  score: number;
  formula_id?: number | null;
  formula_name?: string | null;
}

export interface ReelOut {
  hooks: ReelHookCandidate[];
  beats: BeatsResponse;
  on_screen_text: string[];
  caption: string;
  report: QualityReport;
}

// posts.content_structure: slides (carrusel) | hooks + beats + texto en pantalla (Reel)
export interface ContentStructure {
  slides?: CarouselSlide[];
  hooks?: ReelHookCandidate[];
  beats?: BeatsResponse;
  on_screen_text?: string[];
}

export type CarouselSlideRole = 'cover' | 'stake' | 'idea' | 'recap' | 'cta';

export interface CarouselSlide {
  index: number;
  role: CarouselSlideRole;
  text: string;
  word_count: number;
}

export interface CarouselOut {
  slides: CarouselSlide[];
  caption: string;
  report: QualityReport;
  warnings?: string[];
}

export type StoryStickerType = 'poll' | 'question' | 'link' | 'dm_cta' | 'none';

export interface StoryFrame {
  index: number;
  role: string;
  text: string;
  sticker: StoryStickerType;
  sticker_payload?: Record<string, unknown> | null;
}

export interface StoryOut {
  frames: StoryFrame[];
  caption?: string | null;
  report?: QualityReport | null;
}

export interface RepurposeOut {
  reels: ReelOut[];
  carousels: CarouselOut[];
}

export interface ReelRequest {
  account_id: number;
  topic: string;
  strategy_mode?: StrategyMode;
  language?: 'es' | 'en';
}

export interface CarouselRequest {
  account_id: number;
  topic: string;
  slides?: number;
  strategy_mode?: StrategyMode;
  language?: 'es' | 'en';
}

export interface StoryRequest {
  account_id: number;
  topic?: string;
  strategy_mode?: StrategyMode;
  language?: 'es' | 'en';
}

export interface RepurposeRequest {
  account_id: number;
  transcript: string;
  strategy_mode?: StrategyMode;
  language?: 'es' | 'en';
}

// --- Profile Audit & Swipe File (Fase E) ---

export interface ProfileAuditItem {
  id: string;
  label: string;
  passed: boolean;
  weight: number;
  tip: string;
}

export interface ProfileAuditResponse {
  score: number;
  items: ProfileAuditItem[];
  bio_rewrite?: string | null;
}

export interface SwipeFileItem {
  post_id: string | number;
  hook_text: string;
  formula_id?: number | null;
  formula_name?: string | null;
  outlier_multiple?: number | null;
  sends_per_reach?: number | null;
  is_trial?: boolean;
  reels_skip_rate?: number | null;
}

export interface SwipeFileByFormula {
  formula_id: number;
  formula_name?: string | null;
  count: number;
  avg_outlier?: number | null;
}

export interface SwipeFileResponse {
  items: SwipeFileItem[];
  by_formula: SwipeFileByFormula[];
}

// --- Conversión y Comunidad (Fase F) ---

export type CommentTriageLabel = 'lead' | 'question' | 'objection' | 'support' | 'noise';

export type CommentTriageSource = 'api' | 'unavailable' | 'manual';

export interface CommentTriageItem {
  id: string | number;
  text: string;
  username?: string | null;
  label: CommentTriageLabel;
  suggested_reply: string;
}

export interface CommentsTriageResponse {
  source: CommentTriageSource;
  comments: CommentTriageItem[];
}

export interface CommentsTriageManualRequest {
  comments: string[];
  account_id?: number;
  strategy_mode?: StrategyMode;
  language?: 'es' | 'en';
}

export interface ProspectCommentItem {
  type: number;
  type_name: string;
  text: string;
}

export interface ProspectCommentsRequest {
  target_post_text: string;
  account_id?: number;
  strategy_mode?: StrategyMode;
  language?: 'es' | 'en';
}

export interface ProspectCommentsResponse {
  suggestions: ProspectCommentItem[];
}

export interface DmFunnelRequest {
  keyword: string;
  resource_description: string;
  account_id?: number;
  language?: 'es' | 'en';
}

export interface DmFunnelResponse {
  delivery_dm: string;
  follow_ups: string[];
}
