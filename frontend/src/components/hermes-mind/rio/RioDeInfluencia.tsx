import React, { useMemo } from 'react';
import './RioDeInfluencia.css';
import type { Source } from '../shared/types';

export interface RioOutput {
  key: string;
  label: string;
  color: string;
  n: number;
}

interface RioProps {
  sources: Source[];
  totalDecisions: number;
  outputs: RioOutput[];
  /** key of the active ribbon — a source key or an `out:*` key */
  activeSourceKey: string | null;
  onSelectSource: (key: string) => void;
}

const KIND_COLOR: Record<string, string> = {
  strategy: '#3b82f6',
  campaign: '#f59e0b',
  rule: '#8b5cf6',
};

const VB_W = 900;
const VB_H = 150;
const SRC_X = 150;
const HUB_L = 430;
const HUB_R = 508;
const OUT_X = 812;
const TOP = 12;
const BOTTOM = 138;
const SPAN = BOTTOM - TOP;
const MID = TOP + SPAN / 2;

export const RioDeInfluencia: React.FC<RioProps> = ({
  sources,
  totalDecisions,
  outputs,
  activeSourceKey,
  onSelectSource,
}) => {
  const { srcRibbons, outRibbons } = useMemo(() => {
    const totalCount = Math.max(1, sources.reduce((a, s) => a + s.count, 0));
    const gap = 5;
    const usable = SPAN - gap * Math.max(0, sources.length - 1);

    let cursor = TOP;
    const srcRibbons = sources.map((s) => {
      const h = Math.max(8, usable * (s.count / totalCount));
      const y0 = cursor;
      const y1 = cursor + h;
      const yc = cursor + h / 2;
      cursor += h + gap;
      const hHalf = Math.max(4, (y1 - y0) * 0.42);
      const d =
        `M ${SRC_X} ${y0}` +
        ` C ${SRC_X + 170} ${y0} ${HUB_L - 150} ${MID - hHalf} ${HUB_L} ${MID - hHalf}` +
        ` L ${HUB_L} ${MID + hHalf}` +
        ` C ${HUB_L - 150} ${MID + hHalf} ${SRC_X + 170} ${y1} ${SRC_X} ${y1} Z`;
      return { s, d, yc, fill: s.conflict ? '#fbbf24' : KIND_COLOR[s.kind] };
    });

    const outTotal = Math.max(1, outputs.reduce((a, o) => a + o.n, 0));
    const outRibbons = outputs.map((o, i) => {
      const yc = TOP + SPAN * (0.16 + i * 0.34);
      const w = Math.max(3, 12 * (o.n / outTotal));
      const d =
        `M ${HUB_R} ${MID - w}` +
        ` C ${HUB_R + 150} ${MID - w} ${OUT_X - 130} ${yc - w} ${OUT_X} ${yc - w}` +
        ` L ${OUT_X} ${yc + w}` +
        ` C ${OUT_X - 130} ${yc + w} ${HUB_R + 150} ${MID + w} ${HUB_R} ${MID + w} Z`;
      return { o, d, yc };
    });

    return { srcRibbons, outRibbons };
  }, [sources, outputs]);

  const filtered = activeSourceKey != null;
  const outFiltered = activeSourceKey?.startsWith('out:') ?? false;
  const srcFiltered = filtered && !outFiltered;

  return (
    <section className={`hm-panel rio${filtered ? ' is-filtered' : ''}`}>
      <div className="rio-top">
        <span className="hm-panel-label">Río de influencia</span>
        <span className="rio-hint">
          Grosor = nº de decisiones ·{' '}
          <b>toca una fuente (izq.) o un resultado (der.) para filtrar la lista</b>
        </span>
      </div>
      <div className="rio-svg-wrap">
        <svg
          className="rio-svg"
          viewBox={`0 0 ${VB_W} ${VB_H}`}
          role="img"
          aria-label="Influencia de las fuentes de contexto sobre las decisiones"
        >
          <defs>
            <linearGradient id="hm-rio-ribbon" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="#3b82f6" />
              <stop offset="0.5" stopColor="#8b5cf6" />
              <stop offset="1" stopColor="#ec4899" />
            </linearGradient>
          </defs>

          {srcRibbons.map(({ s, d, fill }) => {
            const active = s.key === activeSourceKey;
            return (
              <path
                key={s.key}
                d={d}
                className="rio-ribbon"
                fill={fill}
                fillOpacity={active ? 0.92 : filtered ? 0.1 : 0.5}
                onClick={() => onSelectSource(s.key)}
              />
            );
          })}

          {srcRibbons.map(({ s, yc }) => (
            <text
              key={`l-${s.key}`}
              x={SRC_X - 14}
              y={yc}
              className={`rio-label${s.key === activeSourceKey ? ' is-active' : ''}`}
              textAnchor="end"
              onClick={() => onSelectSource(s.key)}
            >
              {s.conflict ? '⚠ ' : ''}
              {s.label} {s.count}
            </text>
          ))}

          <rect
            x={HUB_L}
            y={TOP + 3}
            width={HUB_R - HUB_L}
            height={SPAN - 6}
            rx={7}
            fill="url(#hm-rio-ribbon)"
            fillOpacity={0.9}
          />
          <text x={(HUB_L + HUB_R) / 2} y={MID - 7} className="rio-hub-text" style={{ fontSize: 16 }}>
            {totalDecisions}
          </text>
          <text
            x={(HUB_L + HUB_R) / 2}
            y={MID + 9}
            className="rio-hub-text"
            style={{ fontSize: 9, fill: 'rgba(255,255,255,0.85)' }}
          >
            decisiones
          </text>

          {outRibbons.map(({ o, d, yc }) => {
            const active = o.key === activeSourceKey;
            return (
              <g
                key={o.key}
                className="rio-out"
                onClick={() => onSelectSource(o.key)}
              >
                <path
                  d={d}
                  className="rio-ribbon"
                  fill={o.color}
                  fillOpacity={active ? 0.85 : outFiltered ? 0.1 : srcFiltered ? 0.14 : 0.32}
                />
                <circle cx={OUT_X} cy={yc} r={3.5} fill={o.color} fillOpacity={active || !filtered ? 1 : 0.4} />
                <text
                  x={OUT_X + 12}
                  y={yc}
                  className={`rio-out-text${active ? ' is-active' : ''}`}
                >
                  {o.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </section>
  );
};
