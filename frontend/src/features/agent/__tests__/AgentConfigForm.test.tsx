import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import AgentConfigForm from '../AgentConfigForm';

describe('AgentConfigForm Component', () => {
  const mockToken = 'mock-auth-token-xyz';
  
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
      writable: true,
      configurable: true
    });
    window.localStorage.setItem('authToken', mockToken);

    // Mock global fetch
    globalThis.fetch = vi.fn().mockImplementation(() => {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ updated: true }),
      });
    });
  });

  test('renders form fields with initial values', () => {
    const initialConfig = {
      account_type: 'professional' as const,
      sector: 'Sports Analytics',
      purpose: 'Brand awareness',
      target_audience: 'Soccer coach',
      style_guide: 'Informative and clean'
    };

    render(
      <AgentConfigForm
        accountId={123}
        initialConfig={initialConfig}
      />
    );

    expect(screen.getByTestId('agent-config-form')).toBeInTheDocument();
    expect(screen.getByLabelText(/Profesional/i)).toBeChecked();
    expect(screen.getByPlaceholderText(/Ej: Deporte, Fitness, Moda, Tecnología/i)).toHaveValue('Sports Analytics');
    expect(screen.getByPlaceholderText(/Ej: Captación de clientes, Branding, Ventas/i)).toHaveValue('Brand awareness');
    expect(screen.getByPlaceholderText(/Ej: Jóvenes deportistas, Emprendedores/i)).toHaveValue('Soccer coach');
    expect(screen.getByPlaceholderText(/Ej: Tono técnico e inspirador, emojis con moderación.../i)).toHaveValue('Informative and clean');
  });

  test('submits form with updated values and calls API', async () => {
    const onSaveMock = vi.fn();
    
    render(
      <AgentConfigForm
        accountId={123}
        onSave={onSaveMock}
      />
    );

    // Default is 'personal'
    expect(screen.getByLabelText(/Personal/i)).toBeChecked();

    // Fill inputs
    fireEvent.change(screen.getByPlaceholderText(/Ej: Deporte, Fitness, Moda, Tecnología/i), { target: { value: 'Tech' } });
    fireEvent.change(screen.getByPlaceholderText(/Ej: Captación de clientes, Branding, Ventas/i), { target: { value: 'Lead Generation' } });
    fireEvent.change(screen.getByPlaceholderText(/Ej: Jóvenes deportistas, Emprendedores/i), { target: { value: 'SaaS Owners' } });
    fireEvent.change(screen.getByPlaceholderText(/Ej: Tono técnico e inspirador, emojis con moderación.../i), { target: { value: 'No emojis' } });
    
    // Submit
    fireEvent.click(screen.getByRole('button', { name: /Guardar Estrategia/i }));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/agent/config/123',
        expect.objectContaining({
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${mockToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            account_type: 'personal',
            sector: 'Tech',
            purpose: 'Lead Generation',
            target_audience: 'SaaS Owners',
            style_guide: 'No emojis'
          })
        })
      );
    });

    await waitFor(() => {
      expect(screen.getByText(/Estrategia guardada correctamente/i)).toBeInTheDocument();
      expect(onSaveMock).toHaveBeenCalled();
    });
  });
});
