import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import { RioDeInfluencia } from '../rio/RioDeInfluencia';
import type { Source } from '../shared/types';

const sources: Source[] = [
  { key: 'strategy', label: 'Estrategia', kind: 'strategy', count: 5 },
  { key: 'campaign', label: 'Campaña', kind: 'campaign', count: 4 },
  { key: 'rule:Tono', label: 'Tono', kind: 'rule', count: 3 },
  { key: 'rule:Formato', label: 'Formato', kind: 'rule', count: 1, conflict: true },
];

describe('RioDeInfluencia', () => {
  test('draws a label per source with its count', () => {
    render(
      <RioDeInfluencia
        sources={sources}
        totalDecisions={5}
        outputs={[{ key: 'out:post', label: '3 posts', color: '#ec4899', n: 3 }]}
        activeSourceKey={null}
        onSelectSource={() => {}}
      />,
    );
    expect(screen.getByText(/Estrategia 5/)).toBeInTheDocument();
    expect(screen.getByText(/⚠ Formato 1/)).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument(); // hub count
  });

  test('clicking a source label fires onSelectSource with its key', () => {
    const onSelect = vi.fn();
    render(
      <RioDeInfluencia
        sources={sources}
        totalDecisions={5}
        outputs={[]}
        activeSourceKey={null}
        onSelectSource={onSelect}
      />,
    );
    fireEvent.click(screen.getByText(/Tono 3/));
    expect(onSelect).toHaveBeenCalledWith('rule:Tono');
  });

  test('clicking an output ribbon fires onSelectSource with its out: key', () => {
    const onSelect = vi.fn();
    render(
      <RioDeInfluencia
        sources={sources}
        totalDecisions={5}
        outputs={[
          { key: 'out:post', label: '3 posts', color: '#ec4899', n: 3 },
          { key: 'out:suggestion', label: '2 sugerencias', color: '#818cf8', n: 2 },
        ]}
        activeSourceKey={null}
        onSelectSource={onSelect}
      />,
    );
    fireEvent.click(screen.getByText('2 sugerencias'));
    expect(onSelect).toHaveBeenCalledWith('out:suggestion');
  });
});
