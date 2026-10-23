import { apiClient } from './client';
import type {
  AgentConfigPatch,
  AgentStrategyConfig,
  AgentSuggestion,
  StrategyDiagnostics,
  StrategyWizardAnswers,
} from '../types';

export const SUGGESTION_TYPES = ['suggest_schedule_change', 'suggest_mix_change', 'suggest_pillars_change'];

export const strategyApi = {
  getConfig: (accountId: number) =>
    apiClient.get<AgentStrategyConfig>(`/api/agent/config/${accountId}`),

  patchConfig: (accountId: number, patch: AgentConfigPatch) =>
    apiClient.patch<AgentStrategyConfig>(`/api/agent/config/${accountId}`, patch),

  getDiagnostics: (accountId: number) =>
    apiClient.get<StrategyDiagnostics>(`/api/agent/strategy/${accountId}/diagnostics`),

  generateStrategy: (accountId: number, answers: StrategyWizardAnswers) =>
    apiClient.post<Partial<AgentStrategyConfig>>('/api/agent/generate-strategy', { ...answers, account_id: accountId }),

  listPendingSuggestions: async (accountId: number): Promise<AgentSuggestion[]> => {
    const res = await apiClient.get<{ data: AgentSuggestion[] }>(
      `/api/agent/decisions?account_id=${accountId}&status=suggested&per_page=50`
    );
    return (res.data ?? []).filter(d => SUGGESTION_TYPES.includes(d.decision_type));
  },

  acceptSuggestion: (decisionId: number) =>
    apiClient.post<{ accepted: boolean; config_column: keyof AgentStrategyConfig; applied_value: unknown }>(
      `/api/agent/decisions/${decisionId}/accept-suggestion`, {}
    ),

  dismissSuggestion: (decisionId: number) =>
    apiClient.post<{ dismissed: boolean }>(`/api/agent/decisions/${decisionId}/dismiss-suggestion`, {}),
};
