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
      if (url.includes('/instagram/accounts') && (!options || options.method !== 'DELETE')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockAccounts),
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
});
