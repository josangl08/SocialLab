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

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
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
      expect(globalThis.fetch).toHaveBeenCalledWith(
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
      expect(globalThis.fetch).toHaveBeenCalledWith(
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
      expect(globalThis.fetch).toHaveBeenCalledWith(
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
      expect(globalThis.fetch).toHaveBeenCalledWith(
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
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  test('calls onProposalsFound when proposal count increases during polling', async () => {
    let callCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(() => {
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

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(1));
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
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/agent/proposals/proposal-1/slots/0/type'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ post_type: 'reel' }),
        })
      );
    });
  });

  test('renders badge with matrix_role and format [Rol · Formato]', async () => {
    const proposalsWithRole = [
      {
        id: 'proposal-role',
        account_id: '123',
        week_start: '2026-06-29',
        status: 'pending_approval',
        slots: [
          {
            day: 'Monday',
            theme: 'Proof of work',
            caption: 'Resultados reales',
            post_type: 'reel',
            matrix_role: 'proof',
            post_id: 1001,
            image_id: 'file-abc',
          },
          {
            day: 'Tuesday',
            theme: 'Educational carousel',
            caption: 'Paso a paso',
            post_type: 'carousel',
            matrix_role: 'teach',
            post_id: 1002,
            image_id: 'file-def',
          },
        ],
      },
    ];

    (globalThis.fetch as any).mockImplementation((url: string) => {
      if (url.includes('/api/agent/proposals?account_id=')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(proposalsWithRole),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(
      <WeeklyProposalPanel
        accountId={123}
        refreshSignal={1}
        onProposalAction={mockOnProposalAction}
      />
    );

    await waitFor(() => {
      expect(screen.queryByText(/Loading proposals/i)).not.toBeInTheDocument();
    });

    // Badge combina matrix_role y post_type: [Proof · Reel] y [Teach · Carousel]
    expect(screen.getByText(/Proof\s*·\s*Reel/i)).toBeInTheDocument();
    expect(screen.getByText(/Teach\s*·\s*Carousel/i)).toBeInTheDocument();
  });

  test('renders selector between 3 hook candidates and selecting one updates caption', async () => {
    const hookCandidates = [
      'El 78% de las cuentas cometen este error',
      '¿Y si todo lo que sabes sobre Reels fuera falso?',
      'Dejé de buscar la perfección y mis ventas subieron un 40%'
    ];

    const proposalsWithHooks = [
      {
        id: 'proposal-hooks',
        account_id: '123',
        week_start: '2026-06-29',
        status: 'pending_approval',
        slots: [
          {
            day: 'Monday',
            theme: 'Hook test Reel',
            caption: `${hookCandidates[0]}\n\nAquí va el resto del contenido.`,
            post_type: 'reel',
            matrix_role: 'proof',
            hook_candidates: hookCandidates,
            post_id: 1001,
            image_id: 'file-abc',
          },
        ],
      },
    ];

    const newCaption = `${hookCandidates[1]}\n\nAquí va el resto del contenido.`;
    (globalThis.fetch as any).mockImplementation((url: string) => {
      if (url.includes('/api/agent/proposals?account_id=')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(proposalsWithHooks),
        });
      }
      if (url.includes('/slots/0/hook')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ caption: newCaption }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(
      <WeeklyProposalPanel
        accountId={123}
        refreshSignal={1}
        onProposalAction={mockOnProposalAction}
      />
    );

    await waitFor(() => {
      expect(screen.queryByText(/Loading proposals/i)).not.toBeInTheDocument();
    });

    const lunLabel = screen.getByText('Mon');
    const dayBox = lunLabel.closest('div[class*="wpp-day-box"]') as HTMLElement;
    fireEvent.click(dayBox);

    // Los 3 ganchos candidatos están presentes en el panel
    expect(screen.getByText(hookCandidates[0])).toBeInTheDocument();
    expect(screen.getByText(hookCandidates[1])).toBeInTheDocument();
    expect(screen.getByText(hookCandidates[2])).toBeInTheDocument();

    // Seleccionar el segundo gancho candidato lo persiste y actualiza el caption visible
    fireEvent.click(screen.getByText(hookCandidates[1]));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/agent/proposals/proposal-hooks/slots/0/hook'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ hook: hookCandidates[1] }),
        })
      );
    });
    await waitFor(() => {
      const caption = document.querySelector('.wpp-detail-caption');
      expect(caption?.textContent?.startsWith(hookCandidates[1])).toBe(true);
    });
    expect(screen.getByText(hookCandidates[1]).closest('button')).toHaveAttribute('aria-pressed', 'true');
  });
  test('slot con foto adjuntada por Telegram muestra su miniatura en vez de la de Drive', async () => {
    mockProposals[0].slots[0] = { ...mockProposals[0].slots[0], image_id: null as any, media_url: 'https://storage.test/telegram/p1_0.jpg' } as any;
    try {
      const { container } = render(
        <WeeklyProposalPanel accountId={123} refreshSignal={1} onProposalAction={mockOnProposalAction} />
      );
      await waitFor(() => expect(screen.queryByText(/Loading proposals/i)).not.toBeInTheDocument());

      const thumb = container.querySelector('img.wpp-day-thumb') as HTMLImageElement;
      const src = thumb.getAttribute('src') ?? '';
      expect(src).toContain('/api/posts/1001/thumbnail?size=480');
      expect(src).not.toContain('/api/drive/files/');
      expect(thumb).toHaveAttribute('loading', 'lazy');
    } finally {
      mockProposals[0].slots[0] = { ...mockProposals[0].slots[0], image_id: 'file-abc', media_url: undefined } as any;
    }
  });

  test('el post 2026-10-14T18:00Z con Europe/Madrid cae el miercoles 14 a las 20:00', async () => {
    const tzProposals = [
      {
        id: 'prop-tz-1',
        account_id: '123',
        week_start: '2026-10-12',
        status: 'pending_approval',
        slots: [
          {
            day: 'Wednesday',
            theme: 'Consejo semanal',
            caption: 'Contenido del miércoles',
            post_id: 53946,
            scheduled_at: '2026-10-14T18:00:00Z',
          },
        ],
      },
    ];

    (globalThis.fetch as any).mockImplementation((url: string) => {
      if (url.includes('/api/agent/proposals?account_id=')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(tzProposals),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(
      <WeeklyProposalPanel
        accountId={123}
        refreshSignal={1}
        onProposalAction={mockOnProposalAction}
        timezone="Europe/Madrid"
        secondaryTimezone="Asia/Kuching"
      />
    );

    await waitFor(() => expect(screen.queryByText(/Loading proposals/i)).not.toBeInTheDocument());
    expect(screen.getByText('Wed')).toBeInTheDocument();
    expect(screen.getByText('14')).toBeInTheDocument();
  });

  test('coloca el slot por el instante de su post en la zona, no por el día guardado', async () => {
    // Guardado como Thursday, pero el post es el miércoles 14 a las 20:00 en Madrid
    const tzProposals = [{
      id: 'prop-tz-2', account_id: '123', week_start: '2026-10-12', status: 'pending_approval',
      slots: [{ day: 'Thursday', theme: 'Tema', caption: 'Caption del slot', post_id: 53946, scheduled_at: '2026-10-14T18:00:00Z' }],
    }];
    (globalThis.fetch as any).mockImplementation((url: string) => Promise.resolve({
      ok: true,
      json: () => Promise.resolve(url.includes('/api/agent/proposals?account_id=') ? tzProposals : {}),
    }));

    const { container } = render(
      <WeeklyProposalPanel
        accountId={123}
        refreshSignal={1}
        onProposalAction={mockOnProposalAction}
        timezone="Europe/Madrid"
        secondaryTimezone="Asia/Kuching"
      />
    );

    await waitFor(() => expect(screen.queryByText(/Loading proposals/i)).not.toBeInTheDocument());
    const boxes = container.querySelectorAll('.wpp-day-box');
    expect(boxes[2].className).toContain('wpp-day-box--slot');
    expect(boxes[3].className).not.toContain('wpp-day-box--slot');

    fireEvent.click(boxes[2]);
    const timeInput = container.querySelector('.wpp-time-input') as HTMLInputElement;
    expect(timeInput.value).toBe('2026-10-14T20:00');
    expect(screen.getByText(/Mié 14 · 20:00 Madrid · Jue 15 · 02:00 Kuching/)).toBeInTheDocument();
  });

  test('sin zona principal coloca el slot en el día y la hora de la zona del navegador', async () => {
    const spy = vi.spyOn(Intl.DateTimeFormat.prototype, 'resolvedOptions')
      .mockReturnValue({ timeZone: 'America/New_York' } as Intl.ResolvedDateTimeFormatOptions);
    const tzProposals = [{
      id: 'prop-tz-3', account_id: '123', week_start: '2026-10-12', status: 'pending_approval',
      slots: [{ day: 'Wednesday', theme: 'Tema', caption: 'Caption del slot', post_id: 53946, scheduled_at: '2026-10-14T18:00:00Z' }],
    }];
    (globalThis.fetch as any).mockImplementation((url: string) => Promise.resolve({
      ok: true,
      json: () => Promise.resolve(url.includes('/api/agent/proposals?account_id=') ? tzProposals : {}),
    }));

    const { container } = render(
      <WeeklyProposalPanel accountId={123} refreshSignal={1} onProposalAction={mockOnProposalAction} />
    );

    await waitFor(() => expect(screen.queryByText(/Loading proposals/i)).not.toBeInTheDocument());
    // Guardado como Wednesday; 18:00 UTC es el miércoles 14 a las 14:00 en Nueva York
    const boxes = container.querySelectorAll('.wpp-day-box');
    expect(boxes[2].className).toContain('wpp-day-box--slot');
    fireEvent.click(boxes[2]);
    const timeInput = container.querySelector('.wpp-time-input') as HTMLInputElement;
    expect(timeInput.value).toBe('2026-10-14T14:00');
    spy.mockRestore();
  });

  test('reorder envia timezone en el cuerpo de la peticion', async () => {
    let reorderBody: any = null;
    (globalThis.fetch as any).mockImplementation((url: string, options: any) => {
      if (url.includes('/slots/reorder')) {
        reorderBody = JSON.parse(options.body);
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true }) });
      }
      if (url.includes('/api/agent/proposals?account_id=')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockProposals),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(
      <WeeklyProposalPanel
        accountId={123}
        refreshSignal={1}
        onProposalAction={mockOnProposalAction}
        timezone="Europe/Madrid"
      />
    );

    await waitFor(() => expect(screen.queryByText(/Loading proposals/i)).not.toBeInTheDocument());

    // Arrastra el primer slot con post a una columna vacía
    const boxes = Array.from(document.querySelectorAll('.wpp-day-box'));
    const from = boxes.find(b => b.getAttribute('draggable') === 'true') as HTMLElement;
    const to = boxes.find(b => b.querySelector('.wpp-day-empty')) as HTMLElement;
    const dataTransfer = { effectAllowed: '', setData: () => {} };
    fireEvent.dragStart(from, { dataTransfer });
    fireEvent.dragOver(to, { dataTransfer });
    fireEvent.drop(to, { dataTransfer });

    await waitFor(() => expect(reorderBody).not.toBeNull());
    expect(reorderBody.timezone).toBe('Europe/Madrid');
  });
});
