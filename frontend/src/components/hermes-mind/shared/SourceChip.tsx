import React from 'react';
import type { SourceKind } from './types';

interface SourceChipProps {
  label: string;
  kind: SourceKind;
  conflict?: boolean;
}

const KIND_COLOR: Record<SourceKind, string> = {
  strategy: '#3b82f6',
  campaign: '#f59e0b',
  rule: '#8b5cf6',
  output: '#ec4899',
};

export const SourceChip: React.FC<SourceChipProps> = ({ label, kind, conflict }) => {
  const color = conflict ? '#fbbf24' : KIND_COLOR[kind];
  return (
    <span
      className="hm-chip"
      style={{ color, background: `${color}1a`, borderColor: `${color}66` }}
    >
      <span className="hm-chip-dot" style={{ background: color }} />
      {label}
      {conflict ? ' ⚠' : ''}
    </span>
  );
};
