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
