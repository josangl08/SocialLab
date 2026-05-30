import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import CreatePost from '../components/posts/CreatePost';
import { useAuth } from '../context/AuthContext';

// Mock useAuth
vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

describe('CreatePost Component Boilerplate', () => {
  const mockToken = 'mock-token-123';
  const mockOnPostCreated = vi.fn();
  const mockAccounts = [
    { id: 1, username: 'test_user_1', account_name: 'Test Account 1' },
    { id: 2, username: 'test_user_2', account_name: 'Test Account 2' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (useAuth as any).mockReturnValue({ token: mockToken });
    
    // Mock successful fetch for accounts list
    (global.fetch as any).mockImplementation((url: string) => {
      if (url.includes('/instagram/accounts')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockAccounts),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });
  });

  test('renders Instagram account selector option lists', async () => {
    render(<CreatePost onPostCreated={mockOnPostCreated} />);

    // Wait for accounts to load
    await waitFor(() => {
      expect(screen.getByLabelText(/Cuenta de Instagram/i)).toBeInTheDocument();
    });

    const selector = screen.getByLabelText(/Cuenta de Instagram/i) as HTMLSelectElement;
    expect(selector).toBeInTheDocument();
    expect(selector.value).toBe('');

    // Check option values inside the selector specifically
    const options = within(selector).getAllByRole('option');
    // First option is the default prompt option, followed by the two mock accounts
    expect(options[0]).toHaveValue('');
    expect(options[1]).toHaveValue('1');
    expect(options[2]).toHaveValue('2');
    expect(options[1].textContent).toContain('Test Account 1');
    expect(options[2].textContent).toContain('Test Account 2');
  });

  test('allows selecting an Instagram account', async () => {
    render(<CreatePost onPostCreated={mockOnPostCreated} />);

    // Wait for accounts to load
    await waitFor(() => {
      expect(screen.getByLabelText(/Cuenta de Instagram/i)).toBeInTheDocument();
    });

    const selector = screen.getByLabelText(/Cuenta de Instagram/i) as HTMLSelectElement;
    
    // Fire change event to select account ID 2
    fireEvent.change(selector, { target: { value: '2' } });
    expect(selector.value).toBe('2');
  });
});
