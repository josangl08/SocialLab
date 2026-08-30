import { describe, test, expect } from 'vitest';
import { outputMatches } from '../HermesMind';
import type { DecisionSummary } from '../shared/types';

const base: DecisionSummary = {
  id: 1,
  decision_type: 'supabase_create_post',
  confidence_score: 0.8,
  applied_rule_labels: [],
  rationale: '',
  status: 'active',
  created_at: '2026-08-24T12:00:00Z',
};

describe('outputMatches', () => {
  test('a decision with a post lands only in out:post', () => {
    const d = { ...base, related_post_id: 44182 };
    expect(outputMatches(d, 'out:post')).toBe(true);
    expect(outputMatches(d, 'out:proposal')).toBe(false);
    expect(outputMatches(d, 'out:suggestion')).toBe(false);
  });

  test('post_id wins over proposal_id (same priority as the Río counter)', () => {
    const d = { ...base, related_post_id: 44182, related_proposal_id: 'p1' };
    expect(outputMatches(d, 'out:post')).toBe(true);
    expect(outputMatches(d, 'out:proposal')).toBe(false);
  });

  test('no post and no proposal → suggestion', () => {
    expect(outputMatches(base, 'out:suggestion')).toBe(true);
    expect(outputMatches(base, 'out:post')).toBe(false);
  });
});
