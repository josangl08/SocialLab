import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';

interface DemographicsData {
  'audience_gender_age': Record<string, number>;
}

interface DemographicsChartProps {
  data: DemographicsData | null;
  loading?: boolean;
  emptyMessage?: string;
}

export const DemographicsChart: React.FC<DemographicsChartProps> = ({
  data,
  loading = false,
  emptyMessage
}) => {
  if (loading) {
    return (
      <div className="chart-loading">
        <div className="spinner"></div>
        <p>Cargando datos demográficos...</p>
      </div>
    );
  }

  if (!data || !data.audience_gender_age) {
    return (
      <div className="chart-empty d-flex flex-column align-items-center justify-content-center py-4">
        <i className="bi bi-people" style={{ fontSize: '2.5rem', marginBottom: '8px', color: 'rgba(255,255,255,0.12)' }}></i>
        <p style={{ margin: 0, fontSize: '0.85rem', textAlign: 'center', color: 'rgba(240,242,248,0.45)' }}>
          {emptyMessage ?? 'No hay datos demográficos disponibles'}
        </p>
      </div>
    );
  }

  // Procesar datos de audience_gender_age
  // Formato: { "F.18-24": 420, "M.18-24": 350, "U.18-24": 15, ... }
  const processedData = () => {
    const genderAgeData = data.audience_gender_age;
    const genderMap: Record<string, Record<string, number>> = {};

    // Extraer rangos de edad únicos
    Object.keys(genderAgeData).forEach(key => {
      const [gender, age] = key.split('.');
      if (!genderMap[age]) {
        genderMap[age] = { F: 0, M: 0, U: 0 };
      }
      genderMap[age][gender] = genderAgeData[key];
    });

    // Orden ascendente de rangos de edad (de mayor a menor en el eje Y)
    const ageOrder = ['65+', '55-64', '45-54', '35-44', '25-34', '18-24', '13-17'];

    // Convertir a formato para Recharts con orden correcto
    return ageOrder
      .filter(age => genderMap[age]) // Solo incluir rangos que tengan datos
      .map(age => ({
        age,
        Mujeres: genderMap[age].F || 0,
        Hombres: genderMap[age].M || 0,
        Otro: genderMap[age].U || 0
      }));
  };

  const chartData = processedData();

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const total = payload.reduce((sum: number, item: any) => sum + item.value, 0);
      return (
        <div style={{
          background: 'rgba(8, 12, 24, 0.95)',
          padding: '12px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '10px',
        }}>
          <p style={{ color: '#f0f2f8', fontWeight: 700, marginBottom: '8px', fontSize: '13px' }}>
            {label} años
          </p>
          {payload.map((item: any, index: number) => (
            <p key={index} style={{ color: item.color, margin: '4px 0', fontSize: '12px' }}>
              {item.name}: {item.value} ({((item.value / total) * 100).toFixed(1)}%)
            </p>
          ))}
          <p style={{ color: 'rgba(240,242,248,0.45)', marginTop: '8px', paddingTop: '8px', borderTop: '1px solid rgba(255,255,255,0.07)', fontSize: '12px' }}>
            Total: {total}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="demographics-chart">
      <ResponsiveContainer width="100%" height={340}>
        <BarChart data={chartData} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis type="number" stroke="rgba(255,255,255,0.08)" tick={{ fill: 'rgba(240,242,248,0.45)', fontSize: 11 }} />
          <YAxis
            type="category"
            dataKey="age"
            stroke="rgba(255,255,255,0.08)"
            tick={{ fill: 'rgba(240,242,248,0.45)', fontSize: 11 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          <Bar dataKey="Mujeres" stackId="a" fill="#ec4899" radius={[0, 4, 4, 0]} />
          <Bar dataKey="Hombres" stackId="a" fill="#3b82f6" radius={[0, 4, 4, 0]} />
          <Bar dataKey="Otro" stackId="a" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default DemographicsChart;
