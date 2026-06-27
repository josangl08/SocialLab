import React from 'react';
import { LineChart, Line, ResponsiveContainer } from 'recharts';
import './KPICard.css';

interface KPICardProps {
  title: string;
  value: string | number;
  change?: string;
  trend?: 'up' | 'down' | 'neutral';
  icon: string;
  color?: 'primary' | 'success' | 'warning' | 'info' | 'purple' | 'danger';
  comparison?: { value: string | number; label: string };
  loading?: boolean;
  sparklineData?: number[];
  sparklineColor?: string;
}

const computeGrowth = (data: number[]): { label: string; positive: boolean } | null => {
  if (data.length < 2) return null;
  const first = data[0];
  const last = data[data.length - 1];
  if (first === 0) return null;
  const pct = ((last - first) / Math.abs(first)) * 100;
  return { label: `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`, positive: pct >= 0 };
};

export const KPICard: React.FC<KPICardProps> = ({
  title,
  value,
  change,
  trend = 'neutral',
  icon,
  color = 'primary',
  comparison,
  loading = false,
  sparklineData,
  sparklineColor
}) => {
  const getTrendArrow = () => (trend === 'up' ? 'up' : trend === 'down' ? 'down' : 'right');
  const sparkGrowth = sparklineData ? computeGrowth(sparklineData) : null;
  const chartData = sparklineData?.map((v) => ({ v })) ?? [];
  const lineColor = sparklineColor ?? 'rgba(255, 255, 255, 0.75)';

  if (loading) {
    return (
      <div className={`kpi-card kpi-card-${color}`}>
        <div className="kpi-skeleton">
          <div className="skeleton-icon"></div>
          <div className="skeleton-content">
            <div className="skeleton-title"></div>
            <div className="skeleton-value"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`kpi-card kpi-card-${color}`}>
      <div className="kpi-card-top">
        <div className="kpi-icon-wrap">
          <i className={`bi bi-${icon}`}></i>
        </div>
        <div className="kpi-content">
          <h3 className="kpi-title">{title}</h3>
          <div className="kpi-value">{value}</div>
          {(sparkGrowth || change) && (
            <div className={`kpi-growth${sparkGrowth ? (sparkGrowth.positive ? ' kpi-growth-up' : ' kpi-growth-down') : ''}`}>
              {sparkGrowth ? (
                <>
                  <i className={`bi bi-arrow-${sparkGrowth.positive ? 'up' : 'down'}-short`}></i>
                  {sparkGrowth.label}
                </>
              ) : (
                <>
                  <i className={`bi bi-arrow-${getTrendArrow()}-short`}></i>
                  {change}
                </>
              )}
            </div>
          )}
          {comparison && !sparkGrowth && (
            <div className="kpi-comparison">
              <span className="comparison-label">{comparison.label}:</span>
              <span className="comparison-value">{comparison.value}</span>
            </div>
          )}
        </div>
      </div>

      {chartData.length > 1 && (
        <div className="kpi-sparkline">
          <ResponsiveContainer width="100%" height={40}>
            <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
              <Line
                type="monotone"
                dataKey="v"
                stroke={lineColor}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

export default KPICard;
