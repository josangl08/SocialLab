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
    },
    {
      id: 3,
      username: 'revoked_user',
      account_name: 'Revoked Account',
      profile_picture_url: null,
      followers_count: 20,
      expires_at: new Date(Date.now() + 20 * 24 * 60 * 60 * 1000).toISOString(), // 20 days in future
      token_invalid: true, // but Meta already invalidated it (e.g. password change)
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
    globalThis.fetch = vi.fn().mockImplementation((url: string, options?: any) => {
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
      if (url.includes('/api/drive/status')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ connected: false, scopes: [], connected_at: null }),
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

  test('shows "Reconectar" for a token_invalid account even with a future expires_at', async () => {
    render(<AccountsPage />);

    await waitFor(() => {
      expect(screen.getByText('@revoked_user')).toBeInTheDocument();
    });

    const revokedCard = screen.getByText('@revoked_user').closest('.st-account-card') as HTMLElement;
    expect(within(revokedCard).getAllByText(/Reconectar/i).length).toBeGreaterThan(0);
    expect(within(revokedCard).queryByText(/Conectada/i)).not.toBeInTheDocument();
  });

  test('allows disconnecting a account with confirmation', async () => {
    render(<AccountsPage />);

    // Wait for accounts to load
    await waitFor(() => {
      expect(screen.getByText('@active_user')).toBeInTheDocument();
    });

    const activeUserCard = screen.getByText('@active_user').closest('.st-account-card') as HTMLElement;
    const disconnectBtn = within(activeUserCard).getByRole('button', { name: /Desconectar/i });

    fireEvent.click(disconnectBtn);

    // Verify confirmation was triggered
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('active_user'));

    // Wait for DELETE fetch call and UI update
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
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
    globalThis.fetch = vi.fn().mockResolvedValue({
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

    const activeUserCard = screen.getByText('@active_user').closest('.st-account-card') as HTMLElement;
    const expiredUserCard = screen.getByText('@expired_user').closest('.st-account-card') as HTMLElement;

    // Active user has telegram_chat_id: '12345' -> shows "Vinculado" and "Unlink"
    expect(within(activeUserCard).getAllByText(/Vinculado/i).length).toBeGreaterThan(0);
    expect(within(activeUserCard).getAllByRole('button', { name: /Unlink/i }).length).toBeGreaterThan(0);

    // Expired user has telegram_chat_id: null -> should show Link Telegram button
    expect(within(expiredUserCard).getByRole('button', { name: /Link Telegram/i })).toBeInTheDocument();
  });

  test('clicking Link Telegram calls generate-link-token and displays the linking token', async () => {
    render(<AccountsPage />);

    await waitFor(() => {
      expect(screen.getByText('@expired_user')).toBeInTheDocument();
    });

    const expiredUserCard = screen.getByText('@expired_user').closest('.st-account-card') as HTMLElement;
    const linkBtn = within(expiredUserCard).getByRole('button', { name: /Link Telegram/i });

    fireEvent.click(linkBtn);

    // Should call generate-link-token endpoint
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
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

    const activeUserCard = screen.getByText('@active_user').closest('.st-account-card') as HTMLElement;
    const unlinkBtn = within(activeUserCard).getAllByRole('button', { name: /Unlink/i })[0];

    // Mock confirm dialog
    window.confirm = vi.fn().mockReturnValue(true);

    fireEvent.click(unlinkBtn);

    // Should call update endpoint
    await waitFor(() => {
      const call = (globalThis.fetch as any).mock.calls.find(([url]: any) => url.includes('/accounts/1'));
      expect(call).toBeDefined();
      const [, options] = call;
      expect(options.method === 'PATCH' || options.method === 'PUT').toBe(true);
      const body = JSON.parse(options.body);
      expect(body.telegram_chat_id).toBeNull();
    });
  });

  // --- Google Drive OAuth Extension Tests ---

  test('renders "Conectar Drive" button placeholder when driveConnected is false', async () => {
    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText('@active_user')).toBeInTheDocument();
    });

    expect(screen.getAllByRole('button', { name: /Conectar Drive/i }).length).toBeGreaterThan(0);
  });

  test('renders "Drive conectado" placeholder when driveConnected is true', async () => {
    // Mock drive status as connected
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/drive/status')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ connected: true, scopes: ['drive'], connected_at: '2026-06-30T10:00:00Z' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockAccounts),
      });
    });

    render(<AccountsPage />);
    await waitFor(() => {
      expect(screen.getByText('@active_user')).toBeInTheDocument();
    });

    expect(screen.getAllByText(/Drive conectado/i).length).toBeGreaterThan(0);
  });

  test('handles drive_connected=true URL search parameter', async () => {
    const originalLocation = window.location;
    delete (window as any).location;
    window.location = {
      ...originalLocation,
      search: '?drive_connected=true',
    } as any;

    const replaceStateSpy = vi.spyOn(window.history, 'replaceState');

    render(<AccountsPage />);

    await waitFor(() => {
      expect(replaceStateSpy).toHaveBeenCalled();
    });

    (window as any).location = originalLocation;
  });

  test('?instagram_error=no_linked_page explica que falta vincular Instagram a una Página', async () => {
    const originalLocation = window.location;
    delete (window as any).location;
    window.location = { ...originalLocation, search: '?instagram_error=no_linked_page' } as any;
    const replaceStateSpy = vi.spyOn(window.history, 'replaceState');

    render(<AccountsPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent(/cuenta profesional de Instagram vinculada/);
    expect(replaceStateSpy).toHaveBeenCalled();
    (window as any).location = originalLocation;
  });

  const mixedAccounts = [
    {
      id: 1,
      username: 'fb_user',
      account_name: 'FB Connected',
      login_type: 'facebook',
      profile_picture_url: null,
      expires_at: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString(),
      is_active: true,
    },
    {
      id: 2,
      username: 'ig_user',
      account_name: 'IG Connected',
      login_type: 'instagram',
      profile_picture_url: null,
      expires_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
      is_active: true,
    },
  ];

  const renderMixed = async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => Promise.resolve({
      ok: true,
      json: () => Promise.resolve(url.includes('/api/drive/status') ? { connected: false } : mixedAccounts),
    }));
    render(<AccountsPage />);
    await waitFor(() => expect(screen.getByText('@fb_user')).toBeInTheDocument());
  };

  const withMockLocation = (fn: () => void) => {
    const originalLocation = window.location;
    const setLocation = (value: unknown) =>
      Object.defineProperty(window, 'location', { value, writable: true, configurable: true });
    setLocation({ href: '' });
    try { fn(); } finally { setLocation(originalLocation); }
  };

  test('cada tarjeta muestra con qué login está conectada y lo que no incluye', async () => {
    await renderMixed();

    const fbCard = screen.getByText('@fb_user').closest('.st-account-card') as HTMLElement;
    const igCard = screen.getByText('@ig_user').closest('.st-account-card') as HTMLElement;
    expect(within(fbCard).getByText(/Conectada con Facebook/)).toBeInTheDocument();
    expect(within(fbCard).getByText(/reconectar cada 90 días/i)).toBeInTheDocument();
    expect(within(igCard).getByText(/Conectada con Instagram/)).toBeInTheDocument();
    expect(within(igCard).getByText(/No importa colaboraciones/)).toBeInTheDocument();
  });

  test('"Conectar cuenta" abre el selector con las dos opciones y redirige con el método elegido', async () => {
    await renderMixed();

    fireEvent.click(screen.getByRole('button', { name: /Conectar cuenta/i }));
    const dialog = screen.getByRole('dialog');
    const facebook = within(dialog).getByRole('region', { name: 'Facebook' });
    expect(within(facebook).getByText(/Importar Stories/)).toBeInTheDocument();
    expect(within(facebook).getByText(/Ser administrador de esa Página/)).toBeInTheDocument();
    const instagram = within(dialog).getByRole('region', { name: 'Instagram' });
    expect(within(instagram).getByText(/Importar Stories/).closest('li')).toHaveClass('lm-yes');
    expect(within(instagram).getByText(/Importar colaboraciones/).closest('li')).toHaveClass('lm-no');
    expect(within(dialog).getByText(/Stories de mejores amigos no se importan/)).toBeInTheDocument();

    withMockLocation(() => {
      fireEvent.click(within(facebook).getByRole('button', { name: /Conectar con Facebook/i }));
      expect(window.location.href).toContain('/instagram/login');
      expect(window.location.href).toContain('method=facebook');
      expect(window.location.href).not.toContain('account_id');
    });
  });

  test('"Cambiar" abre el selector marcando el login actual y reconecta la misma cuenta', async () => {
    await renderMixed();

    const fbCard = screen.getByText('@fb_user').closest('.st-account-card') as HTMLElement;
    fireEvent.click(within(fbCard).getByRole('button', { name: 'Cambiar' }));
    const dialog = screen.getByRole('dialog');
    expect(within(within(dialog).getByRole('region', { name: 'Facebook' })).getByText('Actual')).toBeInTheDocument();

    withMockLocation(() => {
      fireEvent.click(within(dialog).getByRole('button', { name: /Conectar con Instagram/i }));
      expect(window.location.href).toContain('method=instagram');
      expect(window.location.href).toContain('account_id=1');
    });
  });

  test('Escape cierra el selector', async () => {
    await renderMixed();

    fireEvent.click(screen.getByRole('button', { name: /Conectar cuenta/i }));
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  test('"Reconectar" reutiliza el login de la cuenta sin abrir el selector', async () => {
    await renderMixed();

    const igCard = screen.getByText('@ig_user').closest('.st-account-card') as HTMLElement;
    withMockLocation(() => {
      fireEvent.click(within(igCard).getByRole('button', { name: /^Reconectar$/i }));
      expect(window.location.href).toContain('method=instagram');
      expect(window.location.href).toContain('account_id=2');
    });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
