// Shared types + small helpers for the Hermes Mind panels.

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
  status: 'active' | 'overridden' | 'suggested' | 'accepted';
  created_at: string;
  target_label?: string | null;
  campaign_label?: string | null;
  related_post_id?: number | null;
  related_proposal_id?: string | null;
  media_url?: string | null;
  post_type?: string | null;
  drive_file_id?: string | null;
}

/**
 * The image to show for a decision's post: the published Instagram media if it
 * exists, otherwise the planned Drive image via the app's authenticated proxy
 * (same URL shape the planner uses for draft slots), otherwise null.
 */
export function postImageSrc(
  mediaUrl: string | null | undefined,
  driveFileId: string | null | undefined,
  token: string | null,
  baseUrl: string,
): string | null {
  if (mediaUrl) return mediaUrl;
  if (driveFileId && token) {
    return `${baseUrl}/api/drive/files/${encodeURIComponent(driveFileId)}/image?token=${encodeURIComponent(token)}`;
  }
  return null;
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
};
export function statusLabel(s: DecisionSummary['status']): string {
  return STATUS_LABEL[s] ?? s;
}

export function isSuggestion(d: { decision_type: string }): boolean {
  return d.decision_type === 'suggest_schedule_change' || d.decision_type === 'suggest_mix_change';
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
