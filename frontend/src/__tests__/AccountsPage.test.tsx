import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import AccountsPage from '../components/accounts/AccountsPage';

describe('AccountsPage Component', () => {
  const mockToken = 'mock-auth-token-xyz';
  const mockAccounts = [
    {
      id: 1,
      username: 'active_user',
      account_name: 'Active Account',
      profile_picture_url: 'http://img/1.png',
      followers_count: 5000,
      expires_at: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString(), // 10 days in future -> valid
      is_active: true,
      telegram_chat_id: '12345',
      drive_folder_id: 'folder-1'
    },
    {
      id: 2,
      username: 'expired_user',
      account_name: 'Expired Account',
      profile_picture_url: null,
      followers_count: 10,
      expires_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(), // 2 days in past -> expired
      is_active: true,
      telegram_chat_id: null,
      drive_folder_id: null
    }
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Mock localStorage
    const store: Record<string, string> = {};
    const mockLocalStorage = {
      getItem: (key: string) => store[key] || null,
      setItem: (key: string, value: string) => { store[key] = value; },
      removeItem: (key: string) => { delete store[key]; },
      clear: () => { for (const k in store) delete store[k]; }
    };
    Object.defineProperty(window, 'localStorage', {
      value: mockLocalStorage,
      writable: true
    });
    
    window.localStorage.setItem('authToken', mockToken);
    
    // Mock global fetch
    global.fetch = vi.fn().mockImplementation((url: string, options?: any) => {
      if (url.includes('/instagram/accounts') && (!options || (options.method !== 'DELETE' && options.method !== 'PATCH' && options.method !== 'PUT'))) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockAccounts),
        });
      }
      if (url.includes('/api/telegram/generate-link-token')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ token: 'mock-link-token-abc', expires_at: '2026-06-01T00:00:00Z' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });
    });
    
    // Mock window.confirm
    window.confirm = vi.fn().mockReturnValue(true);
    // Mock window.alert
    window.alert = vi.fn();
  });

  test('renders page title and list of accounts with badges', async () => {
    render(<AccountsPage />);

    // Wait for loading to finish and accounts to show
    await waitFor(() => {
      expect(screen.getByText('@active_user')).toBeInTheDocument();
    });

    // Verify page header is rendered
    expect(screen.getByText(/Cuentas de Instagram/i)).toBeInTheDocument();

    expect(screen.getByText('@expired_user')).toBeInTheDocument();

    // Check status badges
    expect(screen.getByText(/Conectada/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Reconectar/i).length).toBeGreaterThan(0);

    // Verify followers count is displayed correctly
    expect(screen.getByText(/5.000 seguidores/i)).toBeInTheDocument();
    expect(screen.getByText(/10 seguidores/i)).toBeInTheDocument();
  });

  test('allows disconnecting a account with confirmation', async () => {
    render(<AccountsPage />);

    // Wait for accounts to load
    await waitFor(() => {
      expect(screen.getByText('@active_user')).toBeInTheDocument();
    });

    const activeUserCard = screen.getByText('@active_user').closest('.card') as HTMLElement;
    const disconnectBtn = within(activeUserCard).getByRole('button', { name: /Desconectar/i });

    fireEvent.click(disconnectBtn);

    // Verify confirmation was triggered
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('active_user'));

    // Wait for DELETE fetch call and UI update
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/instagram/accounts/1',
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    // Verify account 1 has been removed from screen
    expect(screen.queryByText('@active_user')).not.toBeInTheDocument();
    expect(screen.getByText('@expired_user')).toBeInTheDocument();
  });

  test('displays info alert if accounts list is empty', async () => {
    // Override fetch to return empty list
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    });

    render(<AccountsPage />);

    await waitFor(() => {
      expect(screen.getByText(/No tienes cuentas de Instagram conectadas/i)).toBeInTheDocument();
    });
  });

  test('renders Telegram section: Link Telegram when chat ID is null, Linked badge when chat ID is set', async () => {
    render(<AccountsPage />);

    // Wait for accounts to load
    await waitFor(() => {
      expect(screen.getByText('@active_user')).toBeInTheDocument();
    });

    const activeUserCard = screen.getByText('@active_user').closest('.card') as HTMLElement;
    const expiredUserCard = screen.getByText('@expired_user').closest('.card') as HTMLElement;

    // Active user has telegram_chat_id: '12345' -> should show Linked badge and Unlink button
    expect(within(activeUserCard).getByText(/Linked/i)).toBeInTheDocument();
    expect(within(activeUserCard).getByRole('button', { name: /Unlink/i })).toBeInTheDocument();

    // Expired user has telegram_chat_id: null -> should show Link Telegram button
    expect(within(expiredUserCard).getByRole('button', { name: /Link Telegram/i })).toBeInTheDocument();
  });

  test('clicking Link Telegram calls generate-link-token and displays the linking token', async () => {
    render(<AccountsPage />);

    await waitFor(() => {
      expect(screen.getByText('@expired_user')).toBeInTheDocument();
    });

    const expiredUserCard = screen.getByText('@expired_user').closest('.card') as HTMLElement;
    const linkBtn = within(expiredUserCard).getByRole('button', { name: /Link Telegram/i });

    fireEvent.click(linkBtn);

    // Should call generate-link-token endpoint
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/telegram/generate-link-token',
        expect.objectContaining({ method: 'POST' })
      );
    });

    // Should display the generated token 'mock-link-token-abc' on the screen
    await waitFor(() => {
      expect(screen.getByText(/mock-link-token-abc/i)).toBeInTheDocument();
    });
  });

  test('clicking Unlink calls API to clear telegram_chat_id and updates state', async () => {
    render(<AccountsPage />);

    await waitFor(() => {
      expect(screen.getByText('@active_user')).toBeInTheDocument();
    });

    const activeUserCard = screen.getByText('@active_user').closest('.card') as HTMLElement;
    const unlinkBtn = within(activeUserCard).getByRole('button', { name: /Unlink/i });

    // Mock confirm dialog
    window.confirm = vi.fn().mockReturnValue(true);

    fireEvent.click(unlinkBtn);

    // Should call update endpoint (PATCH /instagram/accounts/1 or PUT /instagram/accounts/1/config)
    await waitFor(() => {
      const call = (global.fetch as any).mock.calls.find(([url]: any) => url.includes('/accounts/1'));
      expect(call).toBeDefined();
      const [, options] = call;
      expect(options.method === 'PATCH' || options.method === 'PUT').toBe(true);
      const body = JSON.parse(options.body);
      expect(body.telegram_chat_id).toBeNull();
    });
  });
});

