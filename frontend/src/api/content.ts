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
  ReelRequest,
  ReelOut,
  CarouselRequest,
  CarouselOut,
  StoryRequest,
  StoryOut,
  RepurposeRequest,
  RepurposeOut,
  ProfileAuditResponse,
  SwipeFileResponse,
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

  generateReel: (
    data: ReelRequest,
    options?: { signal?: AbortSignal }
  ): Promise<ReelOut> => {
    return apiClient.post<ReelOut>('/content/formats/reel', data, options);
  },

  generateCarousel: (
    data: CarouselRequest,
    options?: { signal?: AbortSignal }
  ): Promise<CarouselOut> => {
    return apiClient.post<CarouselOut>('/content/formats/carousel', data, options);
  },

  generateStory: (
    data: StoryRequest,
    options?: { signal?: AbortSignal }
  ): Promise<StoryOut> => {
    return apiClient.post<StoryOut>('/content/formats/story', data, options);
  },

  generateRepurpose: (
    data: RepurposeRequest,
    options?: { signal?: AbortSignal }
  ): Promise<RepurposeOut> => {
    return apiClient.post<RepurposeOut>('/content/formats/repurpose', data, options);
  },

  auditProfile: (
    data: { account_id: number },
    options?: { signal?: AbortSignal }
  ): Promise<ProfileAuditResponse> => {
    return apiClient.post<ProfileAuditResponse>('/content/audit-profile', data, options);
  },

  getSwipeFile: (
    accountId: number,
    options?: { signal?: AbortSignal }
  ): Promise<SwipeFileResponse> => {
    return apiClient.get<SwipeFileResponse>(`/content/swipe-file/${accountId}`, options);
  },
};
