import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { AccountTimezoneSettings } from '../components/accounts/AccountTimezoneSettings';
import { apiClient, ApiError } from '../api/client';
import type { InstagramAccount } from '../types';

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return {
    ...actual,
    apiClient: {
      put: vi.fn(),
    },
  };
});

describe('AccountTimezoneSettings Component', () => {
  const mockAccount: InstagramAccount = {
    id: 7,
    username: 'test_account',
    account_name: 'Test Account',
    primary_timezone: null,
    secondary_timezone: null,
    detected_timezone: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('por defecto muestra el placeholder con la zona del navegador y Ninguna en secundaria', () => {
    render(<AccountTimezoneSettings account={mockAccount} />);

    const primaryInput = screen.getByTestId('input-primary-tz') as HTMLInputElement;
    const secondaryInput = screen.getByTestId('input-secondary-tz') as HTMLInputElement;

    expect(primaryInput.value).toBe('');
    expect(primaryInput.placeholder).toMatch(/Navegador \(.+\)/);

    expect(secondaryInput.value).toBe('');
    expect(secondaryInput.placeholder).toBe('Ninguna');
  });

  test('muestra valores existentes cuando la cuenta tiene zonas configuradas', () => {
    const configuredAccount: InstagramAccount = {
      ...mockAccount,
      primary_timezone: 'Europe/Madrid',
      secondary_timezone: 'Asia/Kuching',
    };

    render(<AccountTimezoneSettings account={configuredAccount} />);

    const primaryInput = screen.getByTestId('input-primary-tz') as HTMLInputElement;
    const secondaryInput = screen.getByTestId('input-secondary-tz') as HTMLInputElement;

    expect(primaryInput.value).toBe('Europe/Madrid');
    expect(secondaryInput.value).toBe('Asia/Kuching');
  });

  test('guardar envía las zonas al endpoint /config y llama onUpdate', async () => {
    vi.mocked(apiClient.put).mockResolvedValue({ success: true });
    const onUpdateMock = vi.fn();

    render(<AccountTimezoneSettings account={mockAccount} onUpdate={onUpdateMock} />);

    const primaryInput = screen.getByTestId('input-primary-tz');
    fireEvent.change(primaryInput, { target: { value: 'Europe/Madrid' } });

    const secondaryInput = screen.getByTestId('input-secondary-tz');
    fireEvent.change(secondaryInput, { target: { value: 'Asia/Kuching' } });

    const saveBtn = screen.getByTestId('btn-save-tz');
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith('/instagram/accounts/7/config', {
        primary_timezone: 'Europe/Madrid',
        secondary_timezone: 'Asia/Kuching',
      });
    });

    expect(onUpdateMock).toHaveBeenCalledWith({
      primary_timezone: 'Europe/Madrid',
      secondary_timezone: 'Asia/Kuching',
    });

    expect(screen.getByTestId('tz-success-msg')).toBeInTheDocument();
  });

  test('restablecer envía null para ambas zonas y limpia los inputs', async () => {
    vi.mocked(apiClient.put).mockResolvedValue({ success: true });
    const onUpdateMock = vi.fn();

    const configuredAccount: InstagramAccount = {
      ...mockAccount,
      primary_timezone: 'Europe/Madrid',
      secondary_timezone: 'Asia/Kuching',
    };

    render(<AccountTimezoneSettings account={configuredAccount} onUpdate={onUpdateMock} />);

    const resetBtn = screen.getByTestId('btn-reset-tz');
    fireEvent.click(resetBtn);

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith('/instagram/accounts/7/config', {
        primary_timezone: null,
        secondary_timezone: null,
      });
    });

    const primaryInput = screen.getByTestId('input-primary-tz') as HTMLInputElement;
    const secondaryInput = screen.getByTestId('input-secondary-tz') as HTMLInputElement;

    expect(primaryInput.value).toBe('');
    expect(secondaryInput.value).toBe('');

    expect(onUpdateMock).toHaveBeenCalledWith({
      primary_timezone: null,
      secondary_timezone: null,
    });
  });

  test('muestra el mensaje de error 422 de la API de forma visible', async () => {
    vi.mocked(apiClient.put).mockRejectedValue(
      new ApiError(422, 'Zona horaria no encontrada en la base IANA: Invalida/Falsa')
    );

    render(<AccountTimezoneSettings account={mockAccount} />);

    const primaryInput = screen.getByTestId('input-primary-tz');
    fireEvent.change(primaryInput, { target: { value: 'Invalida/Falsa' } });

    const saveBtn = screen.getByTestId('btn-save-tz');
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByTestId('tz-error-msg')).toBeInTheDocument();
    });

    expect(screen.getByTestId('tz-error-msg')).toHaveTextContent(
      'Zona horaria no encontrada en la base IANA: Invalida/Falsa'
    );
  });
});
