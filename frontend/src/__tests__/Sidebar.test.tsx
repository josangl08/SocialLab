import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, test, expect, vi } from 'vitest';
import Sidebar from '../components/layout/Sidebar';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ logout: vi.fn() }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe('Sidebar', () => {
  test('muestra exactamente 6 ítems en orden', () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );

    const items = within(screen.getByRole('list')).getAllByRole('link');
    expect(items.map((item) => item.textContent)).toEqual([
      'Dashboard', 'Planner', 'Content Studio', 'Analytics', 'Hermes Mind', 'Estrategia', 'Settings',
    ]);
    expect(screen.getByRole('link', { name: 'Content Studio' })).toHaveAttribute('href', '/generate');
  });
});
