import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { ProfileAudit } from '../components/studio/ProfileAudit';
import { contentApi } from '../api/content';

vi.mock('../api/content', () => ({
  contentApi: {
    auditProfile: vi.fn(),
  },
}));

describe('ProfileAudit Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('does not render when isOpen is false', () => {
    const { container } = render(
      <ProfileAudit accountId={1} isOpen={false} onClose={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  test('renders loading state when opened', () => {
    (contentApi.auditProfile as any).mockReturnValue(new Promise(() => {}));
    render(<ProfileAudit accountId={1} isOpen={true} onClose={vi.fn()} />);
    expect(screen.getByText('Evaluando perfil frente a la rúbrica...')).toBeInTheDocument();
  });

  test('renders error state when API fails', async () => {
    (contentApi.auditProfile as any).mockRejectedValue(new Error('Audit failed'));
    render(<ProfileAudit accountId={1} isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Audit failed')).toBeInTheDocument();
    });
  });

  test('renders audit report with score, items, tips, and bio rewrite', async () => {
    const mockAudit = {
      score: 85,
      items: [
        {
          id: 'bio_clarity',
          label: 'Biografía clara con propuesta de valor',
          passed: true,
          weight: 25,
          tip: null,
        },
        {
          id: 'cta_link',
          label: 'Enlace en bio o llamada a la acción',
          passed: false,
          weight: 20,
          tip: 'Añade un enlace directo a tu oferta principal o lead magnet',
        },
      ],
      bio_rewrite: 'Ayudo a creadores a monetizar su audiencia en 90 días | Guía gratis 👇',
    };

    (contentApi.auditProfile as any).mockResolvedValue(mockAudit);
    const handleClose = vi.fn();

    render(<ProfileAudit accountId={1} isOpen={true} onClose={handleClose} />);

    await waitFor(() => {
      expect(screen.getByTestId('profile-audit-modal')).toBeInTheDocument();
    });

    // Score
    expect(screen.getByText('85/100')).toBeInTheDocument();
    expect(screen.getByText('Puntos de la rúbrica (2)')).toBeInTheDocument();

    // Items
    expect(screen.getByText('Biografía clara con propuesta de valor')).toBeInTheDocument();
    expect(screen.getByText('Enlace en bio o llamada a la acción')).toBeInTheDocument();
    expect(
      screen.getByText('Añade un enlace directo a tu oferta principal o lead magnet')
    ).toBeInTheDocument();

    // Bio rewrite
    expect(screen.getByText('Bio sugerida')).toBeInTheDocument();
    expect(
      screen.getByText('Ayudo a creadores a monetizar su audiencia en 90 días | Guía gratis 👇')
    ).toBeInTheDocument();

    // Close button
    const closeBtn = screen.getByRole('button', { name: /cerrar/i });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
