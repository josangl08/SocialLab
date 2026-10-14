import { TZDate } from '@date-fns/tz';
import type { InstagramAccount } from '../types';

/**
 * Devuelve la zona horaria del navegador (ej. 'Europe/Madrid', 'Asia/Kuching').
 */
export function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

/**
 * Determina la zona efectiva para el frontend (AD-2):
 * primary_timezone ?? zona del navegador.
 */
export function effectiveTimezone(account?: Pick<InstagramAccount, 'primary_timezone'> | null): string {
  if (account?.primary_timezone && account.primary_timezone.trim()) {
    return account.primary_timezone.trim();
  }
  return browserTimezone();
}

/**
 * Convierte un instante (ISO string o Date) en un Date local cuyos componentes
 * (año, mes, día, hora, minuto, segundo) corresponden a la hora de pared en la zona indicada (AD-5).
 * Usado para alimentar react-big-calendar sin importar la zona del navegador.
 */
export function toWallClock(isoOrDate: string | Date, tz: string): Date {
  const target = typeof isoOrDate === 'string' ? new TZDate(isoOrDate, tz) : new TZDate(isoOrDate, tz);
  return new Date(
    target.getFullYear(),
    target.getMonth(),
    target.getDate(),
    target.getHours(),
    target.getMinutes(),
    target.getSeconds(),
    target.getMilliseconds()
  );
}

/**
 * Convierte una Date de hora de pared en la zona indicada de vuelta a un instante UTC en formato ISO 8601 (AD-5).
 */
export function fromWallClock(date: Date, tz: string): string {
  const target = new TZDate(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
    date.getHours(),
    date.getMinutes(),
    date.getSeconds(),
    date.getMilliseconds(),
    tz
  );
  return new Date(target.getTime()).toISOString();
}

/**
 * Convierte el valor de un input datetime-local (YYYY-MM-DDTHH:mm), leído como hora de pared
 * en la zona indicada, a un instante UTC en ISO 8601 (AD-9).
 */
export function fromDatetimeLocalValue(value: string, tz: string): string {
  return fromWallClock(new Date(value), tz);
}

/**
 * Zonas (principal efectiva y secundaria) de la cuenta indicada (AD-6).
 */
export function accountZones(
  accounts: Pick<InstagramAccount, 'id' | 'primary_timezone' | 'secondary_timezone'>[] | undefined,
  accountId: number | null | undefined
): { primary: string; secondary: string | null } {
  const acc = accounts?.find(a => a.id === accountId);
  return { primary: effectiveTimezone(acc), secondary: acc?.secondary_timezone ?? null };
}

/**
 * Formatea un instante en el formato requerido por inputs datetime-local (YYYY-MM-DDTHH:mm)
 * según la hora de pared en la zona indicada (AD-9).
 */
export function toDatetimeLocalValue(isoOrDate: string | Date, tz: string): string {
  const wall = toWallClock(isoOrDate, tz);
  const pad = (n: number) => String(n).padStart(2, '0');
  const year = wall.getFullYear();
  const month = pad(wall.getMonth() + 1);
  const day = pad(wall.getDate());
  const hours = pad(wall.getHours());
  const minutes = pad(wall.getMinutes());
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

/**
 * Devuelve la etiqueta legible de una zona horaria (ej. "Europe/Madrid" -> "Madrid", "Asia/Kuching" -> "Kuching").
 */
export function zoneLabel(tz: string): string {
  if (!tz) return 'UTC';
  const last = tz.split('/').pop() || tz;
  return last.replace(/_/g, ' ');
}

function formatSingleZone(date: Date, tz: string): string {
  const target = new TZDate(date, tz);
  const weekdayShort = new Intl.DateTimeFormat('es-ES', { timeZone: tz, weekday: 'short' }).format(target);
  const day = target.getDate();
  const pad = (n: number) => String(n).padStart(2, '0');
  const time = `${pad(target.getHours())}:${pad(target.getMinutes())}`;
  const capWeekday = weekdayShort.charAt(0).toUpperCase() + weekdayShort.slice(1).replace('.', '');
  return `${capWeekday} ${day} · ${time} ${zoneLabel(tz)}`;
}

/**
 * Formatea una fecha en su zona principal y opcionalmente secundaria (AD-10).
 * Ejemplo: "Mié 14 · 20:00 Madrid · Jue 15 · 02:00 Kuching"
 */
export function formatInZones(
  isoOrDate: string | Date,
  zones: { primary?: string | null; secondary?: string | null }
): string {
  if (!isoOrDate) return '';
  const date = typeof isoOrDate === 'string' ? new Date(isoOrDate) : isoOrDate;
  if (isNaN(date.getTime())) return '';

  const primaryTz = zones.primary?.trim() || browserTimezone();
  const primaryText = formatSingleZone(date, primaryTz);

  const secondaryTz = zones.secondary?.trim();
  if (secondaryTz && secondaryTz !== primaryTz) {
    const secondaryText = formatSingleZone(date, secondaryTz);
    return `${primaryText} · ${secondaryText}`;
  }

  return primaryText;
}
