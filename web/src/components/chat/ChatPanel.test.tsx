import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ListingCard } from '../../api/types'
import { ChatPanel } from './ChatPanel'
import { ChatProvider } from './ChatProvider'

const enc = new TextEncoder()
const ev = (o: object) => enc.encode(`data: ${JSON.stringify(o)}\n\n`)
const listing = { id: 5, title: 'فيلا', property_type: 'villa', price: 1_850_000, district: 'النرجس', score: 86, photo_url: null } as ListingCard

/** A response whose body the test feeds event by event. */
function controlled() {
  let c!: ReadableStreamDefaultController<Uint8Array<ArrayBuffer>>
  const body = new ReadableStream<Uint8Array<ArrayBuffer>>({ start(x) { c = x } })
  return { response: { ok: true, status: 200, body } as unknown as Response, push: (o: object) => c.enqueue(ev(o)), close: () => c.close() }
}
const complete = (...events: object[]) => ({
  ok: true, status: 200,
  body: new ReadableStream<Uint8Array<ArrayBuffer>>({ start(c) { events.forEach((e) => c.enqueue(ev(e))); c.close() } }),
}) as unknown as Response

type Handler = (url: string, init?: RequestInit) => Response | Promise<Response>
function mockFetch(onChat: Handler) {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/chat') return onChat(url, init)
    if (url === '/api/chat/threads') return new Response(JSON.stringify([{ id: 't1', title: 'بيت قديم', updated_at: '2026-11-01T10:00:00Z' }]), { status: 200 })
    return new Response('{}', { status: 404 })
  })
  vi.stubGlobal('fetch', f)
  return f
}
const chatCalls = (f: ReturnType<typeof mockFetch>) => f.mock.calls.filter((c) => c[0] === '/api/chat')

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const spy = vi.spyOn(qc, 'invalidateQueries')
  render(
    <QueryClientProvider client={qc}><MemoryRouter><ChatProvider><ChatPanel variant="page" /></ChatProvider></MemoryRouter></QueryClientProvider>,
  )
  return { spy, box: () => screen.getByRole('textbox', { name: 'رسالتك' }) }
}

beforeEach(() => localStorage.clear())
afterEach(() => vi.unstubAllGlobals())

