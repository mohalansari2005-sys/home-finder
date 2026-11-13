import { afterEach, describe, expect, it, vi } from 'vitest'
import { parseSSE, streamChat, type ChatEvent } from './chat'

const enc = new TextEncoder()
const sseBody = (chunks: Uint8Array<ArrayBuffer>[]) =>
  new ReadableStream<Uint8Array<ArrayBuffer>>({ start(c) { chunks.forEach((x) => c.enqueue(x)); c.close() } })
const ev = (o: object) => `data: ${JSON.stringify(o)}\n\n`

afterEach(() => vi.unstubAllGlobals())

describe('parseSSE', () => {
  it('parses complete events and keeps partial rest', () => {
    const { events, rest } = parseSSE('data: {"type":"token","text":"مر"}\n\ndata: {"type":"tok', '')
    expect(events).toEqual([{ type: 'token', text: 'مر' }])
    expect(rest).toBe('data: {"type":"tok')
    const second = parseSSE('en","text":"حبا"}\n\n', rest)
    expect(second.events).toEqual([{ type: 'token', text: 'حبا' }])
    expect(second.rest).toBe('')
  })

  it('handles several events in one chunk and CRLF separators', () => {
    const { events } = parseSSE('data: {"type":"thread","thread_id":"t1"}\r\n\r\ndata: {"type":"done"}\r\n\r\n', '')
    expect(events).toEqual([{ type: 'thread', thread_id: 't1' }, { type: 'done' }])
  })

  it('ignores comments, non-data lines and malformed json', () => {
    const { events } = parseSSE(': ping\n\nevent: x\ndata: not-json\n\ndata: {"type":"done"}\n\n', '')
    expect(events).toEqual([{ type: 'done' }])
  })
})

describe('streamChat', () => {
  const collect = async (res: Partial<Response> | Error | DOMException, signal?: AbortSignal) => {
    vi.stubGlobal('fetch', vi.fn(async () => { if (res instanceof Error || res instanceof DOMException) throw res; return res }))
    const out: ChatEvent[] = []
    await streamChat('وش عندك؟', null, (e) => out.push(e), signal)
    return out
  }

  it('posts the message and emits events in order, even when a multibyte char is split across chunks', async () => {
    const bytes = enc.encode(ev({ type: 'thread', thread_id: 'a' }) + ev({ type: 'token', text: 'مرحبا' }) + ev({ type: 'done' }))
    const cut = bytes.indexOf(0xd9) + 1 // inside the first Arabic letter
    const out = await collect({ ok: true, status: 200, body: sseBody([bytes.slice(0, cut + 40), bytes.slice(cut + 40)]) })
    expect(out.map((e) => e.type)).toEqual(['thread', 'token', 'done'])
    expect(out[1]).toEqual({ type: 'token', text: 'مرحبا' })
    const call = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(call[0]).toBe('/api/chat')
    expect(JSON.parse(call[1].body)).toEqual({ message: 'وش عندك؟', thread_id: null })
  })

  it('maps 503 to a friendly non-retryable Arabic message', async () => {
    const out = await collect({ ok: false, status: 503, body: null })
    expect(out).toHaveLength(1)
    expect(out[0]).toMatchObject({ type: 'error', retryable: false })
    expect((out[0] as { message: string }).message).toMatch(/المساعد غير مفعّل بعد/)
  })

  it('maps other http failures to a retryable error', async () => {
    const out = await collect({ ok: false, status: 500, body: null })
    expect(out[0]).toMatchObject({ type: 'error', message: 'تعذّر الاتصال بالمساعد' })
  })

  it('rejects when the network fails so the caller can offer retry', async () => {
    await expect(collect(new TypeError('Failed to fetch'))).rejects.toThrow('Failed to fetch')
  })

  it('rejects with AbortError when aborted', async () => {
    const ctl = new AbortController()
    ctl.abort()
    await expect(collect(new DOMException('aborted', 'AbortError'), ctl.signal)).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('rejects when the stream ends without done or error (dropped connection)', async () => {
    const body = sseBody([enc.encode(ev({ type: 'thread', thread_id: 'a' }) + ev({ type: 'token', text: 'مر' }))])
    await expect(collect({ ok: true, status: 200, body })).rejects.toThrow(/interrupted/)
  })

  it('a budget error event is a clean terminal event', async () => {
    const msg = 'تم الوصول إلى الحد الشهري لاستخدام المساعد'
    const body = sseBody([enc.encode(ev({ type: 'thread', thread_id: 'a' }) + ev({ type: 'error', message: msg }) + ev({ type: 'done' }))])
    const out = await collect({ ok: true, status: 200, body })
    expect(out.map((e) => e.type)).toEqual(['thread', 'error', 'done'])
    expect(out[1]).toMatchObject({ message: msg })
  })
})
