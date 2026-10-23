import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import { StrategyBrandTab } from '../components/strategy/StrategyBrandTab';
import { DEFAULT_CONFIG } from '../components/strategy/strategyOptions';
import type { AgentStrategyConfig } from '../types';

const DRAFT: AgentStrategyConfig = {
  ...DEFAULT_CONFIG,
  account_type: 'personal',
  default_tone: 'casual',
  best_times: ['20:00'],
  scheduling_mode: 'flexible',
  banned_phrases: ['sinergia'],
};

describe('StrategyBrandTab', () => {
  test('changing account type shows the preset diff before applying', () => {
    const onChange = vi.fn();
    render(<StrategyBrandTab draft={DRAFT} onChange={onChange} />);

    fireEvent.click(screen.getByRole('button', { name: /Profesional.*Marca/ }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('Tono')).toBeInTheDocument();
    expect(within(dialog).getByText('casual')).toBeInTheDocument();
    expect(within(dialog).getByText('professional')).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Aplicar preset' }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
      account_type: 'professional', default_tone: 'professional', scheduling_mode: 'fixed',
    }));
  });

  test('"Solo cambiar el tipo" leaves the other fields untouched', () => {
    const onChange = vi.fn();
    render(<StrategyBrandTab draft={DRAFT} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /Profesional.*Marca/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Solo cambiar el tipo' }));
    expect(onChange).toHaveBeenCalledWith({ account_type: 'professional' });
  });

  test('anti-slop toggle and banned phrases', () => {
    const onChange = vi.fn();
    render(<StrategyBrandTab draft={DRAFT} onChange={onChange} />);
    expect(screen.getByText('sinergia')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText(/Limpieza automática de lenguaje sintético/));
    expect(onChange).toHaveBeenCalledWith({ humanizer_enabled: false });

    const input = screen.getByPlaceholderText('Nuevo término vetado...');
    fireEvent.change(input, { target: { value: 'holístico' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith({ banned_phrases: ['sinergia', 'holístico'] });
  });
});
