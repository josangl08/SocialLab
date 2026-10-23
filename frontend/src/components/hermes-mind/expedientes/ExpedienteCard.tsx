import React from 'react';
import { ConfidenceRing } from '../shared/ConfidenceRing';
import { PostImage } from '../shared/PostImage';
import { SourceChip } from '../shared/SourceChip';
import {
  type DecisionSummary,
  type Source,
  verbFor,
  statusLabel,
  relativeTime,
  postImageSrc,
  fromReferences,
} from '../shared/types';

interface ExpedienteCardProps {
  decision: DecisionSummary;
  /** applied rules resolved to source chips (Estrategia + Campaña + reglas) */
  sources: Source[];
  token: string | null;
  selected: boolean;
  onSelect: (id: number) => void;
}

const ICON_CAL = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} className="hm-ph">
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M3 10h18M8 3v4M16 3v4" />
  </svg>
);
const ICON_CLOCK = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} className="hm-ph">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);

function metaLine(d: DecisionSummary): string {
  if (d.related_post_id) return d.target_label ?? 'Post';
  if (d.related_proposal_id) return d.target_label ?? 'Propuesta semanal';
  return 'Sugerencia';
}

const ICON_PHOTO = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} className="hm-ph">
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <circle cx="9" cy="10" r="2" />
    <path d="M4 18l5-4 4 3 3-2 4 3" />
  </svg>
);

const Thumb: React.FC<{ decision: DecisionSummary; token: string | null; small?: boolean }> = ({
  decision,
  token,
  small,
}) => {
  const base = `exp-thumb${small ? ' exp-thumb-sm' : ''}`;
  if (decision.related_post_id) {
    // "post" is a square feed image; stories/reels are portrait
    const square = (decision.post_type ?? '').toLowerCase() === 'post';
    const src = postImageSrc(decision.media_url, decision.drive_file_id, token, decision.related_post_id);
    return (
      <div className={`${base}${square ? ' is-square' : ''}`}>
        <PostImage src={src} fallback={ICON_PHOTO} />
      </div>
    );
  }
  return (
    <div className={`${base} is-square`}>{decision.related_proposal_id ? ICON_CAL : ICON_CLOCK}</div>
  );
};

export const ExpedienteCard: React.FC<ExpedienteCardProps> = ({
  decision,
  sources,
  token,
  selected,
  onSelect,
}) => {
  const badgeClass =
    decision.status === 'overridden'
      ? 'badge-overridden'
      : decision.status === 'suggested'
        ? 'badge-suggested'
        : decision.status === 'accepted'
          ? 'badge-accepted'
          : 'badge-active';

  return (
    <article
      className={`exp${selected ? ' sel' : ''}`}
      role="button"
      tabIndex={0}
      onClick={() => onSelect(decision.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(decision.id);
        }
      }}
    >
      <div className="exp-bar">
        <ConfidenceRing score={decision.confidence_score} size={54} />
        <span className="exp-verb">{verbFor(decision.decision_type)}</span>
        <span className={`hm-badge ${badgeClass}`}>{statusLabel(decision.status)}</span>
        {fromReferences(decision) && <span className="hm-badge exp-badge-refs">Referentes</span>}
        <span className="exp-when">{relativeTime(decision.created_at)}</span>
      </div>

      <div className={`exp-body${selected ? ' exp-body-mini' : ''}`}>
        <Thumb decision={decision} token={token} small={selected} />
        <div className="exp-main">
          <div className="exp-sources">
            {sources.map((s) => (
              <SourceChip key={s.key} label={s.label} kind={s.kind} conflict={s.conflict} />
            ))}
          </div>
          {selected ? (
            <span className="exp-open-hint">Detalle en la Órbita ←</span>
          ) : (
            <>
              <p className="exp-reason">{decision.rationale}</p>
              <div className="exp-meta">
                <b>{metaLine(decision)}</b>
                {decision.campaign_label ? ` · ${decision.campaign_label}` : ''}
              </div>
            </>
          )}
        </div>
      </div>
    </article>
  );
};