describe('ChatPanel', () => {
  it('shows suggestion chips on an empty thread and sends one when clicked', async () => {
    const f = mockFetch(() => complete({ type: 'thread', thread_id: 'a' }, { type: 'done' }))
    setup()
    await userEvent.click(screen.getByRole('button', { name: 'دوّر إعلانات جديدة' }))
    await waitFor(() => expect(chatCalls(f)).toHaveLength(1))
    expect(JSON.parse(chatCalls(f)[0][1]!.body as string).message).toBe('دوّر إعلانات جديدة')
    expect(screen.queryByRole('button', { name: 'غيّر الميزانية' })).toBeNull()
  })

  it('Enter submits, Shift+Enter inserts a newline, input is cleared and keeps focus', async () => {
    const f = mockFetch(() => complete({ type: 'done' }))
    const { box } = setup()
    await userEvent.type(box(), 'سطر أول{Shift>}{Enter}{/Shift}سطر ثان')
    expect(box()).toHaveValue('سطر أول\nسطر ثان')
    expect(chatCalls(f)).toHaveLength(0)
    await userEvent.keyboard('{Enter}')
    await waitFor(() => expect(chatCalls(f)).toHaveLength(1))
    expect(JSON.parse(chatCalls(f)[0][1]!.body as string)).toEqual({ message: 'سطر أول\nسطر ثان', thread_id: null })
    expect(box()).toHaveValue('')
    expect(box()).toHaveFocus()
    expect(screen.getByText(/سطر أول/)).toBeInTheDocument()
  })

  it('streams tokens progressively, shows stop while streaming and send again after done', async () => {
    const s = controlled()
    mockFetch(() => s.response)
    const { box } = setup()
    await userEvent.type(box(), 'هلا{Enter}')
    const log = screen.getByRole('log')
    expect(log).toHaveAttribute('aria-live', 'polite')
    expect(log).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('button', { name: 'إيقاف' })).toBeInTheDocument()
    s.push({ type: 'thread', thread_id: 't9' })
    s.push({ type: 'token', text: 'مر' })
    expect(await within(log).findByText('مر')).toBeInTheDocument()
    s.push({ type: 'token', text: 'حبا' })
    expect(await within(log).findByText('مرحبا')).toBeInTheDocument()
    expect(box()).toBeEnabled()
    s.push({ type: 'done' }); s.close()
    expect(await screen.findByRole('button', { name: 'إرسال' })).toBeInTheDocument()
    expect(log).toHaveAttribute('aria-busy', 'false')
    expect(localStorage.getItem('hf_thread')).toBe('t9')
  })

  it('shows the tool status pill with an Arabic label and falls back for unknown tools', async () => {
    const s = controlled()
    mockFetch(() => s.response)
    const { box } = setup()
    await userEvent.type(box(), 'ابحث{Enter}')
    s.push({ type: 'tool', name: 'search_listings' })
    expect(await screen.findByText('يبحث في العقارات…')).toBeInTheDocument()
    s.push({ type: 'tool', name: 'something_new' })
    expect(await screen.findByText('جارٍ العمل…')).toBeInTheDocument()
    s.push({ type: 'token', text: 'تم' })
    await waitFor(() => expect(screen.queryByText('جارٍ العمل…')).toBeNull())
    s.push({ type: 'done' }); s.close()
  })

  it('Stop aborts the request and keeps the partial answer', async () => {
    const s = controlled()
    const f = mockFetch((_u, init) => {
      init!.signal!.addEventListener('abort', () => { try { s.close() } catch { /* already closed */ } })
      return s.response
    })
    const { box } = setup()
    await userEvent.type(box(), 'هلا{Enter}')
    s.push({ type: 'token', text: 'جزء من الرد' })
    await screen.findByText('جزء من الرد')
    await userEvent.click(screen.getByRole('button', { name: 'إيقاف' }))
    expect((chatCalls(f)[0][1]!.signal as AbortSignal).aborted).toBe(true)
    expect(await screen.findByRole('button', { name: 'إرسال' })).toBeInTheDocument()
    expect(screen.getByText('جزء من الرد')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('a failed network request shows an inline error and retry re-sends the same message', async () => {
    let n = 0
    const f = mockFetch(() => { if (n++ === 0) throw new TypeError('Failed to fetch'); return complete({ type: 'token', text: 'وصلت' }, { type: 'done' }) })
    const { box } = setup()
    await userEvent.type(box(), 'وش عندك؟{Enter}')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('تعذّر الاتصال بالمساعد')
    await userEvent.click(within(alert).getByRole('button', { name: 'إعادة المحاولة' }))
    expect(await screen.findByText('وصلت')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getAllByText('وش عندك؟')).toHaveLength(1)
    expect(chatCalls(f).map((c) => JSON.parse(c[1]!.body as string).message)).toEqual(['وش عندك؟', 'وش عندك؟'])
  })

  it('503 shows a friendly not-set-up message without a retry button', async () => {
    mockFetch(() => new Response(JSON.stringify({ detail: 'no key' }), { status: 503 }))
    const { box } = setup()
    await userEvent.type(box(), 'هلا{Enter}')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('المساعد غير مفعّل بعد')
    expect(within(alert).queryByRole('button')).toBeNull()
  })

  it('budget exhausted is displayed as-is without retry or tokens', async () => {
    const msg = 'تم الوصول إلى الحد الشهري لاستخدام المساعد'
    mockFetch(() => complete({ type: 'thread', thread_id: 'b' }, { type: 'error', message: msg }, { type: 'done' }))
    const { box } = setup()
    await userEvent.type(box(), 'هلا{Enter}')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(msg)
    expect(within(alert).queryByRole('button')).toBeNull()
    expect(await screen.findByRole('button', { name: 'إرسال' })).toBeInTheDocument()
  })

  it('prefs_changed invalidates feed, map and preferences and shows a notice', async () => {
    mockFetch(() => complete({ type: 'tool', name: 'update_preferences' }, { type: 'prefs_changed' }, { type: 'done' }))
    const { spy, box } = setup()
    await userEvent.type(box(), 'غيّر الميزانية{Enter}')
    expect(await screen.findByText('تم تحديث التفضيلات')).toBeInTheDocument()
    const keys = spy.mock.calls.map((c) => JSON.stringify((c[0] as { queryKey: unknown[] }).queryKey))
    expect(keys).toEqual(expect.arrayContaining(['["feed"]', '["map"]', '["preferences"]']))
  })

  it.each([[390, '/listing/5'], [820, '/?id=5']])('renders inline listing cards as links in a strip (width %i)', async (width, href) => {
    Object.defineProperty(window, 'innerWidth', { value: width, configurable: true })
    mockFetch(() => complete({ type: 'listings', items: [listing] }, { type: 'token', text: 'هذا أفضل خيار' }, { type: 'done' }))
    const { box } = setup()
    await userEvent.type(box(), 'وش أفضل؟{Enter}')
    const strip = await screen.findByTestId('chat-listings')
    const link = within(strip).getByRole('link')
    expect(link).toHaveAttribute('href', href)
    expect(link).toHaveTextContent('1,850,000')
    expect(link).toHaveTextContent('فيلا في النرجس')
    expect(within(strip).getByLabelText('درجة الملاءمة 86')).toBeInTheDocument()
  })

  it('new chat clears the messages and the stored thread', async () => {
    mockFetch(() => complete({ type: 'thread', thread_id: 'zz' }, { type: 'token', text: 'رد' }, { type: 'done' }))
    const { box } = setup()
    await userEvent.type(box(), 'سؤال{Enter}')
    await screen.findByText('رد')
    expect(localStorage.getItem('hf_thread')).toBe('zz')
    await userEvent.click(screen.getByRole('button', { name: 'محادثة جديدة' }))
    expect(screen.queryByText('رد')).toBeNull()
    expect(localStorage.getItem('hf_thread')).toBeNull()
    expect(box()).toHaveFocus()
    expect(screen.getByRole('button', { name: 'وش أفضل البيوت حالياً؟' })).toBeInTheDocument()
  })

  it('restores the stored thread on mount', async () => {
    localStorage.setItem('hf_thread', 'old')
    const f = vi.fn(async (url: string) => url === '/api/chat/threads/old'
      ? new Response(JSON.stringify({ id: 'old', title: 'x', messages: [{ role: 'user', text: 'سؤال قديم' }, { role: 'assistant', text: 'جواب قديم' }] }))
      : new Response('{}', { status: 404 }))
    vi.stubGlobal('fetch', f)
    setup()
    expect(await screen.findByText('جواب قديم')).toBeInTheDocument()
    expect(screen.getByText('سؤال قديم')).toBeInTheDocument()
  })
})
