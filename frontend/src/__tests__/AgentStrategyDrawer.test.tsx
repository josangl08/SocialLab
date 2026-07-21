import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import AgentStrategyDrawer from '../features/agent/AgentStrategyDrawer';

describe('MonthlyCampaignSection in AgentStrategyDrawer', () => {
  const mockOnHide = vi.fn();
  const mockOnSave = vi.fn();

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

    // Set mock token in localStorage
    window.localStorage.setItem('authToken', 'mock-token-abc');

    // Mock API fetch response for Agent Strategy config
    (global.fetch as any).mockImplementation((url: string) => {
      if (url.includes('/api/agent/config/12')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            account_type: 'personal',
            sector: 'Testing',
            purpose: 'Verification',
            target_audience: 'Developers',
            style_guide: 'Clean',
            default_tone: 'casual',
            default_language: 'es',
            posting_frequency: 'few_times_week',
            best_times: ['10:00'],
            content_pillars: ['code'],
            hashtag_strategy: 'minimal',
            reference_accounts: [],
            posts_per_week: 1,
            scheduling_mode: 'flexible',
            preferred_days: [],
            content_type_mix: { post: 1, reel: 0, carousel: 0, story: 0 }
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });
  });

  test('renders Monthly Campaign inputs when Drawer is visible', async () => {
    render(
      <AgentStrategyDrawer
        accountId={12}
        accountUsername="test_profile"
        show={true}
        onHide={mockOnHide}
        onSave={mockOnSave}
      />
    );

    // Wait for strategy config loading to finish
    await waitFor(() => {
      expect(screen.getByText(/Tipo de Cuenta/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Enfoque del Mes/i)).toBeInTheDocument();

    // Check mode buttons
    expect(screen.getByText('Campaña Comercial')).toBeInTheDocument();
    expect(screen.getByText('Hilo Personal')).toBeInTheDocument();

    // Check Title and Description inputs via labels
    expect(screen.getByText('Título del Enfoque')).toBeInTheDocument();
    expect(screen.getByText('Descripción')).toBeInTheDocument();

    // Check Weekly Focus inputs
    expect(screen.getByPlaceholderText('Foco para la semana 1')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Foco para la semana 2')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Foco para la semana 3')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Foco para la semana 4')).toBeInTheDocument();
  });

  test('allows typing title, description, and weekly focus', async () => {
    render(
      <AgentStrategyDrawer
        accountId={12}
        show={true}
        onHide={mockOnHide}
        onSave={mockOnSave}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Título del Enfoque')).toBeInTheDocument();
    });

    const titleLabel = screen.getByText('Título del Enfoque');
    const titleInput = titleLabel.parentElement?.querySelector('input') as HTMLInputElement;
    fireEvent.change(titleInput, { target: { value: 'Nueva Campaña' } });
    expect(titleInput.value).toBe('Nueva Campaña');

    const descLabel = screen.getByText('Descripción');
    const descTextarea = descLabel.parentElement?.querySelector('textarea') as HTMLTextAreaElement;
    fireEvent.change(descTextarea, { target: { value: 'Descripción detallada de la campaña.' } });
    expect(descTextarea.value).toBe('Descripción detallada de la campaña.');

    const week1Input = screen.getByPlaceholderText('Foco para la semana 1') as HTMLInputElement;
    fireEvent.change(week1Input, { target: { value: 'Foco inicial' } });
    expect(week1Input.value).toBe('Foco inicial');
  });

  test('allows adding and removing milestones', async () => {
    render(
      <AgentStrategyDrawer
        accountId={12}
        show={true}
        onHide={mockOnHide}
        onSave={mockOnSave}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Hitos (Milestones)')).toBeInTheDocument();
    });

    const label = screen.getByText('Hitos (Milestones)');
    const container = label.parentElement;
    const dateInput = container?.querySelector('input[type="date"]') as HTMLInputElement;
    const eventInput = screen.getByPlaceholderText('Nuevo hito...') as HTMLInputElement;
    const addButton = container?.querySelector('button') as HTMLButtonElement;

    // Add a milestone
    fireEvent.change(dateInput, { target: { value: '2026-07-15' } });
    fireEvent.change(eventInput, { target: { value: 'Lanzamiento Especial' } });
    fireEvent.click(addButton);

    // Verify it is listed
    expect(screen.getByText('2026-07-15')).toBeInTheDocument();
    expect(screen.getByText('Lanzamiento Especial')).toBeInTheDocument();

    // Find the trash/remove button inside the milestone item
    const removeButton = screen.getByText('Lanzamiento Especial').parentElement?.querySelector('button') as HTMLButtonElement;
    fireEvent.click(removeButton);

    // Verify it is gone
    expect(screen.queryByText('Lanzamiento Especial')).not.toBeInTheDocument();
  });
});
