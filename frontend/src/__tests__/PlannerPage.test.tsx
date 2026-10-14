import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, test, expect, vi } from 'vitest';
import PlannerPage from '../components/planner/PlannerPage';
import { apiClient } from '../api/client';
import { contentApi } from '../api/content';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ token: 'mock-token' }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('../api/client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
  ApiError: class ApiError extends Error {},
}));

vi.mock('../api/content', () => ({
  contentApi: { generateStory: vi.fn() },
}));

// Vistas pesadas del Planner fuera del alcance de este test
vi.mock('../components/calendar/CalendarView', () => ({ default: () => <div>calendar</div> }));
vi.mock('../components/posts/PostList', () => ({ default: () => <div>post-list</div> }));
vi.mock('../components/planner/WeeklyProposalPanel', () => ({ default: () => null }));
vi.mock('../components/planner/MonthlyFocusBanner', () => ({ MonthlyFocusBanner: () => null }));

describe('PlannerPage', () => {
  test('la pestaña "Stories del día" muestra la secuencia de la cuenta principal', async () => {
    (apiClient.get as any).mockResolvedValue([{ id: 5, username: 'cuenta' }]);
    (contentApi.generateStory as any).mockResolvedValue({
      frames: [{ index: 1, role: 'warmup', text: '¿Café o té?', sticker: 'poll' }],
    });
    render(
      <MemoryRouter>
        <PlannerPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: /Stories del día/i }));
    const generate = screen.getByRole('button', { name: /Generar Stories del día/i });
    await waitFor(() => expect(generate).toBeEnabled());
    fireEvent.click(generate);

    expect(await screen.findByRole('list', { name: /Secuencia de Stories/i })).toBeInTheDocument();
    expect(contentApi.generateStory).toHaveBeenCalledWith(expect.objectContaining({ account_id: 5 }));
    expect(screen.queryByText('calendar')).not.toBeInTheDocument();
  });

  test('reporta la zona del navegador como detected_timezone solo en las cuentas donde difiere', async () => {
    const spy = vi.spyOn(Intl.DateTimeFormat.prototype, 'resolvedOptions')
      .mockReturnValue({ timeZone: 'America/New_York' } as Intl.ResolvedDateTimeFormatOptions);
    (apiClient.get as any).mockResolvedValue([
      { id: 5, username: 'desfasada', detected_timezone: 'Asia/Kuching' },
      { id: 6, username: 'al-dia', detected_timezone: 'America/New_York' },
    ]);
    (apiClient.put as any).mockResolvedValue({});

    render(
      <MemoryRouter>
        <PlannerPage />
      </MemoryRouter>
    );

    await waitFor(() => expect(apiClient.put).toHaveBeenCalled());
    expect(apiClient.put).toHaveBeenCalledTimes(1);
    expect(apiClient.put).toHaveBeenCalledWith('/instagram/accounts/5/config', { detected_timezone: 'America/New_York' });
    spy.mockRestore();
  });
});
