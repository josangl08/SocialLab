import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { AuthProvider, useAuth } from '../context/AuthContext';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

const TestConsumer: React.FC = () => {
  const { login, isAuthenticated } = useAuth();
  return (
    <div>
      <button onClick={() => login('mock-token-abc')}>login</button>
      <span data-testid="auth-status">{isAuthenticated ? 'in' : 'out'}</span>
    </div>
  );
};

describe('AuthContext global 401 interceptor', () => {
  let originalFetch: typeof window.fetch;

  beforeEach(() => {
    mockNavigate.mockClear();
    localStorage.clear();
    originalFetch = window.fetch;
  });

  afterEach(() => {
    window.fetch = originalFetch;
  });

  const renderLoggedIn = () => {
    render(<AuthProvider><TestConsumer /></AuthProvider>);
    act(() => {
      screen.getByText('login').click();
    });
  };

  test('forces logout and redirects on a 401 from a session-protected endpoint', async () => {
    window.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 401 })) as typeof window.fetch;
    renderLoggedIn();

    await act(async () => {
      await fetch('/api/agent/config/7');
    });

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('out');
    });
    expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true });
  });

  test('does not force logout on a 401 from /instagram/sync (third-party token expired)', async () => {
    window.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 401 })) as typeof window.fetch;
    renderLoggedIn();

    await act(async () => {
      await fetch('/instagram/sync?instagram_account_id=7');
    });

    expect(screen.getByTestId('auth-status').textContent).toBe('in');
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
