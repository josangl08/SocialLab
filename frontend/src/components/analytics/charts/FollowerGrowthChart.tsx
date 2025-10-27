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
}

export const FollowerGrowthChart: React.FC<FollowerGrowthChartProps> = ({
  data,
  loading = false
}) => {
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

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('es-ES', {
      day: 'numeric',
      month: 'short'
    });
  };

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
          background: 'rgba(31, 41, 55, 0.95)',
          padding: '12px',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '8px',
          boxShadow: '0 4px 6px rgba(0, 0, 0, 0.3)'
        }}>
          <p style={{ color: '#d1d5db', marginBottom: '8px', fontSize: '13px' }}>
            {formatDate(data.date)}
          </p>
          <p style={{ color: '#fff', fontWeight: 'bold', margin: '4px 0', fontSize: '14px' }}>
            {formatNumber(data.follower_count)} seguidores
          </p>
          {data.change !== 0 && (
            <p style={{
              color: data.change > 0 ? '#10b981' : '#ef4444',
              fontWeight: 'bold',
              marginTop: '8px',
              fontSize: '13px'
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
    <div className="follower-growth-chart">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            stroke="#6b7280"
            style={{ fontSize: '12px' }}
          />
          <YAxis
            tickFormatter={formatNumber}
            stroke="#6b7280"
            style={{ fontSize: '12px' }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          <Line
            type="monotone"
            dataKey="follower_count"
            stroke="#8b5cf6"
            strokeWidth={2}
            name="Seguidores"
            dot={{ fill: '#8b5cf6', r: 4 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default FollowerGrowthChart;
