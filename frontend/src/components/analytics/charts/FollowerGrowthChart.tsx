import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';

interface FollowerGrowthData {
  date: string;
  follower_count: number;
  change: number;
}

interface FollowerGrowthChartProps {
  data: FollowerGrowthData[];
  loading?: boolean;
  timeRange?: string;
}

export const FollowerGrowthChart: React.FC<FollowerGrowthChartProps> = ({
  data,
  loading = false,
  timeRange = '30days'
}) => {
  const effectiveDays = timeRange === 'all' ? 365 : timeRange === '7days' ? 7 : timeRange === '30days' ? 30 : 90;
  const xAxisInterval = Math.max(0, Math.floor(effectiveDays / 7) - 1);
  const xAxisTickFormatter = (dateStr: string) => {
    const d = new Date(dateStr + 'T12:00:00');
    if (timeRange === '7days')
      return d.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric' });
    if (timeRange === 'all')
      return d.toLocaleDateString('es-ES', { month: 'short', year: '2-digit' });
    return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
  };
  if (loading) {
    return (
      <div className="chart-loading">
        <div className="spinner"></div>
        <p>Cargando datos de crecimiento...</p>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="chart-empty">
        <i className="bi bi-graph-up" style={{ fontSize: '48px', color: '#d1d5db' }}></i>
        <p>No hay datos de crecimiento disponibles</p>
      </div>
    );
  }

  const formatNumber = (num: number) => {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  };

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div style={{
          background: 'rgba(8, 12, 24, 0.95)',
          padding: '12px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '10px',
        }}>
          <p style={{ color: 'rgba(240,242,248,0.55)', marginBottom: '8px', fontSize: '12px' }}>
            {xAxisTickFormatter(data.date)}
          </p>
          <p style={{ color: '#f0f2f8', fontWeight: 700, margin: '4px 0', fontSize: '14px' }}>
            {formatNumber(data.follower_count)} seguidores
          </p>
          {data.change !== 0 && (
            <p style={{
              color: data.change > 0 ? '#22c55e' : '#ef4444',
              fontWeight: 600,
              marginTop: '6px',
              fontSize: '12px',
            }}>
              {data.change > 0 ? '+' : ''}{data.change} hoy
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
        <XAxis
          dataKey="date"
          tickFormatter={xAxisTickFormatter}
          interval={xAxisInterval}
          stroke="rgba(255,255,255,0.08)"
          tick={{ fill: 'rgba(240,242,248,0.45)', fontSize: 11 }}
        />
        <YAxis
          tickFormatter={formatNumber}
          stroke="rgba(255,255,255,0.08)"
          tick={{ fill: 'rgba(240,242,248,0.45)', fontSize: 11 }}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        <Line
          type="monotone"
          dataKey="follower_count"
          stroke="#833ab4"
          strokeWidth={2}
          name="Seguidores"
          dot={false}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default FollowerGrowthChart;
