import { describe, test, expect } from 'vitest';
import {
  browserTimezone,
  effectiveTimezone,
  toWallClock,
  fromWallClock,
  toDatetimeLocalValue,
  formatInZones,
  zoneLabel,
  fromDatetimeLocalValue,
  accountZones,
} from '../utils/timezone';

describe('utils/timezone', () => {
  test('browserTimezone devuelve un string IANA o UTC', () => {
    const tz = browserTimezone();
    expect(typeof tz).toBe('string');
    expect(tz.length).toBeGreaterThan(0);
  });

  test('effectiveTimezone: primary_timezone si existe, de lo contrario zona del navegador', () => {
    expect(effectiveTimezone({ primary_timezone: 'Europe/Madrid' })).toBe('Europe/Madrid');
    expect(effectiveTimezone({ primary_timezone: '' })).toBe(browserTimezone());
    expect(effectiveTimezone({ primary_timezone: null })).toBe(browserTimezone());
    expect(effectiveTimezone(null)).toBe(browserTimezone());
    expect(effectiveTimezone(undefined)).toBe(browserTimezone());
  });

  test('ida y vuelta UTC ↔ hora de pared (roundtrip)', () => {
    // 2026-10-14 18:00 UTC en Europe/Madrid (+2 CEST) -> 20:00 hora de pared
    const utcIso = '2026-10-14T18:00:00.000Z';
    const tz = 'Europe/Madrid';

    const wallClock = toWallClock(utcIso, tz);
    expect(wallClock.getFullYear()).toBe(2026);
    expect(wallClock.getMonth()).toBe(9); // Octubre (0-indexed)
    expect(wallClock.getDate()).toBe(14);
    expect(wallClock.getHours()).toBe(20);
    expect(wallClock.getMinutes()).toBe(0);

    const backToUtc = fromWallClock(wallClock, tz);
    expect(backToUtc).toBe(utcIso);
  });

  test('día distinto entre zonas para el mismo post', () => {
    // El post 53946: 2026-10-14T18:00:00Z
    // En Europe/Madrid (UTC+2) es Miércoles 14 a las 20:00
    // En Asia/Kuching (UTC+8) es Jueves 15 a las 02:00
    const utcIso = '2026-10-14T18:00:00Z';

    const madridWall = toWallClock(utcIso, 'Europe/Madrid');
    expect(madridWall.getDate()).toBe(14);
    expect(madridWall.getHours()).toBe(20);

    const kuchingWall = toWallClock(utcIso, 'Asia/Kuching');
    expect(kuchingWall.getDate()).toBe(15);
    expect(kuchingWall.getHours()).toBe(2);
  });

  test('cambio de horario 25-oct-2026 en Madrid (DST CEST -> CET)', () => {
    // Antes del cambio: 24-oct-2026 18:00 UTC -> 20:00 CEST (+2)
    const beforeWall = toWallClock('2026-10-24T18:00:00Z', 'Europe/Madrid');
    expect(beforeWall.getHours()).toBe(20);

    // Después del cambio: 26-oct-2026 18:00 UTC -> 19:00 CET (+1)
    const afterWall = toWallClock('2026-10-26T18:00:00Z', 'Europe/Madrid');
    expect(afterWall.getHours()).toBe(19);

    // Conservación de hora de pared al arrastrar/guardar:
    // 20:00 el 24-oct -> 18:00 UTC
    const localBefore = new Date(2026, 9, 24, 20, 0, 0);
    expect(fromWallClock(localBefore, 'Europe/Madrid')).toBe('2026-10-24T18:00:00.000Z');

    // 20:00 el 26-oct -> 19:00 UTC
    const localAfter = new Date(2026, 9, 26, 20, 0, 0);
    expect(fromWallClock(localAfter, 'Europe/Madrid')).toBe('2026-10-26T19:00:00.000Z');
  });

  test('toDatetimeLocalValue formatea YYYY-MM-DDTHH:mm en la zona indicada', () => {
    const value = toDatetimeLocalValue('2026-10-14T18:00:00Z', 'Europe/Madrid');
    expect(value).toBe('2026-10-14T20:00');

    const kuchingVal = toDatetimeLocalValue('2026-10-14T18:00:00Z', 'Asia/Kuching');
    expect(kuchingVal).toBe('2026-10-15T02:00');
  });

  test('zoneLabel extrae el nombre legible', () => {
    expect(zoneLabel('Europe/Madrid')).toBe('Madrid');
    expect(zoneLabel('Asia/Kuching')).toBe('Kuching');
    expect(zoneLabel('America/New_York')).toBe('New York');
    expect(zoneLabel('UTC')).toBe('UTC');
  });

  test('formatInZones muestra principal y secundaria legible (AD-10)', () => {
    const iso = '2026-10-14T18:00:00Z';
    const text = formatInZones(iso, {
      primary: 'Europe/Madrid',
      secondary: 'Asia/Kuching',
    });

    // Debe contener día y hora en Madrid y día y hora en Kuching
    expect(text).toContain('14 · 20:00 Madrid');
    expect(text).toContain('15 · 02:00 Kuching');
    expect(text).toContain('·');
  });

  test('formatInZones sin secundaria o si son iguales solo muestra una vez', () => {
    const iso = '2026-10-14T18:00:00Z';
    const textOnlyPrimary = formatInZones(iso, { primary: 'Europe/Madrid', secondary: null });
    expect(textOnlyPrimary).toContain('14 · 20:00 Madrid');
    expect(textOnlyPrimary).not.toContain('Kuching');

    const textSame = formatInZones(iso, { primary: 'Europe/Madrid', secondary: 'Europe/Madrid' });
    expect(textSame.split('Europe/Madrid').length - 1).toBeLessThanOrEqual(1);
  });

  test('fromDatetimeLocalValue interpreta el valor del input en la zona indicada', () => {
    expect(fromDatetimeLocalValue('2026-10-15T18:00', 'Europe/Madrid')).toBe('2026-10-15T16:00:00.000Z');
    expect(fromDatetimeLocalValue('2026-10-26T18:00', 'Europe/Madrid')).toBe('2026-10-26T17:00:00.000Z');
  });

  test('accountZones devuelve la zona efectiva y la secundaria de la cuenta', () => {
    const accounts = [{ id: 7, primary_timezone: 'Europe/Madrid', secondary_timezone: 'Asia/Kuching' }];
    expect(accountZones(accounts, 7)).toEqual({ primary: 'Europe/Madrid', secondary: 'Asia/Kuching' });
    expect(accountZones(accounts, 8)).toEqual({ primary: browserTimezone(), secondary: null });
    expect(accountZones(undefined, 7)).toEqual({ primary: browserTimezone(), secondary: null });
  });
});
