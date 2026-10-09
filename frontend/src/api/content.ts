import { apiClient } from './client';
import type {
  LintRequest,
  QualityReport,
  HumanizeRequest,
  HumanizeResponse,
  HookScoreRequest,
  HookScoreResponse,
  HookFormula,
  BeatsRequest,
  BeatsResponse,
  StrategyMode,
} from '../types';

export const contentApi = {
  lintCaption: (
    data: LintRequest,
    options?: { signal?: AbortSignal }
  ): Promise<QualityReport> => {
    return apiClient.post<QualityReport>('/content/lint', data, options);
  },

  humanizeText: (
    data: HumanizeRequest,
    options?: { signal?: AbortSignal }
  ): Promise<HumanizeResponse> => {
    return apiClient.post<HumanizeResponse>('/content/humanize', data, options);
  },

  scoreHook: (
    data: HookScoreRequest,
    options?: { signal?: AbortSignal }
  ): Promise<HookScoreResponse> => {
    return apiClient.post<HookScoreResponse>('/content/score-hook', data, options);
  },

  timeBeats: (
    data: BeatsRequest,
    options?: { signal?: AbortSignal }
  ): Promise<BeatsResponse> => {
    return apiClient.post<BeatsResponse>('/content/beats', data, options);
  },

  getHookFormulas: (
    strategyMode?: StrategyMode,
    options?: { signal?: AbortSignal }
  ): Promise<HookFormula[]> => {
    const url = strategyMode
      ? `/content/hook-formulas?strategy_mode=${encodeURIComponent(strategyMode)}`
      : '/content/hook-formulas';
    return apiClient.get<HookFormula[]>(url, options);
  },
};
