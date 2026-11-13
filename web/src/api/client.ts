export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(path, {
    credentials: 'include',
    ...init,
    headers: { 'content-type': 'application/json', ...(init.headers ?? {}) },
  })
  if (r.status === 401 && !path.startsWith('/api/login') && !path.startsWith('/api/me')) {
    if (!location.pathname.startsWith('/login')) location.assign('/login')
  }
  if (!r.ok) throw new ApiError(r.status, await r.text())
  if (r.status === 204) return undefined as T
  return r.json() as Promise<T>
}

/** Pull a readable cause out of an ApiError body (FastAPI sends {"detail": string | [{msg}]}). */
export function errorDetail(e: unknown): string {
  if (!(e instanceof ApiError)) return 'تعذّر الاتصال بالخادم'
  try {
    const d = JSON.parse(e.message)?.detail
    if (typeof d === 'string') return d
    if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg)
  } catch { /* not json */ }
  return e.message || 'خطأ غير معروف'
}
