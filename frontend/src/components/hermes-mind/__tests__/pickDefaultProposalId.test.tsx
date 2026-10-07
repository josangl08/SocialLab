import { describe, test, expect } from 'vitest';
import { pickDefaultProposalId } from '../HermesMind';
import type { ContentProposal } from '../../../types';

const mk = (id: string, status: ContentProposal['status']): ContentProposal => ({
  id,
  account_id: '7',
  week_start: '2026-09-07',
  slots: [],
  status,
});

describe('pickDefaultProposalId', () => {
  test('picks the newest non-rejected proposal (list is newest-first)', () => {
    const proposals = [mk('c', 'rejected'), mk('b', 'pending_approval'), mk('a', 'approved')];
    expect(pickDefaultProposalId(proposals)).toBe('b');
  });

  test('falls back to an approved proposal when none are pending', () => {
    const proposals = [mk('c', 'rejected'), mk('a', 'approved')];
    expect(pickDefaultProposalId(proposals)).toBe('a');
  });

  test('returns "" (Toda la cuenta) when every proposal is rejected', () => {
    expect(pickDefaultProposalId([mk('c', 'rejected'), mk('d', 'rejected')])).toBe('');
  });

  test('returns "" for an empty list', () => {
    expect(pickDefaultProposalId([])).toBe('');
  });
});
