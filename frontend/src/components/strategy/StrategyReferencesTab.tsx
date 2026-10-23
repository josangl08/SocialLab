import React from 'react';
import type { AgentConfigPatch, AgentStrategyConfig } from '../../types';
import { TagInput } from './TagInput';
import { MAX_REFERENCE_ACCOUNTS } from './strategyOptions';
import './StrategyReferencesTab.css';

interface StrategyReferencesTabProps {
  draft: AgentStrategyConfig;
  onChange: (patch: AgentConfigPatch) => void;
}

export const StrategyReferencesTab: React.FC<StrategyReferencesTabProps> = ({ draft, onChange }) => (
  <div className="srt">
    <section className="stg-section">
      <div className="d-flex align-items-center justify-content-between">
        <h3 className="stg-section-title"><i className="bi bi-at" />Cuentas de referencia</h3>
        <span className="srt-count">{draft.reference_accounts.length}/{MAX_REFERENCE_ACCOUNTS}</span>
      </div>
      <p className="srt-help small">Cuentas que te inspiran o con las que compites. Hermes las tiene en cuenta al planificar.</p>
      <TagInput id="srt-refs" prefix="@" variant="info" max={MAX_REFERENCE_ACCOUNTS}
        values={draft.reference_accounts}
        normalize={raw => raw.trim().replace(/^@/, '')}
        onChange={v => onChange({ reference_accounts: v })}
        placeholder="cuenta_referente" />
    </section>
  </div>
);
