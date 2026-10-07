import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './HermesMind.css';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import type { InstagramAccount, ContentProposal } from '../../types';
import { RioDeInfluencia, type RioOutput } from './rio/RioDeInfluencia';
import { ExpedientesPanel } from './expedientes/ExpedientesPanel';
import { OrbitaPanel } from './orbita/OrbitaPanel';
import {
  type DecisionSummary,
  type DecisionsResponse,
  type ContextGraphResponse,
  type Source,
} from './shared/types';

export interface HermesMindProps {
  accountId?: number;
}

const WEEK_FORMAT = new Intl.DateTimeFormat('es', { day: 'numeric', month: 'short', year: 'numeric' });

function humanizeRuleType(t: string): string {
  return t.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

const OUTPUT_LABEL: Record<string, string> = {
  'out:post': 'Posts',
  'out:proposal': 'Propuestas',
  'out:suggestion': 'Sugerencias',
};

/**
 * Which Río *output* bucket a decision belongs to (`out:post` | `out:proposal` |
 * `out:suggestion`). Must mirror the rioOutputs counting in the component, or the
 * ribbon thickness and the filtered list will disagree.
 */
export function outputMatches(d: DecisionSummary, key: string): boolean {
  const bucket = d.related_post_id
    ? 'out:post'
    : d.related_proposal_id
      ? 'out:proposal'
      : 'out:suggestion';
  return bucket === key;
}

/**
 * Which proposal the "Propuesta" filter should default to when Hermes Mind
 * first loads, so the Río shows the most relevant week instead of every
 * decision the account ever produced. `proposals` arrives newest-first
 * (created_at desc). Return '' to mean "Toda la cuenta" (no filter).
 */
export function pickDefaultProposalId(proposals: ContentProposal[]): string {
  // Newest-first: the first proposal still in play (awaiting review or approved
  // as the current week). Rejected proposals carry no context. No match → ''
  // ("Toda la cuenta").
  const relevant = proposals.find(
    (p) => p.status === 'pending_approval' || p.status === 'approved',
  );
  return relevant?.id ?? '';
}

export const HermesMind: React.FC<HermesMindProps> = ({ accountId: accountIdProp }) => {
  const { token } = useAuth();
  const [accountId, setAccountId] = useState<number | null>(accountIdProp ?? null);
  const [proposals, setProposals] = useState<ContentProposal[]>([]);
  const [proposalId, setProposalId] = useState<string>('');

  const [decisions, setDecisions] = useState<DecisionSummary[]>([]);
  const [graph, setGraph] = useState<ContextGraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const [activeSourceKey, setActiveSourceKey] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // resolve the user's primary account (single-account app for now)
  useEffect(() => {
    if (accountIdProp) return;
    apiClient
      .get<InstagramAccount[]>('/instagram/accounts')
      .then((accs) => accs.length > 0 && setAccountId(accs[0].id))
      .catch(() => {});
  }, [accountIdProp]);

  const didInitProposal = useRef(false);
  useEffect(() => {
    if (accountId == null) return;
    apiClient
      .get<ContentProposal[]>(`/api/agent/proposals?account_id=${accountId}`)
      .then(setProposals)
      .catch(() => setProposals([]));
  }, [accountId]);

  // On first load, start the filter on the most relevant proposal instead of
  // "Toda la cuenta" — keeps stale decisions from older sessions out of view.
  useEffect(() => {
    if (didInitProposal.current || proposals.length === 0) return;
    didInitProposal.current = true;
    const initial = pickDefaultProposalId(proposals);
    if (initial) setProposalId(initial);
  }, [proposals]);

  useEffect(() => {
    if (accountId == null) return;
    setLoading(true);
    setError(false);
    const q = proposalId ? `&proposal_id=${proposalId}` : '';
    Promise.all([
      apiClient.get<DecisionsResponse>(`/api/agent/decisions?account_id=${accountId}&per_page=50${q}`),
      apiClient.get<ContextGraphResponse>(`/api/agent/context-graph?account_id=${accountId}${q}`),
    ])
      .then(([dec, g]) => {
        setDecisions(dec.data);
        setGraph(g);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [accountId, proposalId, refreshKey]);

  const conflictLabels = useMemo(() => {
    const set = new Set<string>();
    for (const n of graph?.nodes ?? []) {
      if (n.type === 'rule' && n.data.conflicts_with) {
        set.add(humanizeRuleType(String(n.data.rule_type ?? '')));
      }
    }
    return set;
  }, [graph]);

  const sourcesFor = useCallback(
    (d: DecisionSummary): Source[] => {
      const out: Source[] = [{ key: 'strategy', label: 'Estrategia', kind: 'strategy', count: 0 }];
      if (d.campaign_label) out.push({ key: 'campaign', label: 'Campaña', kind: 'campaign', count: 0 });
      for (const label of Array.from(new Set(d.applied_rule_labels))) {
        out.push({ key: `rule:${label}`, label, kind: 'rule', count: 0, conflict: conflictLabels.has(label) });
      }
      return out;
    },
    [conflictLabels],
  );

  // Río data — the influence picture, computed from what we already have
  const { rioSources, rioOutputs } = useMemo(() => {
    const total = decisions.length;
    const ruleCount = new Map<string, number>();
    let campaignCount = 0;
    let posts = 0;
    let props = 0;
    let sugg = 0;
    for (const d of decisions) {
      if (d.campaign_label) campaignCount += 1;
      if (d.related_post_id) posts += 1;
      else if (d.related_proposal_id) props += 1;
      else sugg += 1;
      for (const label of Array.from(new Set(d.applied_rule_labels))) {
        ruleCount.set(label, (ruleCount.get(label) ?? 0) + 1);
      }
    }
    const rioSources: Source[] = [
      { key: 'strategy', label: 'Estrategia', kind: 'strategy', count: total },
    ];
    if (campaignCount > 0) {
      rioSources.push({ key: 'campaign', label: 'Campaña', kind: 'campaign', count: campaignCount });
    }
    Array.from(ruleCount.entries())
      .sort((a, b) => b[1] - a[1])
      .forEach(([label, count]) =>
        rioSources.push({ key: `rule:${label}`, label, kind: 'rule', count, conflict: conflictLabels.has(label) }),
      );

    const rioOutputs: RioOutput[] = [
      { key: 'out:post', label: `${posts} ${posts === 1 ? 'post' : 'posts'}`, color: '#ec4899', n: posts },
      { key: 'out:proposal', label: `${props} ${props === 1 ? 'propuesta' : 'propuestas'}`, color: '#f472b6', n: props },
      { key: 'out:suggestion', label: `${sugg} ${sugg === 1 ? 'sugerencia' : 'sugerencias'}`, color: '#818cf8', n: sugg },
    ].filter((o) => o.n > 0);

    return { rioSources, rioOutputs };
  }, [decisions, conflictLabels]);

  const visibleDecisions = useMemo(() => {
    if (!activeSourceKey || activeSourceKey === 'strategy') return decisions;
    if (activeSourceKey === 'campaign') return decisions.filter((d) => d.campaign_label);
    if (activeSourceKey.startsWith('out:')) {
      return decisions.filter((d) => outputMatches(d, activeSourceKey));
    }
    const label = activeSourceKey.slice('rule:'.length);
    return decisions.filter((d) => d.applied_rule_labels.includes(label));
  }, [decisions, activeSourceKey]);

  // always keep a valid selection: first of the visible list
  useEffect(() => {
    if (visibleDecisions.length === 0) {
      setSelectedId(null);
      return;
    }
    setSelectedId((cur) =>
      cur != null && visibleDecisions.some((d) => d.id === cur) ? cur : visibleDecisions[0].id,
    );
  }, [visibleDecisions]);

  const selectedDecision = useMemo(
    () => decisions.find((d) => d.id === selectedId) ?? null,
    [decisions, selectedId],
  );
  const activeSource = useMemo<Source | null>(() => {
    if (activeSourceKey?.startsWith('out:')) {
      return {
        key: activeSourceKey,
        label: OUTPUT_LABEL[activeSourceKey] ?? 'Resultado',
        kind: 'output',
        count: 0,
      };
    }
    return rioSources.find((s) => s.key === activeSourceKey) ?? null;
  }, [rioSources, activeSourceKey]);

  const toggleSource = useCallback(
    (key: string) => setActiveSourceKey((cur) => (cur === key ? null : key)),
    [],
  );

  if (accountId == null) {
    return (
      <div className="hermes-mind-page">
        <div className="hm-state">
          <div className="hm-spinner" />
          <p>Cargando cuenta…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="hermes-mind-page">
      <header className="hm-head">
        <h1>
          Hermes Mind
          <span className="hm-sub">Por qué el agente decidió lo que decidió — y cómo corregirlo.</span>
        </h1>
        {proposals.length > 0 && (
          <label className="hm-filter">
            Propuesta
            <select value={proposalId} onChange={(e) => setProposalId(e.target.value)}>
              <option value="">Toda la cuenta</option>
              {proposals.map((p) => (
                <option key={p.id} value={p.id}>
                  Semana del {WEEK_FORMAT.format(new Date(p.week_start))}
                  {p.status !== 'approved' ? ` · ${p.status}` : ''}
                </option>
              ))}
            </select>
          </label>
        )}
      </header>

      <RioDeInfluencia
        sources={rioSources}
        totalDecisions={decisions.length}
        outputs={rioOutputs}
        activeSourceKey={activeSourceKey}
        onSelectSource={toggleSource}
      />

      <div className="hm-workbench">
        <OrbitaPanel
          decision={selectedDecision}
          graph={graph}
          token={token}
          onChanged={() => setRefreshKey((k) => k + 1)}
        />
        <ExpedientesPanel
          decisions={visibleDecisions}
          sourcesFor={sourcesFor}
          token={token}
          selectedId={selectedId}
          onSelect={setSelectedId}
          loading={loading}
          error={error}
          activeSource={activeSource}
          onClearFilter={() => setActiveSourceKey(null)}
        />
      </div>
    </div>
  );
};

export default HermesMind;
