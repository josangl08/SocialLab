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
    {
      id: 2,
      user_id: 'user-123',
      content: 'AI proposal post',
      media_url: null,
      post_type: 'post',
      status: 'draft',
      scheduled_at: '2026-06-29T12:00:00Z',
      created_at: '2026-06-27T10:00:00Z',
      publication_date: null,
      is_ai_generated: true,
    },
    {
      id: 3,
      user_id: 'user-123',
      content: 'AI post already approved',
      media_url: null,
      post_type: 'post',
      status: 'scheduled',
      scheduled_at: '2026-06-30T12:00:00Z',
      created_at: '2026-06-27T10:00:00Z',
      publication_date: null,
      is_ai_generated: true,
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
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });
  });

  test('renders calendar and loads events from /api/posts', async () => {
    render(<CalendarView />);

    // Wait for the calendar to render and stop loading
    await waitFor(() => {
      expect(screen.getByTestId('mock-calendar')).toBeInTheDocument();
    });

    // Check that both the regular post and the AI-generated draft post are rendered
    expect(screen.getByTestId('event-1')).toBeInTheDocument();
    expect(screen.getByTestId('event-2')).toBeInTheDocument();
  });

  test('AI-generated draft posts render with distinct proposal class', async () => {
    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('event-2')).toBeInTheDocument();
    });

    const proposalEvent = screen.getByTestId('event-2');
    expect(proposalEvent.className).toContain('event-proposal');
  });

  test('AI posts keep an AI marker class once approved (scheduled)', async () => {
    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('event-3')).toBeInTheDocument();
    });

    const scheduledAiEvent = screen.getByTestId('event-3');
    expect(scheduledAiEvent.className).toContain('event-status-scheduled');
    expect(scheduledAiEvent.className).toContain('event-ai-scheduled');
    expect(scheduledAiEvent.className).not.toContain('event-proposal');
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

  test('onSelectSlot navigates to Content Studio with correct date query parameter', async () => {
    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-calendar')).toBeInTheDocument();
    });

    // Trigger onSelectSlot mock trigger button
    const slotBtn = screen.getByTestId('btn-trigger-slot');
    fireEvent.click(slotBtn);

    expect(mockNavigate).toHaveBeenCalledWith(
      `/generate?date=${encodeURIComponent('2026-06-30T15:00:00.000Z')}`
    );
  });
});
