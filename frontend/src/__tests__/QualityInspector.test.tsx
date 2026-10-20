import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import QualityInspector from '../components/studio/QualityInspector';
import { contentApi } from '../api/content';
import type { QualityReport } from '../types';

vi.mock('../api/content', () => ({
  contentApi: {
    lintCaption: vi.fn(),
  },
}));

describe('QualityInspector Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockReport: QualityReport = {
    visible_text: 'Gran partido del equipo ayer en casa.',
    visible_length: 37,
    truncated: false,
    hashtag_count: 3,
    hashtag_limit: 5,
    hashtags_over_limit: [],
    keywords_missing_in_visible: [],
    slop: {
      score: 0,
      hits: [],
      invisible_chars: 0,
      em_dash_count: 0,
    },
    hook: {
      formula_id: 1,
      formula_name: 'Pregunta provocadora',
      score: 85,
      dealbreakers: [],
    },
    warnings: [],
  };

  test('muestra contador de 125 caracteres visibles y corte en cliente', () => {
    const shortCaption = 'Texto breve';
    const { rerender } = render(<QualityInspector caption={shortCaption} />);

    expect(screen.getByTestId('char-counter')).toHaveTextContent('11/125 chars');
    expect(screen.getByText('Texto breve')).toBeInTheDocument();

    const longCaption = 'A'.repeat(140);
    rerender(<QualityInspector caption={longCaption} />);

    expect(screen.getByTestId('char-counter')).toHaveTextContent('125/125 chars');
    expect(screen.getByText(/… más/)).toBeInTheDocument();
  });

  test('ejecuta lint con debounce de 400 ms y actualiza métricas', async () => {
    (contentApi.lintCaption as any).mockResolvedValue(mockReport);

    render(<QualityInspector caption="Gran partido del equipo ayer en casa." />);

    // Inmediatamente no se debe haber llamado antes de 400ms
    expect(contentApi.lintCaption).not.toHaveBeenCalled();

    // Esperar los 400ms del debounce
    await act(async () => {
      await new Promise((r) => setTimeout(r, 450));
    });

    expect(contentApi.lintCaption).toHaveBeenCalledTimes(1);

    await waitFor(() => {
      expect(screen.getByTestId('hashtag-count')).toHaveTextContent('3/5');
      expect(screen.getByTestId('voice-purity')).toHaveTextContent('100%');
      expect(screen.getByTestId('hook-score')).toHaveTextContent('85/100');
    });
  });

  test('muestra avisos cuando hay más de 5 hashtags y léxico sintético', async () => {
    const warningReport: QualityReport = {
      visible_text: 'Descubre este increíble contenido.',
      visible_length: 34,
      truncated: false,
      hashtag_count: 8,
      hashtag_limit: 5,
      hashtags_over_limit: ['#seis', '#siete', '#ocho'],
      keywords_missing_in_visible: [],
      slop: {
        score: 30,
        hits: [{ term: 'delve into', index: 10, suggestion: 'explorar' }],
        invisible_chars: 0,
        em_dash_count: 0,
      },
      hook: {
        formula_id: null,
        formula_name: null,
        score: 20,
        dealbreakers: ['Stop scrolling'],
      },
      warnings: [
        { code: 'HASHTAGS_OVER_LIMIT', message: '8 / 5 máx. Sobran: #seis #siete #ocho' },
      ],
    };

    (contentApi.lintCaption as any).mockResolvedValue(warningReport);

    render(<QualityInspector caption="Descubre este increíble contenido." />);

    await act(async () => {
      await new Promise((r) => setTimeout(r, 450));
    });

    await waitFor(() => {
      expect(screen.getByTestId('hashtag-count')).toHaveTextContent('8/5');
      expect(screen.getByText('Exceso')).toBeInTheDocument();
      expect(screen.getByText(/delve into/)).toBeInTheDocument();
      expect(screen.getByText(/Stop scrolling/)).toBeInTheDocument();
      expect(screen.getByText('8 / 5 máx. Sobran: #seis #siete #ocho')).toBeInTheDocument();
    });
  });

  test('renderiza BeatSheet cuando el formato es reel y hay beats', () => {
    const beats = [
      { label: 'Hook', text: 'Mira esto', start_s: 0, end_s: 2.5, duration_s: 2.5 },
      { label: 'Desarrollo', text: 'Explicación larga', start_s: 2.5, end_s: 7.2, duration_s: 4.7, alert: 'OVER_4S' as const },
    ];

    render(
      <QualityInspector
        caption="Reel caption"
        format="reel"
        beats={beats}
        beatsTotalSeconds={7.2}
      />
    );

    expect(screen.getByText(/Beat Sheet \(Guion de Reel\)/i)).toBeInTheDocument();
    expect(screen.getByText('OVER_4S')).toBeInTheDocument();
    expect(screen.getByText('Total: 7.2s')).toBeInTheDocument();
  });
});
