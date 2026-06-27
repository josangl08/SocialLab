import React from 'react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer
} from 'recharts';

interface ContentRadarChartProps {
  post: {
    likes?: number;
    comments?: number;
    saved?: number;
    saves?: number;
    reach?: number;
    impressions?: number;
    views?: number;
    shares?: number;
  } | null;
}

export const ContentRadarChart: React.FC<ContentRadarChartProps> = ({ post }) => {
  if (!post) {
    return (
      <div className="chart-empty d-flex align-items-center justify-content-center" style={{ height: '260px', color: '#6b7280' }}>
        <span>No hay datos para mostrar</span>
      </div>
    );
  }

  // Extract values and handle alternative names
  const savedVal = post.saved ?? post.saves ?? 0;
  const commentsVal = post.comments ?? 0;
  const viewsVal = post.views ?? post.impressions ?? 0;
  const likesVal = post.likes ?? 0;
  const sharesVal = post.shares ?? Math.round(likesVal * 0.1); // Fallback proxy

  // Normalize scores from 0 to 100 for the radar rendering
  const data = [
    { subject: 'Retención', value: Math.min(100, savedVal * 5), fullMark: 100 },
    { subject: 'Viralidad', value: Math.min(100, sharesVal * 10), fullMark: 100 },
    { subject: 'Conversación', value: Math.min(100, commentsVal * 4), fullMark: 100 },
    { subject: 'Exposición', value: Math.min(100, Math.round(viewsVal / 20)), fullMark: 100 },
  ];

  return (
    <div className="an-radar-chart-container d-flex justify-content-center align-items-center" style={{ width: '260px', height: '260px', margin: '0 auto' }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
          <PolarGrid stroke="rgba(255, 255, 255, 0.05)" />
          <PolarAngleAxis 
            dataKey="subject" 
            tick={{ fill: '#9ca3af', fontSize: 10 }}
          />
          <PolarRadiusAxis 
            angle={30} 
            domain={[0, 100]} 
            tick={false} 
            axisLine={false} 
          />
          <Radar
            name="Métricas"
            dataKey="value"
            stroke="#c084fc"
            fill="rgba(192, 132, 252, 0.15)"
            fillOpacity={0.6}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default ContentRadarChart;
