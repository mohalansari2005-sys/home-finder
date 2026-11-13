import { describe, expect, it } from 'vitest'
import type { ListingCard } from '../../api/types'
import { chatReducer, initialChatState, type ChatState } from './chatState'

const card = { id: 7, title: 'فيلا', price: 1_000_000 } as ListingCard
const run = (s: ChatState, ...actions: Parameters<typeof chatReducer>[1][]) => actions.reduce(chatReducer, s)
const started = () => run(initialChatState, { type: 'send', text: 'هلا' })

describe('chatReducer', () => {
  it('send adds the user bubble and starts streaming', () => {
    const s = started()
    expect(s.streaming).toBe(true)
    expect(s.items).toEqual([{ id: 'm0', kind: 'user', text: 'هلا' }])
  })

  it('tokens append to one assistant bubble and clear the tool status', () => {
    const s = run(started(), { type: 'event', event: { type: 'tool', name: 'search_listings' } })
    expect(s.tool).toBe('search_listings')
    const t = run(s, { type: 'event', event: { type: 'token', text: 'مر' } }, { type: 'event', event: { type: 'token', text: 'حبا' } })
    expect(t.tool).toBeNull()
    expect(t.items.filter((i) => i.kind === 'assistant')).toHaveLength(1)
    expect(t.items[1]).toMatchObject({ kind: 'assistant', text: 'مرحبا' })
  })

  it('listings attach to the turn assistant item; thread id is stored', () => {
    const s = run(started(), { type: 'event', event: { type: 'thread', thread_id: 't9' } },
      { type: 'event', event: { type: 'listings', items: [card] } }, { type: 'event', event: { type: 'token', text: 'وجدت' } })
    expect(s.threadId).toBe('t9')
    expect(s.items[1]).toMatchObject({ kind: 'assistant', text: 'وجدت', listings: [card] })
  })

  it('prefs_changed adds a notice pill', () => {
    const s = run(started(), { type: 'event', event: { type: 'prefs_changed' } })
    expect(s.items.at(-1)).toMatchObject({ kind: 'notice', text: 'تم تحديث التفضيلات' })
  })

  it('error event adds an error item and stops streaming; budget is not retryable', () => {
    const budget = 'تم الوصول إلى الحد الشهري لاستخدام المساعد'
    const s = run(started(), { type: 'event', event: { type: 'error', message: budget } }, { type: 'event', event: { type: 'done' } })
    expect(s.streaming).toBe(false)
    expect(s.items.at(-1)).toMatchObject({ kind: 'error', text: budget, retryable: false })
    const t = run(started(), { type: 'event', event: { type: 'error', message: 'حدث خطأ، حاول مرة أخرى' } })
    expect(t.items.at(-1)).toMatchObject({ kind: 'error', retryable: true })
  })

  it('fail (network) adds a retryable error; abort keeps the partial text', () => {
    const f = run(started(), { type: 'fail' })
    expect(f.streaming).toBe(false)
    expect(f.items.at(-1)).toMatchObject({ kind: 'error', retryable: true })
    const a = run(started(), { type: 'event', event: { type: 'token', text: 'نص جزئي' } }, { type: 'abort' })
    expect(a.streaming).toBe(false)
    expect(a.items[1]).toMatchObject({ kind: 'assistant', text: 'نص جزئي' })
    expect(a.items.some((i) => i.kind === 'error')).toBe(false)
  })

  it('retry drops the trailing error and re-streams without a second user bubble', () => {
    const f = run(started(), { type: 'fail' })
    const r = run(f, { type: 'retry' })
    expect(r.streaming).toBe(true)
    expect(r.items).toEqual([{ id: 'm0', kind: 'user', text: 'هلا' }])
  })

  it('reset clears everything; load replaces items from history', () => {
    expect(run(started(), { type: 'reset' })).toEqual(initialChatState)
    const s = run(initialChatState, { type: 'load', thread: { id: 't1', title: 'x', messages: [
      { role: 'user', text: 'أ' }, { role: 'assistant', text: 'ب', listings: [card] }] } })
    expect(s.threadId).toBe('t1')
    expect(s.items.map((i) => i.kind)).toEqual(['user', 'assistant'])
    expect(s.items[1]).toMatchObject({ text: 'ب', listings: [card] })
  })
})
