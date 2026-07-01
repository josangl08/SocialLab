import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import CalendarView from '../components/calendar/CalendarView';
import { useAuth } from '../context/AuthContext';

// Mock routing hook
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useSearchParams: () => [new URLSearchParams()],
}));

// Mock useAuth
vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

// Mock react-big-calendar and its DnD addon to trigger events easily
vi.mock('react-big-calendar', () => {
  return {
    Calendar: (props: any) => (
      <div data-testid="mock-calendar">
        <div data-testid="events-container">
          {props.events.map((e: any) => (
            <div
              key={e.id}
              data-testid={`event-${e.id}`}
              className={props.eventPropGetter ? props.eventPropGetter(e).className : ''}
              onClick={() => props.onSelectEvent(e)}
            >
              {e.title}
            </div>
          ))}
        </div>
        <button
          data-testid="btn-trigger-drop"
          onClick={() => {
            if (props.onEventDrop) {
              props.onEventDrop({
                event: props.events[0],
                start: new Date('2030-06-28T10:00:00Z'),
              });
            }
          }}
        >
          Drop Event
        </button>
        <button
          data-testid="btn-trigger-slot"
          onClick={() => {
            if (props.onSelectSlot) {
              props.onSelectSlot({
                start: new Date('2026-06-30T15:00:00Z'),
              });
            }
          }}
        >
          Select Slot
        </button>
      </div>
    ),
    dateFnsLocalizer: vi.fn(),
  };
});

vi.mock('react-big-calendar/lib/addons/dragAndDrop', () => {
  return {
    default: (CalendarComp: any) => {
      return (props: any) => <CalendarComp {...props} />;
    },
  };
});

describe('CalendarView Component', () => {
  const mockToken = 'mock-token-123';
  const mockPosts = [
    {
      id: 1,
      user_id: 'user-123',
      content: 'Post 1',
      media_url: null,
      post_type: 'post',
      status: 'draft',
      scheduled_at: '2026-06-27T12:00:00Z',
      created_at: '2026-06-27T10:00:00Z',
      publication_date: null,
    },
  ];
  const mockProposals = [
    {
      id: 'proposal-abc',
      account_id: '123',
      week_start: '2026-06-29',
      status: 'pending_approval',
      slots: [
        {
          day: 'lunes',
          theme: 'Lunes motivacional',
          caption: '¡A por la semana!',
          post_type: 'post',
        },
      ],
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (useAuth as any).mockReturnValue({ token: mockToken, syncCompleted: false });

    // Mock global fetch
    (global.fetch as any).mockImplementation((url: string) => {
      if (url.includes('/api/posts')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockPosts),
        });
      }
      if (url.includes('/instagram/accounts')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([{ id: 123, username: 'test_account' }]),
        });
      }
      if (url.includes('/api/agent/proposals')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockProposals),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });
  });

  test('renders calendar and loads events from /api/posts and /api/agent/proposals', async () => {
    render(<CalendarView />);

    // Wait for the calendar to render and stop loading
    await waitFor(() => {
      expect(screen.getByTestId('mock-calendar')).toBeInTheDocument();
    });

    // Check that post event and proposal event are rendered
    expect(screen.getByTestId('event-1')).toBeInTheDocument();
    expect(screen.getByTestId('event-proposal-proposal-abc-0')).toBeInTheDocument();
  });

  test('proposal events render with distinct class', async () => {
    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('event-proposal-proposal-abc-0')).toBeInTheDocument();
    });

    const proposalEvent = screen.getByTestId('event-proposal-proposal-abc-0');
    expect(proposalEvent.className).toContain('event-proposal');
  });

  test('onEventDrop calls reschedule API endpoint', async () => {
    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('event-1')).toBeInTheDocument();
    });

    // Trigger onEventDrop mock trigger button
    const dropBtn = screen.getByTestId('btn-trigger-drop');
    fireEvent.click(dropBtn);

    await waitFor(() => {
      // Verify fetch was called with PUT /api/scheduler/reschedule/1
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/scheduler/reschedule/1'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ new_scheduled_time: '2030-06-28T10:00:00.000Z' }),
        })
      );
    });
  });

  test('onSelectSlot navigates to CreatePost with correct date query parameter', async () => {
    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-calendar')).toBeInTheDocument();
    });

    // Trigger onSelectSlot mock trigger button
    const slotBtn = screen.getByTestId('btn-trigger-slot');
    fireEvent.click(slotBtn);

    expect(mockNavigate).toHaveBeenCalledWith(
      '/create-post?date=2026-06-30T15:00:00.000Z'
    );
  });
});
