import React from 'react';
import './KPICard.css';

interface KPICardProps {
  title: string;
  value: string | number;
  change?: string;        // "+12.5%" o "-5.2%"
  trend?: 'up' | 'down' | 'neutral';
  icon: string;           // Bootstrap icon class (sin 'bi-')
  color?: 'primary' | 'success' | 'warning' | 'info' | 'purple' | 'danger';
  comparison?: {
    value: string | number;
    label: string;
  };
  loading?: boolean;
}

export const KPICard: React.FC<KPICardProps> = ({
  title,
  value,
  change,
  trend = 'neutral',
  icon,
  color = 'primary',
  comparison,
  loading = false
}) => {
  const getTrendColor = () => {
    if (trend === 'up') return '#10b981';      // green-500
    if (trend === 'down') return '#ef4444';    // red-500
    return '#6b7280';                          // gray-500
  };

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
      <div className="kpi-icon">
        <i className={`bi bi-${icon}`}></i>
      </div>
      <div className="kpi-content">
        <h3 className="kpi-title">{title}</h3>
        <div className="kpi-value">{value}</div>
        {change && (
          <div className="kpi-change" style={{ color: getTrendColor() }}>
            <i className={`bi bi-arrow-${trend === 'up' ? 'up' : trend === 'down' ? 'down' : 'right'}`}></i>
            <span>{change}</span>
          </div>
        )}
        {comparison && (
          <div className="kpi-comparison">
            <span className="comparison-label">{comparison.label}:</span>
            <span className="comparison-value">{comparison.value}</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default KPICard;
