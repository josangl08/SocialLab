import { vi } from 'vitest';

export interface MockRoute {
  method?: string;
  /** Subcadena o expresión que debe contener la URL. */
  url: string | RegExp;
  response: unknown | ((body: unknown) => unknown);
  status?: number;
}

export interface RecordedCall { method: string; url: string; body: unknown }

/** Sustituye fetch por una tabla de rutas; devuelve las llamadas hechas. */
export function mockFetch(routes: MockRoute[]): RecordedCall[] {
  const calls: RecordedCall[] = [];
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string, init?: RequestInit) => {
    const method = (init?.method ?? 'GET').toUpperCase();
    const body = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined;
    calls.push({ method, url, body });
    const route = routes.find(r =>
      (r.method ?? 'GET').toUpperCase() === method
      && (typeof r.url === 'string' ? url.includes(r.url) : r.url.test(url))
    );
    const status = route?.status ?? (route ? 200 : 404);
    const payload = route
      ? (typeof route.response === 'function' ? (route.response as (b: unknown) => unknown)(body) : route.response)
      : { detail: 'not mocked' };
    return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(payload) });
  });
  return calls;
}
