import type { ListingCard } from './types'

export type ChatEvent =
  | { type: 'thread'; thread_id: string }
  | { type: 'token'; text: string }
  | { type: 'tool'; name: string }
  | { type: 'listings'; items: ListingCard[] }
  | { type: 'prefs_changed' }
  /** `retryable` is set by the client for local failures (503/422); server events leave it unset. */
  | { type: 'error'; message: string; retryable?: boolean }
  | { type: 'done' }

export interface ChatThreadSummary { id: string; title: string; updated_at: string }
export interface ChatHistoryMessage { role: 'user' | 'assistant'; text: string; listings?: ListingCard[] }
export interface ChatThread { id: string; title: string; messages: ChatHistoryMessage[] }

export const BUDGET_MESSAGE = 'تم الوصول إلى الحد الشهري لاستخدام المساعد'
export const NOT_CONFIGURED_MESSAGE = 'المساعد غير مفعّل بعد. اطلبوا من مسؤول النظام إضافة مفتاح الخدمة.'

/** Split an SSE byte-stream text into complete `data: <json>` events; the unfinished tail is returned as `rest`. */
export function parseSSE(chunk: string, buffer: string): { events: ChatEvent[]; rest: string } {
  const parts = (buffer + chunk).replace(/\r\n/g, '\n').split('\n\n')
  const rest = parts.pop() ?? ''
  const events: ChatEvent[] = []
  for (const part of parts) {
    for (const line of part.split('\n')) {
      if (!line.startsWith('data: ')) continue
      try { events.push(JSON.parse(line.slice(6)) as ChatEvent) } catch { /* malformed event: skip */ }
    }
  }
  return { events, rest }
}

/**
 * POST a message and stream the reply. Resolves after `done`/`error`.
 * Rejects (so the caller can offer retry) on network failure or a connection that drops mid-stream,
 * and with an AbortError when `signal` aborts.
 */
export async function streamChat(
  message: string, threadId: string | null, onEvent: (e: ChatEvent) => void, signal?: AbortSignal,
): Promise<void> {
  const r = await fetch('/api/chat', {
    method: 'POST', credentials: 'include', signal,
    headers: { 'content-type': 'application/json' }, body: JSON.stringify({ message, thread_id: threadId }),
  })
  if (r.status === 401) { location.assign('/login'); return }
  if (r.status === 503) { onEvent({ type: 'error', message: NOT_CONFIGURED_MESSAGE, retryable: false }); return }
  if (r.status === 422) { onEvent({ type: 'error', message: 'الرسالة فارغة أو أطول من المسموح', retryable: false }); return }
  if (!r.ok || !r.body) { onEvent({ type: 'error', message: 'تعذّر الاتصال بالمساعد' }); return }
  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let rest = ''
  let finished = false
  const handle = (e: ChatEvent) => { if (e.type === 'done' || e.type === 'error') finished = true; onEvent(e) }
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    const out = parseSSE(decoder.decode(value, { stream: true }), rest)
    rest = out.rest
    out.events.forEach(handle)
  }
  if (!finished) throw new Error('chat stream interrupted')
}
