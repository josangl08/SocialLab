import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
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
              <props.components.event event={e} />
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
        <button data-testid="btn-view-week" onClick={() => props.onView('week')}>Week</button>
        <button
          data-testid="btn-drop-mosaic-future"
          onClick={() => props.onDropFromOutside({ start: new Date(2030, 6, 2), end: new Date(2030, 6, 3), allDay: false })}
        >
          Drop on future day
        </button>
        <button
          data-testid="btn-drop-mosaic-past"
          onClick={() => props.onDropFromOutside({ start: new Date(2020, 0, 1), end: new Date(2020, 0, 2), allDay: false })}
        >
          Drop on past day
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
    {
      id: 4,
      user_id: 'user-123',
      content: 'Second post on the same day as post 1',
      media_url: null,
      drive_file_id: 'file-4',
      post_type: 'post',
      status: 'published',
      scheduled_at: '2026-06-27T13:00:00Z',
      created_at: '2026-06-27T10:00:00Z',
      publication_date: null,
    },
  ];
  const dayOf = (iso: string) => {
    const d = new Date(iso);
    return `day-${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
  };

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

  test('month view groups the posts of each day into one mosaic ordered by time', async () => {
    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-calendar')).toBeInTheDocument();
    });

    expect(screen.getAllByTestId('day-mosaic')).toHaveLength(3);
    const day = screen.getByTestId(`event-${dayOf('2026-06-27T12:00:00Z')}`);
    const tiles = within(day).getAllByTestId(/^mosaic-tile-/);
    expect(tiles.map(t => t.dataset.testid)).toEqual(['mosaic-tile-1', 'mosaic-tile-4']);
    expect(within(day).getByTestId('day-mosaic')).toHaveClass('sl-mosaic--2');
  });

  test('mosaic tiles carry the status classes of their posts', async () => {
    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('mosaic-tile-2')).toBeInTheDocument();
    });

    expect(screen.getByTestId('mosaic-tile-1').className).toContain('event-status-draft');
    expect(screen.getByTestId('mosaic-tile-4').className).toContain('event-status-published');
    // AI draft → proposal style
    expect(screen.getByTestId('mosaic-tile-2').className).toContain('event-proposal');
    // AI post once approved keeps its status colour and an AI marker
    const scheduledAi = screen.getByTestId('mosaic-tile-3');
    expect(scheduledAi.className).toContain('event-status-scheduled');
    expect(scheduledAi.className).toContain('event-ai-scheduled');
    expect(scheduledAi.className).not.toContain('event-proposal');
  });

  test('week view shows one event per post with its thumbnail and text', async () => {
    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-calendar')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('btn-view-week'));

    expect(screen.queryByTestId('day-mosaic')).not.toBeInTheDocument();
    expect(screen.getByTestId('event-2').className).toContain('event-proposal');
    const withImage = screen.getByTestId('event-4');
    expect(withImage.querySelector('img')?.getAttribute('src')).toContain('/api/posts/4/thumbnail?size=160');
    expect(withImage).toHaveTextContent('Second post on the same day');
  });

  test('onEventDrop calls reschedule API endpoint (week view)', async () => {
    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-calendar')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('btn-view-week'));

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

  test('dragging a mosaic tile to another day reschedules it keeping its time', async () => {
    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('mosaic-tile-4')).toBeInTheDocument();
    });
    fireEvent.dragStart(screen.getByTestId('mosaic-tile-4'), { dataTransfer: { setData: vi.fn() } });
    fireEvent.click(screen.getByTestId('btn-drop-mosaic-future'));

    const expected = new Date('2026-06-27T13:00:00Z');
    expected.setFullYear(2030, 6, 2);
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/scheduler/reschedule/4'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ new_scheduled_time: expected.toISOString() }),
        })
      );
    });
    // Only that post moved: post 1 stays alone on its day
    const oldDay = screen.getByTestId(`event-${dayOf('2026-06-27T12:00:00Z')}`);
    expect(within(oldDay).queryByTestId('mosaic-tile-4')).not.toBeInTheDocument();
    expect(within(oldDay).getByTestId('mosaic-tile-1')).toBeInTheDocument();
  });

  test('dropping a mosaic tile on a past day is rejected', async () => {
    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('mosaic-tile-4')).toBeInTheDocument();
    });
    fireEvent.dragStart(screen.getByTestId('mosaic-tile-4'), { dataTransfer: { setData: vi.fn() } });
    fireEvent.click(screen.getByTestId('btn-drop-mosaic-past'));

    expect(screen.getByText('Cannot schedule posts in the past.')).toBeInTheDocument();
    expect(globalThis.fetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/api/scheduler/reschedule/'),
      expect.anything()
    );
  });

  test('a failed mosaic drop reverts the post to its original day', async () => {
    (globalThis.fetch as any).mockImplementation((url: string) => {
      if (url.includes('/api/scheduler/reschedule/')) {
        return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ detail: 'boom' }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(url.includes('/api/posts') ? mockPosts : {}) });
    });
    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('mosaic-tile-4')).toBeInTheDocument();
    });
    fireEvent.dragStart(screen.getByTestId('mosaic-tile-4'), { dataTransfer: { setData: vi.fn() } });
    fireEvent.click(screen.getByTestId('btn-drop-mosaic-future'));

    await waitFor(() => {
      expect(screen.getByText('Could not reschedule the post.')).toBeInTheDocument();
    });
    const oldDay = screen.getByTestId(`event-${dayOf('2026-06-27T12:00:00Z')}`);
    expect(within(oldDay).getByTestId('mosaic-tile-4')).toBeInTheDocument();
  });

  test('clicking a tile opens the viewer; "Ver detalles" opens the post modal', async () => {
    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('mosaic-tile-4')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('mosaic-tile-4'));

    const viewer = screen.getByTestId('media-lightbox');
    expect(within(viewer).getByText('2 / 2')).toBeInTheDocument();
    fireEvent.click(within(viewer).getByText('Ver detalles'));

    expect(screen.queryByTestId('media-lightbox')).not.toBeInTheDocument();
    expect(document.querySelector('.pdm-backdrop')).toBeInTheDocument();
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

  test('con timezone Europe/Madrid, el post 2026-10-14T18:00Z cae el miercoles 14 a las 20:00', async () => {
    // Post 53946 programado a las 18:00 UTC
    (globalThis.fetch as any).mockImplementation((url: string) => {
      if (url.includes('/api/posts')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([
            {
              id: 53946,
              user_id: 'user-1',
              content: 'Post con timezone Madrid',
              media_url: null,
              post_type: 'post',
              status: 'scheduled',
              scheduled_at: '2026-10-14T18:00:00Z',
              created_at: '2026-10-01T10:00:00Z',
              instagram_account_id: 7,
            },
          ]),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<CalendarView timezone="Europe/Madrid" secondaryTimezone="Asia/Kuching" />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-calendar')).toBeInTheDocument();
    });

    // Cambiar a vista de semana para ver el evento
    fireEvent.click(screen.getByTestId('btn-view-week'));

    await waitFor(() => {
      expect(screen.getByTestId('event-53946')).toBeInTheDocument();
    });
    // Hora secundaria junto al evento: jueves 02:00 en Kuching
    expect(screen.getByTestId('event-53946')).toHaveTextContent('02:00 Kuching');
  });

  test('vista de mes marca la miniatura cuando el día cambia en la zona secundaria', async () => {
    (globalThis.fetch as any).mockImplementation((url: string) => Promise.resolve({
      ok: true,
      json: () => Promise.resolve(url.includes('/api/posts') ? [{
        id: 53946, user_id: 'user-1', content: 'Post', media_url: null, post_type: 'post', status: 'scheduled',
        scheduled_at: '2026-10-14T18:00:00Z', created_at: '2026-10-01T10:00:00Z', instagram_account_id: 7,
      }] : {}),
    }));

    render(<CalendarView timezone="Europe/Madrid" secondaryTimezone="Asia/Kuching" />);

    await waitFor(() => {
      expect(screen.getByTestId('mosaic-tz-mark-53946')).toHaveAttribute('title', 'Jue 15 · 02:00 Kuching');
    });
  });

  test('con timezone, soltar un evento convierte la hora de pared de la zona a UTC', async () => {
    render(<CalendarView timezone="Europe/Madrid" />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-calendar')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('btn-view-week'));
    fireEvent.click(screen.getByTestId('btn-trigger-drop'));

    // El mock suelta en una Date cuyo reloj de pared se lee en Madrid (CEST, UTC+2)
    const dropped = new Date('2030-06-28T10:00:00Z');
    const expected = new Date(Date.UTC(
      dropped.getFullYear(), dropped.getMonth(), dropped.getDate(), dropped.getHours() - 2, dropped.getMinutes()
    )).toISOString();
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/scheduler/reschedule/1'),
        expect.objectContaining({ body: JSON.stringify({ new_scheduled_time: expected }) })
      );
    });
  });

  test('sin timezone principal usa la zona del navegador', async () => {
    (globalThis.fetch as any).mockImplementation((url: string) => {
      if (url.includes('/api/posts')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([
            {
              id: 53947,
              user_id: 'user-1',
              content: 'Post fallback navegador',
              media_url: null,
              post_type: 'post',
              status: 'scheduled',
              scheduled_at: '2026-10-14T18:00:00Z',
              created_at: '2026-10-01T10:00:00Z',
            },
          ]),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(<CalendarView />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-calendar')).toBeInTheDocument();
    });
  });
});
