import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import FormatEditor from '../components/studio/FormatEditor';

vi.mock('../api/content', () => ({
  contentApi: { getHookFormulas: () => Promise.resolve([]) },
}));

describe('FormatEditor en la zona de la cuenta', () => {
  test('guarda la fecha del campo interpretada en la zona de la cuenta', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <FormatEditor
        format="post"
        onFormatChange={vi.fn()}
        caption="Caption"
        onCaptionChange={vi.fn()}
        mediaFile={null}
        onMediaFileChange={vi.fn()}
        mediaUrl="https://s.test/a.jpg"
        scheduledAt="2030-10-15T18:00"
        onScheduledAtChange={vi.fn()}
        timezone="Europe/Madrid"
        strategyMode="personal_storyline"
        hasTelegram={false}
        onSave={onSave}
      />
    );

    expect(screen.getByTestId('schedule-zone-hint')).toHaveTextContent('Hora de Madrid');
    fireEvent.click(screen.getByRole('button', { name: /Programar/i }));

    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(onSave.mock.calls[0][0].scheduledAt).toBe('2030-10-15T16:00:00.000Z');
  });
});
