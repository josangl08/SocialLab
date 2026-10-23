import type { MonthlyCampaign } from '../types';

export const getFirstOfDayOfMonth = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  return `${y}-${m}-01`;
};

export const emptyCampaign = (accountId: number, month_date: string): MonthlyCampaign => ({
  account_id: accountId,
  month_date,
  strategy_mode: 'commercial_campaign',
  title: '',
  description: '',
  milestones: [],
  weekly_focus: { '1': '', '2': '', '3': '', '4': '' },
});

/** Une una campaña del API con los valores por defecto (semanas y hitos vacíos). */
export const withCampaignDefaults = (
  accountId: number,
  month_date: string,
  data: Partial<MonthlyCampaign> | null,
): MonthlyCampaign => {
  const base = emptyCampaign(accountId, month_date);
  if (!data) return base;
  return {
    ...base,
    ...data,
    weekly_focus: { ...base.weekly_focus, ...data.weekly_focus },
    milestones: data.milestones ?? base.milestones,
  };
};
