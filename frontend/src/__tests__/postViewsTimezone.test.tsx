import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import MediaLightbox from '../components/media/MediaLightbox';
import type { Post } from '../types';
import { toDatetimeLocalValue, fromWallClock, formatInZones } from '../utils/timezone';

describe('Vistas secundarias con zonas horarias (AD-6, AD-9, AD-10)', () => {
  const sampleIso = '2026-10-14T18:00:00Z';

  test('formatInZones muestra fecha/hora en la zona principal y secundaria', () => {
    const formatted = formatInZones(sampleIso, {
      primary: 'Europe/Madrid',
      secondary: 'Asia/Kuching',
    });
    // Miércoles 14 a las 20:00 Madrid y Jueves 15 a las 02:00 Kuching
    expect(formatted).toContain('14 · 20:00 Madrid');
    expect(formatted).toContain('15 · 02:00 Kuching');
  });

  test('toDatetimeLocalValue inicializa el input en la hora de pared de la cuenta', () => {
    // Para 18:00 UTC con cuenta en Europe/Madrid (UTC+2) -> "2026-10-14T20:00"
    const localVal = toDatetimeLocalValue(sampleIso, 'Europe/Madrid');
    expect(localVal).toBe('2026-10-14T20:00');

    // Para 18:00 UTC con cuenta en Asia/Kuching (UTC+8) -> "2026-10-15T02:00"
    const kuchingVal = toDatetimeLocalValue(sampleIso, 'Asia/Kuching');
    expect(kuchingVal).toBe('2026-10-15T02:00');
  });

  test('fromWallClock convierte el valor editado de pared a UTC ISO al guardar', () => {
    // El usuario selecciona 2026-10-14 20:00 en Madrid -> debe guardarse como 18:00 UTC
    const dateInput = new Date(2026, 9, 14, 20, 0, 0);
    const utcIso = fromWallClock(dateInput, 'Europe/Madrid');
    expect(utcIso).toBe('2026-10-14T18:00:00.000Z');

    // Cruzando el cambio de horario (26-oct-2026 20:00 Madrid, CET UTC+1) -> 19:00 UTC
    const dstDateInput = new Date(2026, 9, 26, 20, 0, 0);
    const dstUtcIso = fromWallClock(dstDateInput, 'Europe/Madrid');
    expect(dstUtcIso).toBe('2026-10-26T19:00:00.000Z');
  });

  test('MediaLightbox muestra fecha en la zona cuando se proporciona la zona de la cuenta', () => {
    const testPost: Post = {
      id: 53946,
      user_id: 'u1',
      content: 'Contenido test',
      media_url: 'https://s.test/photo.jpg',
      post_type: 'post',
      status: 'scheduled',
      scheduled_at: sampleIso,
      created_at: '2026-10-01T10:00:00Z',
    };

    render(
      <MediaLightbox
        posts={[testPost]}
        startIndex={0}
        token="tok"
        onClose={vi.fn()}
        onDetails={vi.fn()}
        zonesFor={() => ({ primary: 'Europe/Madrid', secondary: 'Asia/Kuching' })}
      />
    );

    expect(screen.getByTestId('media-lightbox')).toBeInTheDocument();
    expect(screen.getByTestId('lightbox-date')).toHaveTextContent('Mié 14 · 20:00 Madrid · Jue 15 · 02:00 Kuching');
  });
});
