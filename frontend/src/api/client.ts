const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (Array.isArray(body?.detail)) {
      return body.detail.map((e: { msg: string }) => e.msg).join('; ');
    }
    return body?.detail ?? 'Error desconocido';
  } catch {
    return 'Error desconocido';
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('authToken');
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

function jsonRequest<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  return request<T>(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export const apiClient = {
  get: <T>(path: string, options?: { signal?: AbortSignal }) => request<T>(path, options),
  post: <T>(path: string, body?: unknown) => jsonRequest<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => jsonRequest<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => jsonRequest<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  postForm: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: 'POST', body: formData }),
  putForm: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: 'PUT', body: formData }),
  postUrlEncoded: <T>(path: string, params: URLSearchParams) =>
    request<T>(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params.toString(),
    }),
  getUrl: (path: string) => `${BASE_URL}${path}`,
};
