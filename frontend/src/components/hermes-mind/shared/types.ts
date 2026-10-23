// Shared types + small helpers for the Hermes Mind panels.

import { driveThumbnailUrl, postThumbnailUrl } from '../../../api/media';

export type SourceKind = 'strategy' | 'campaign' | 'rule' | 'output';

export interface Source {
  key: string;
  label: string;
  kind: SourceKind;
  count: number;
  conflict?: boolean;
}

export interface DecisionSummary {
  id: number;
  decision_type: string;
  confidence_score: number;
  applied_rule_labels: string[];
  rationale: string;
  status: 'active' | 'overridden' | 'suggested' | 'accepted' | 'dismissed';
  created_at: string;
  target_label?: string | null;
  campaign_label?: string | null;
  campaign_id?: string | null;
  related_post_id?: number | null;
  related_proposal_id?: string | null;
  media_url?: string | null;
  post_type?: string | null;
  drive_file_id?: string | null;
}

/**
 * The thumbnail to show for a decision's post (Storage photo or planned Drive
 * image, via the app's authenticated thumbnail endpoint), or null. Without a
 * post id it falls back to the Drive thumbnail or the raw media URL.
 */
export function postImageSrc(
  mediaUrl: string | null | undefined,
  driveFileId: string | null | undefined,
  token: string | null,
  postId?: number | null,
): string | null {
  if (postId && token && (mediaUrl || driveFileId)) {
    return postThumbnailUrl({ id: postId, media_url: mediaUrl, drive_file_id: driveFileId }, token);
  }
  if (driveFileId && token) return driveThumbnailUrl(driveFileId, token);
  return mediaUrl ?? null;
}

export interface DecisionsResponse {
  data: DecisionSummary[];
  meta: { total: number; page: number; per_page: number };
}

export interface GraphNode {
  id: string;
  type: string;
  data: Record<string, unknown>;
}

export interface ContextGraphResponse {
  nodes: GraphNode[];
  edges: { id: string; source: string; target: string; type?: string }[];
}

/** Shape of a `type: 'strategy'` graph node's `data` (see get_context_graph). */
export interface StrategyNodeData {
  tone?: string | null;
  style_guide?: string | null;
  target_audience?: string | null;
  hashtag_strategy?: string | null;
  posting_frequency?: string | null;
  best_times?: unknown;
  content_type_mix?: unknown;
  memory_summary?: string | null;
}

/** Shape of a `type: 'campaign'` graph node's `data`. */
export interface CampaignNodeData {
  title?: string | null;
  description?: string | null;
  strategy_mode?: string | null;
  weekly_focus?: Record<string, string> | null;
  milestones?: { date: string; event: string }[] | null;
  status?: string | null;
}

/** Shape of a `type: 'rule'` graph node's `data`. */
export interface RuleNodeData {
  rule_type?: string | null;
  rule_text?: string | null;
  conflicts_with?: { id: number; rule_text: string } | null;
}

export function findNode(graph: ContextGraphResponse | null, id: string): GraphNode | null {
  return graph?.nodes.find((n) => n.id === id) ?? null;
}

export function findNodeByType(graph: ContextGraphResponse | null, type: string): GraphNode | null {
  return graph?.nodes.find((n) => n.type === type) ?? null;
}

export interface BrandRule {
  id: number;
  rule_type: string;
  rule_text: string;
  conflicts_with_id?: number | null;
  source_correction_id?: number | null;
}

export interface PostDetail {
  id: number;
  post_type: string | null;
  scheduled_at: string | null;
  content: string | null;
  media_url: string | null;
  status: string | null;
  drive_file_id: string | null;
}

export interface CorrectionRow {
  id: number;
  content?: { edit_type?: string; user_message?: string; resolution?: string };
}

export interface DecisionDetail {
  decision: DecisionSummary & { applied_rule_ids?: number[] };
  applied_rules: BrandRule[];
  post: PostDetail | null;
  proposal: { id: string; week_start: string | null; status: string | null; slots: number } | null;
}

export interface AuditTrail {
  decision: DecisionSummary;
  applied_rules: BrandRule[];
  source_corrections: CorrectionRow[];
}

const VERBS: Record<string, string> = {
  supabase_create_post: 'Creó un post',
  supabase_create_proposal: 'Creó una propuesta',
  suggest_schedule_change: 'Sugirió un horario',
  suggest_mix_change: 'Sugirió una mezcla',
};
export function verbFor(decisionType: string): string {
  return VERBS[decisionType] ?? decisionType;
}

const STATUS_LABEL: Record<DecisionSummary['status'], string> = {
  active: 'registrada',
  overridden: 'anulada',
  suggested: 'sugerencia',
  accepted: 'aceptada',
  dismissed: 'descartada',
};
export function statusLabel(s: DecisionSummary['status']): string {
  return STATUS_LABEL[s] ?? s;
}

export function isSuggestion(d: { decision_type: string }): boolean {
  return d.decision_type === 'suggest_schedule_change' || d.decision_type === 'suggest_mix_change'
    || d.decision_type === 'suggest_pillars_change';
}

const RELATIVE = new Intl.RelativeTimeFormat('es', { numeric: 'auto' });
export function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const days = Math.round(diffMs / 86_400_000);
  if (Math.abs(days) >= 1) return RELATIVE.format(-days, 'day');
  const hours = Math.round(diffMs / 3_600_000);
  if (Math.abs(hours) >= 1) return RELATIVE.format(-hours, 'hour');
  const mins = Math.round(diffMs / 60_000);
  return RELATIVE.format(-mins, 'minute');
}
