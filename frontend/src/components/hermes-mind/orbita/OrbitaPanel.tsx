import React, { useCallback, useEffect, useLayoutEffect, useMemo, useState } from 'react';
import './OrbitaPanel.css';
import { apiClient } from '../../../api/client';
import { ConfidenceRing } from '../shared/ConfidenceRing';
import { PostImage } from '../shared/PostImage';
import {
  type DecisionSummary,
  type DecisionDetail,
  type AuditTrail,
  type SourceKind,
  type BrandRule,
  type ContextGraphResponse,
  type StrategyNodeData,
  type CampaignNodeData,
  type RuleNodeData,
  findNode,
  findNodeByType,
  verbFor,
  isSuggestion,
  postImageSrc,
} from '../shared/types';

interface OrbitaPanelProps {
  decision: DecisionSummary | null;
  graph: ContextGraphResponse | null;
  token: string | null;
  onChanged: () => void;
}

interface ArcSource {
  key: string;
  kind: SourceKind;
  label: string;
  conflict: boolean;
  ruleId?: number;
  ruleType?: string;
}

const KIND_COLOR: Record<SourceKind, string> = {
  strategy: '#3b82f6',
  campaign: '#f59e0b',
  rule: '#8b5cf6',
  output: '#ec4899',
};
const KIND_LABEL: Record<SourceKind, string> = {
  strategy: 'Estrategia',
  campaign: 'Campaña',
  rule: 'Regla',
  output: 'Resultado',
};
const HUMANIZE: Record<string, string> = {
  tone: 'Tono',
  frequency: 'Frecuencia',
  format: 'Formato',
  topic: 'Tema',
  brand_safety: 'Marca segura',
  other: 'Regla',
};

const STAGE_H = 198;

