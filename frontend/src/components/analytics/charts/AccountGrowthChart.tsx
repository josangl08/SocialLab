import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import './AccountGrowthChart.css';

export interface AccountGrowthPoint {
  date: string;
  follows: number;
  unfollows: number;
  net: number;
}

export interface AccountGrowth {
  series: AccountGrowthPoint[];
  follows: number;
  unfollows: number;
  net: number;
}

interface AccountGrowthChartProps {
  growth: AccountGrowth | null | undefined;
}

const formatNet = (net: number) => (net > 0 ? `+${net}` : String(net));

/** Altas vs bajas de seguidores por día y neto del periodo (AD-9). */
export const AccountGrowthChart: React.FC<AccountGrowthChartProps> = ({ growth }) => {
  if (!growth || growth.series.length === 0) {
    return (
      <p className="account-growth-empty">
        Sin datos de altas y bajas todavía — se registran en cada sincronización.
      </p>
    );
  }

  return (
    <div>
      <div className="account-growth-totals">
        <span>Altas <strong className="account-growth-follows">{growth.follows}</strong></span>
        <span>Bajas <strong className="account-growth-unfollows">{growth.unfollows}</strong></span>
        <span>Neto <strong>{formatNet(growth.net)}</strong></span>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={growth.series}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="date" stroke="rgba(255,255,255,0.08)" tick={{ fill: 'rgba(240,242,248,0.45)', fontSize: 11 }} />
          <YAxis stroke="rgba(255,255,255,0.08)" tick={{ fill: 'rgba(240,242,248,0.45)', fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(8, 12, 24, 0.95)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '10px',
              color: '#f0f2f8',
            }}
          />
          <Legend />
          <Bar dataKey="follows" name="Altas" fill="#6ee7b7" radius={[4, 4, 0, 0]} />
          <Bar dataKey="unfollows" name="Bajas" fill="#fd1d1d" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default AccountGrowthChart;
