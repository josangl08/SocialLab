import React from 'react';

interface ConfidenceRingProps {
  /** 0–1 */
  score: number;
  size?: number;
}

// Lightweight SVG ring — sized freely (small in a card, large in the Órbita).
// Replaces the old recharts ConfidenceGauge, which was locked to 72px.
export const ConfidenceRing: React.FC<ConfidenceRingProps> = ({ score, size = 44 }) => {
  const pct = Math.max(0, Math.min(100, Math.round(score * 100)));
  const sw = Math.max(3, Math.min(6, size * 0.09));
  const r = (size - sw * 2) / 2;
  const c = 2 * Math.PI * r;
  const stroke = pct >= 80 ? '#34d399' : pct >= 55 ? '#818cf8' : '#fbbf24';

  return (
    <div className="hm-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth={sw} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={stroke}
          strokeWidth={sw}
          strokeLinecap="round"
          strokeDasharray={`${((c * pct) / 100).toFixed(1)} ${c.toFixed(1)}`}
        />
      </svg>
      <span className="hm-ring-val" style={{ fontSize: size * 0.26 }}>
        {pct}
        <small>%</small>
      </span>
    </div>
  );
};
