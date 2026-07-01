import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import WeeklyProposalPanel from '../components/planner/WeeklyProposalPanel';
import { useAuth } from '../context/AuthContext';

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

describe('WeeklyProposalPanel Component', () => {
  const mockToken = 'mock-token-123';
  const mockOnProposalAction = vi.fn();

  const mockProposals = [
    {
      id: 'proposal-1',
      account_id: '123',
      week_start: '2026-06-29',
      status: 'pending_approval',
      slots: [
        {
          day: 'Monday',
          theme: 'Monday motivation',
          caption: "Let's go!",
          post_type: 'post',
          post_id: 1001,
          image_id: 'file-abc',
        },
      ],
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (useAuth as any).mockReturnValue({ token: mockToken });

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/agent/proposals/proposal-1/slots/0/regenerate')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ caption: 'Regenerated caption!' }),
        });
      }
      if (url.includes('/api/agent/proposals?account_id=')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockProposals),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }) as any;
  });

  // Helper: wait for proposals to load then click the Monday day box to open detail panel
  async function openMondayPanel() {
    await waitFor(() => expect(screen.queryByText(/Loading proposals/i)).not.toBeInTheDocument());
    const lunLabel = screen.getByText('Mon');
    const dayBox = lunLabel.closest('div[class*="wpp-day-box"]') as HTMLElement;
    fireEvent.click(dayBox);
  }

  test('renders loading state first, then 7-box week row with day labels and badge', async () => {
    render(
      <WeeklyProposalPanel
        accountId={123}
        refreshSignal={1}
        onProposalAction={mockOnProposalAction}
      />
    );

    expect(screen.getByText(/Loading proposals/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText(/Loading proposals/i)).not.toBeInTheDocument();
    });

    expect(screen.getByText('Pending AI Proposals')).toBeInTheDocument();
    expect(screen.getByText('Week of 2026-06-29')).toBeInTheDocument();

    // All 7 day abbreviations should be present
    expect(screen.getByText('Mon')).toBeInTheDocument();
    expect(screen.getByText('Tue')).toBeInTheDocument();
    expect(screen.getByText('Wed')).toBeInTheDocument();

    // Post type badge appears directly in the day box
    expect(screen.getByText('Post')).toBeInTheDocument();
  });

  test('approve proposal action triggers API call and onProposalAction callback', async () => {
    render(
      <WeeklyProposalPanel
        accountId={123}
        refreshSignal={1}
        onProposalAction={mockOnProposalAction}
      />
    );

    await waitFor(() => expect(screen.getByText('Approve all')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Approve all'));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/agent/proposals/proposal-1/approve'),
        expect.objectContaining({ method: 'POST' })
      );
      expect(mockOnProposalAction).toHaveBeenCalled();
    });
  });

  test('reject proposal action triggers API call and onProposalAction callback', async () => {
    render(
      <WeeklyProposalPanel
        accountId={123}
        refreshSignal={1}
        onProposalAction={mockOnProposalAction}
      />
    );

    await waitFor(() => expect(screen.getByText('Reject')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Reject'));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/agent/proposals/proposal-1/reject'),
        expect.objectContaining({ method: 'POST' })
      );
      expect(mockOnProposalAction).toHaveBeenCalled();
    });
  });

  test('clicking a day box expands detail panel; regenerate updates caption', async () => {
    render(
      <WeeklyProposalPanel
        accountId={123}
        refreshSignal={1}
        onProposalAction={mockOnProposalAction}
      />
    );

    await openMondayPanel();

    // Detail panel is now visible
    expect(screen.getByText("Let's go!")).toBeInTheDocument();
    expect(screen.getByText('Regenerate')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Regenerate'));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/agent/proposals/proposal-1/slots/0/regenerate'),
        expect.objectContaining({ method: 'POST' })
      );
      expect(screen.getByText('Regenerated caption!')).toBeInTheDocument();
    });
  });

  test('clicking a day box expands detail panel; omit slot triggers API call', async () => {
    render(
      <WeeklyProposalPanel
        accountId={123}
        refreshSignal={1}
        onProposalAction={mockOnProposalAction}
      />
    );

    await openMondayPanel();

    expect(screen.getByText('Skip')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Skip'));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/agent/proposals/proposal-1/slots/0/skip'),
        expect.objectContaining({ method: 'POST' })
      );
    });
  });

  test('does not fetch anything when accountId is null', () => {
    render(
      <WeeklyProposalPanel
        accountId={null}
        refreshSignal={0}
        onProposalAction={mockOnProposalAction}
      />
    );
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('calls onProposalsFound when proposal count increases during polling', async () => {
    let callCount = 0;
    global.fetch = vi.fn().mockImplementation(() => {
      callCount++;
      const data = callCount === 1 ? [] : mockProposals;
      return Promise.resolve({ ok: true, json: () => Promise.resolve(data) });
    }) as any;

    const onProposalsFound = vi.fn();
    const { rerender } = render(
      <WeeklyProposalPanel
        accountId={123}
        refreshSignal={0}
        onProposalAction={vi.fn()}
        onProposalsFound={onProposalsFound}
      />
    );

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    expect(onProposalsFound).not.toHaveBeenCalled();

    rerender(
      <WeeklyProposalPanel
        accountId={123}
        refreshSignal={1}
        onProposalAction={vi.fn()}
        onProposalsFound={onProposalsFound}
      />
    );

    await waitFor(() => expect(onProposalsFound).toHaveBeenCalledTimes(1));
  });

  test('clicking a day box expands detail panel; change type triggers API call', async () => {
    render(
      <WeeklyProposalPanel
        accountId={123}
        refreshSignal={1}
        onProposalAction={mockOnProposalAction}
      />
    );

    await openMondayPanel();

    expect(screen.getByText('Type')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Type'));

    // Dropdown options appear
    expect(screen.getByText('Reel')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Reel'));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/agent/proposals/proposal-1/slots/0/type'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ post_type: 'reel' }),
        })
      );
    });
  });
});
