import React, { useState, useEffect } from 'react';
import { getFirstOfDayOfMonth } from '../../features/agent/AgentStrategyDrawer';
import type { MonthlyCampaign } from '../../features/agent/AgentStrategyDrawer';
import { useAuth } from '../../context/AuthContext';
import './MonthlyFocusBanner.css';

interface MonthlyFocusBannerProps {
  accountId: number | null;
  currentDate: Date;
}

export const MonthlyFocusBanner: React.FC<MonthlyFocusBannerProps> = ({ accountId, currentDate }) => {
  const { token } = useAuth();
  const [campaign, setCampaign] = useState<MonthlyCampaign | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token || !accountId) {
      setCampaign(null);
      return;
    }

    const monthDate = getFirstOfDayOfMonth(currentDate);
    setLoading(true);

    fetch(`http://localhost:8000/api/agent/campaign?account_id=${accountId}&month_date=${monthDate}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => {
        setCampaign(data);
      })
      .catch(() => {
        setCampaign(null);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [token, accountId, currentDate]);

  if (loading || !campaign) {
    return null;
  }

  const currentWeek = Math.min(Math.floor((currentDate.getDate() - 1) / 7) + 1, 4);
  const weeks = (['1', '2', '3', '4'] as const)
    .map(week => ({ week, text: campaign.weekly_focus[week] || '' }))
    .filter(w => w.text);

  return (
    <div className="monthly-focus-banner p-3 mb-4 rounded-3">
      <div className="d-flex align-items-center gap-3 mb-3">
        <div className="banner-badge px-2 py-1 rounded text-uppercase fw-bold">
          {campaign.strategy_mode === 'commercial_campaign' ? '💼 Comercial' : '✨ Personal'}
        </div>
        <div>
          <h6 className="mb-0 fw-bold text-white banner-title">{campaign.title}</h6>
          <p className="mb-0 text-white-50 small banner-description">{campaign.description}</p>
        </div>
      </div>
      {weeks.length > 0 && (
        <div className="d-flex gap-2 flex-wrap">
          {weeks.map(w => (
            <div
              key={w.week}
              className={`banner-week-chip px-3 py-2 rounded${w.week === String(currentWeek) ? ' active' : ''}`}
            >
              <div className="focus-label text-uppercase fw-bold text-white-50">Foco Semana {w.week}</div>
              <div className="focus-text fw-semibold text-white">{w.text}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