export const OrbitaPanel: React.FC<OrbitaPanelProps> = ({ decision, graph, token, onChanged }) => {
  const [detail, setDetail] = useState<DecisionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [audit, setAudit] = useState<AuditTrail | null>(null);
  const [openSource, setOpenSource] = useState<string | null>(null);
  const [correcting, setCorrecting] = useState(false);
  const [correctText, setCorrectText] = useState('');
  const [busy, setBusy] = useState(false);

  // callback ref: the stage element only mounts once a decision is selected
  // (the empty state has no stage), so a [] effect would miss it — this fires
  // on every attach/detach
  const [stageEl, setStageEl] = useState<HTMLDivElement | null>(null);
  const [stageW, setStageW] = useState(520);

  useLayoutEffect(() => {
    if (!stageEl) return;
    setStageW(stageEl.clientWidth); // measure before first paint — no 520px flash
    const ro = new ResizeObserver(([entry]) => setStageW(entry.contentRect.width));
    ro.observe(stageEl);
    return () => ro.disconnect();
  }, [stageEl]);

  useEffect(() => {
    setDetail(null);
    setAudit(null);
    setOpenSource(null);
    setCorrecting(false);
    setCorrectText('');
    if (decision == null) return;
    setLoading(true);
    apiClient
      .get<DecisionDetail>(`/api/agent/decisions/${decision.id}`)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [decision]);

  const sources = useMemo<ArcSource[]>(() => {
    if (!decision) return [];
    const list: ArcSource[] = [{ key: 'strategy', kind: 'strategy', label: 'Estrategia', conflict: false }];
    if (decision.campaign_label) {
      list.push({ key: 'campaign', kind: 'campaign', label: decision.campaign_label, conflict: false });
    }
    // One chip per distinct rule_type. When a type has more than one active rule
    // (a conflict pair, e.g. two "format" rules) they'd otherwise render as
    // duplicate chips — group them and surface both texts in the detail panel.
    const byType = new Map<string, BrandRule[]>();
    for (const r of detail?.applied_rules ?? []) {
      const group = byType.get(r.rule_type) ?? [];
      group.push(r);
      byType.set(r.rule_type, group);
    }
    for (const [ruleType, group] of byType) {
      list.push({
        key: `rule-${ruleType}`,
        kind: 'rule',
        label: HUMANIZE[ruleType] ?? ruleType,
        conflict: group.some((r) => !!r.conflicts_with_id) || group.length > 1,
        ruleId: group[0].id,
        ruleType,
      });
    }
    return list;
  }, [decision, detail]);

  // the ring's centre — shared by the SVG lines and the ring element, so they
  // can never drift apart regardless of the measured width
  const W = stageW || 520;
  const cx = W / 2;
  const cy = STAGE_H * 0.58;

  // polar-ish placement of the source chips on an elliptical arc above the ring
  const placed = useMemo(() => {
    const R = Math.max(112, Math.min(176, W / 2 - 62));
    const VF = 0.58;
    const ringR = 64; // ConfidenceRing edge ≈ 54px + a small breathing gap
    const n = sources.length;
    return sources.map((s, i) => {
      const deg = n === 1 ? 270 : 200 + 140 * (i / (n - 1));
      const t = (deg * Math.PI) / 180;
      const x = cx + R * Math.cos(t);
      const y = cy + R * VF * Math.sin(t);
      const dx = x - cx;
      const dy = y - cy;
      const a = Math.atan2(dy, dx);
      // inner end: on the ring edge, with a small breathing gap
      const ex = cx + ringR * Math.cos(a);
      const ey = cy + ringR * Math.sin(a);
      // outer end: stop at the chip's border (never run under the box)
      const HALF_W = 62;
      const HALF_H = 25;
      const tt = Math.min(
        Math.abs(dx) > 0.5 ? HALF_W / Math.abs(dx) : Infinity,
        Math.abs(dy) > 0.5 ? HALF_H / Math.abs(dy) : Infinity,
        1,
      );
      return { s, x, y, ex, ey, lx: x - dx * tt, ly: y - dy * tt };
    });
  }, [sources, W, cx, cy]);

  const toggleSource = useCallback(
    (key: string, ruleId?: number) => {
      setOpenSource((prev) => (prev === key ? null : key));
      if (ruleId != null && !audit && decision) {
        apiClient
          .get<AuditTrail>(`/api/agent/decisions/${decision.id}/audit-trail`)
          .then(setAudit)
          .catch(() => setAudit(null));
      }
    },
    [audit, decision],
  );

  const submitOverride = useCallback(async () => {
    if (!decision || !correctText.trim()) return;
    setBusy(true);
    try {
      await apiClient.post(`/api/agent/decisions/${decision.id}/override`, { user_message: correctText });
      setCorrecting(false);
      setCorrectText('');
      onChanged();
    } finally {
      setBusy(false);
    }
  }, [decision, correctText, onChanged]);

  const acceptSuggestion = useCallback(async () => {
    if (!decision) return;
    setBusy(true);
    try {
      await apiClient.post(`/api/agent/decisions/${decision.id}/accept-suggestion`, {});
      onChanged();
    } finally {
      setBusy(false);
    }
  }, [decision, onChanged]);

  if (!decision) {
    return (
      <section className="hm-panel orbita hm-col">
        <div className="orbita-head">
          <span className="hm-panel-label">Órbita de la decisión</span>
        </div>
        <div className="hm-state">
          <i className="bi bi-bullseye" />
          <p>Selecciona una decisión para ver de qué se alimentó.</p>
        </div>
      </section>
    );
  }

  const openRuleGroup = openSource?.startsWith('rule-')
    ? (detail?.applied_rules ?? []).filter((r) => `rule-${r.rule_type}` === openSource)
    : [];
  const openRule = openRuleGroup[0] ?? null;
  const openCorrection = openRule?.source_correction_id
    ? audit?.source_corrections.find((c) => c.id === openRule.source_correction_id)
    : null;
  const hasConflict = openRuleGroup.some((r) => !!r.conflicts_with_id) || openRuleGroup.length > 1;

  // The text of the rule(s) in tension: prefer what the graph resolved
  // (conflicts_with.rule_text on the rule node), fall back to the other rule
  // texts in the same group.
  const conflictTexts = Array.from(
    new Set(
      openRuleGroup.flatMap((r) => {
        const node = findNode(graph, `rule-${r.id}`);
        const fromGraph = (node?.data as RuleNodeData | undefined)?.conflicts_with?.rule_text;
        if (fromGraph) return [fromGraph];
        return openRuleGroup.filter((o) => o.id !== r.id).map((o) => o.rule_text);
      }),
    ),
  );

  const strategyData = (findNodeByType(graph, 'strategy')?.data as StrategyNodeData | undefined) ?? null;
  const campaignNode =
    (decision.campaign_id ? findNode(graph, `campaign-${decision.campaign_id}`) : null) ??
    findNodeByType(graph, 'campaign');
  const campaignData = (campaignNode?.data as CampaignNodeData | undefined) ?? null;

  return (
    <section className="hm-panel orbita hm-col">
      <div className="orbita-head">
        <span className="hm-panel-label">Órbita de la decisión</span>
      </div>
      <div className="orbita-scroll">
        <div className="orbita-stage" ref={setStageEl}>
          <svg className="orbita-lines" aria-hidden="true">
            {placed.map(({ s, ex, ey, lx, ly }) => (
              <g key={s.key}>
                <line
                  x1={ex}
                  y1={ey}
                  x2={lx}
                  y2={ly}
                  stroke={s.conflict ? 'rgba(251,191,36,0.5)' : 'rgba(255,255,255,0.16)'}
                  strokeWidth={1.5}
                />
                <circle cx={ex} cy={ey} r={2.5} fill={s.conflict ? '#fbbf24' : KIND_COLOR[s.kind]} />
              </g>
            ))}
          </svg>

          <div className="orbita-ring" style={{ left: cx, top: cy }}>
            <ConfidenceRing score={decision.confidence_score} size={112} />
            <div className="orbita-verb">{verbFor(decision.decision_type)}</div>
          </div>

          {placed.map(({ s, x, y }) => (
            <button
              key={s.key}
              type="button"
              className={`orb-src${openSource === s.key ? ' sel' : ''}`}
              data-kind={s.kind}
              data-conflict={s.conflict ? '1' : undefined}
              style={{ left: x, top: y }}
              onClick={() => toggleSource(s.key, s.ruleId)}
            >
              <span className="orb-src-k">{KIND_LABEL[s.kind]}</span>
              <span className="orb-src-v">
                {s.label}
                {s.conflict ? ' ⚠' : ''}
              </span>
            </button>
          ))}
        </div>

        {openSource && (
          <div className={`arc-detail${hasConflict && openRuleGroup.length > 0 ? ' is-conflict' : ''}`}>
            {openRuleGroup.length > 0 ? (
              <>
                <span className="arc-lead">
                  {openRuleGroup.length > 1 ? 'Reglas aprendidas' : 'Regla aprendida'}
                </span>
                <ul className="arc-list">
                  {openRuleGroup.map((r) => (
                    <li key={r.id}>{r.rule_text}</li>
                  ))}
                </ul>
                {openCorrection ? (
                  <>Nació de tu corrección: “{openCorrection.content?.user_message ?? ''}”</>
                ) : (
                  'Sin corrección de origen registrada.'
                )}
                {hasConflict ? (
                  <>
                    <br />
                    <br />⚠{' '}
                    {conflictTexts.length > 0
                      ? `En tensión con: ${conflictTexts.map((t) => `“${t}”`).join('; ')}. Hermes las muestra en tensión, no elige ganadora.`
                      : 'En conflicto con otra regla activa del mismo tipo — Hermes las muestra en tensión, no elige ganadora.'}
                  </>
                ) : null}
              </>
            ) : openSource === 'strategy' ? (
              <>
                <span className="arc-lead">Estrategia de la cuenta</span>
                {strategyData ? (
                  <dl className="arc-dl">
                    {strategyData.tone ? (
                      <>
                        <dt>Tono</dt>
                        <dd>{strategyData.tone}</dd>
                      </>
                    ) : null}
                    {strategyData.target_audience ? (
                      <>
                        <dt>Audiencia</dt>
                        <dd>{strategyData.target_audience}</dd>
                      </>
                    ) : null}
                    {strategyData.style_guide ? (
                      <>
                        <dt>Guía de estilo</dt>
                        <dd>{strategyData.style_guide}</dd>
                      </>
                    ) : null}
                    {strategyData.posting_frequency ? (
                      <>
                        <dt>Frecuencia</dt>
                        <dd>{strategyData.posting_frequency}</dd>
                      </>
                    ) : null}
                    {strategyData.hashtag_strategy ? (
                      <>
                        <dt>Hashtags</dt>
                        <dd>{strategyData.hashtag_strategy}</dd>
                      </>
                    ) : null}
                  </dl>
                ) : (
                  <> — contexto que Hermes recibe en cada sesión.</>
                )}
              </>
            ) : (
              <>
                <span className="arc-lead">
                  {campaignData?.title ?? decision.campaign_label ?? 'Campaña del mes'}
                  {campaignData?.status && campaignData.status !== 'approved' ? (
                    <span className="arc-badge">pendiente</span>
                  ) : null}
                </span>
                {campaignData ? (
                  <>
                    {campaignData.description ? <p className="arc-p">{campaignData.description}</p> : null}
                    {campaignData.weekly_focus ? (
                      <ol className="arc-weeks">
                        {['1', '2', '3', '4'].map((w) =>
                          campaignData.weekly_focus?.[w] ? (
                            <li key={w}>
                              <b>Semana {w}:</b> {campaignData.weekly_focus[w]}
                            </li>
                          ) : null,
                        )}
                      </ol>
                    ) : null}
                    {campaignData.milestones && campaignData.milestones.length > 0 ? (
                      <ul className="arc-list">
                        {campaignData.milestones.map((m) => (
                          <li key={m.date}>
                            {m.date} — {m.event}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </>
                ) : (
                  <> — contexto que Hermes recibe en cada sesión.</>
                )}
              </>
            )}
          </div>
        )}

        <p className="orbita-rationale">{decision.rationale}</p>

        <OrbitaResult decision={decision} detail={detail} loading={loading} token={token} />

        <div className="orbita-foot">
          {isSuggestion(decision) ? (
            decision.status === 'suggested' ? (
              <button type="button" className="hm-btn hm-btn-accept" disabled={busy} onClick={acceptSuggestion}>
                <i className="bi bi-check-circle" /> Aplicar a Ajustes
              </button>
            ) : (
              <span className="orbita-note">Sugerencia {decision.status === 'accepted' ? 'aceptada' : decision.status}.</span>
            )
          ) : (
            <button type="button" className="hm-btn hm-btn-danger" onClick={() => setCorrecting((v) => !v)}>
              <i className="bi bi-x-circle" /> Corregir esta decisión
            </button>
          )}
        </div>

        {correcting && (
          <div className="correct-box">
            <textarea
              value={correctText}
              onChange={(e) => setCorrectText(e.target.value)}
              placeholder="Explica qué debería cambiar. Hermes lo aprende como una regla nueva."
            />
            <div className="correct-row">
              <button type="button" className="hm-btn" onClick={() => setCorrecting(false)}>
                Cancelar
              </button>
              <button
                type="button"
                className="hm-btn hm-btn-danger"
                disabled={busy || !correctText.trim()}
                onClick={submitOverride}
              >
                Registrar corrección
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

const ICON_CAL = <i className="bi bi-calendar-week" />;
const ICON_CLOCK = <i className="bi bi-clock-history" />;

const OrbitaResult: React.FC<{
  decision: DecisionSummary;
  detail: DecisionDetail | null;
  loading: boolean;
  token: string | null;
}> = ({ decision, detail, loading, token }) => {
  if (decision.related_post_id) {
    const post = detail?.post;
    const src = postImageSrc(
      post?.media_url ?? decision.media_url,
      post?.drive_file_id ?? decision.drive_file_id,
      token,
      decision.related_post_id,
    );
    return (
      <div className="orbita-post">
        <div className="orbita-post-media is-photo">
          <PostImage src={src} fallback={<i className="bi bi-image" />} />
        </div>
        <div className="orbita-post-meta">
          <span className="t">{decision.target_label ?? 'Publicación'}{post?.status ? ` · ${post.status}` : ''}</span>
          <span className="cap">{loading ? 'Cargando…' : post?.content ?? 'Sin caption.'}</span>
        </div>
      </div>
    );
  }
  if (decision.related_proposal_id) {
    const p = detail?.proposal;
    return (
      <div className="orbita-post">
        <div className="orbita-post-media is-icon">{ICON_CAL}</div>
        <div className="orbita-post-meta">
          <span className="t">{decision.target_label ?? 'Propuesta semanal'}</span>
          <span className="cap">
            {p ? `${p.slots} publicaciones planificadas · ${p.status ?? ''}` : 'Cargando…'}
          </span>
        </div>
      </div>
    );
  }
  return (
    <div className="orbita-post">
      <div className="orbita-post-media is-icon">{ICON_CLOCK}</div>
      <div className="orbita-post-meta">
        <span className="t">Sugerencia</span>
        <span className="cap">Visible en el timeline; no cambia nada por sí sola.</span>
      </div>
    </div>
  );
};
