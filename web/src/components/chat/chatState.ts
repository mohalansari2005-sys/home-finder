import { BUDGET_MESSAGE, type ChatEvent, type ChatThread } from '../../api/chat'
import type { ListingCard } from '../../api/types'

export type ChatItem =
  | { id: string; kind: 'user'; text: string }
  | { id: string; kind: 'assistant'; text: string; listings: ListingCard[] }
  | { id: string; kind: 'notice'; text: string }
  | { id: string; kind: 'error'; text: string; retryable: boolean }

export interface ChatState {
  items: ChatItem[]
  threadId: string | null
  streaming: boolean
  /** Name of the tool the agent is currently running (shown as a status pill). */
  tool: string | null
  /** id of the assistant bubble for the turn in progress; created lazily by the first token or listings event. */
  turnId: string | null
}

export const initialChatState: ChatState = { items: [], threadId: null, streaming: false, tool: null, turnId: null }

export type ChatAction =
  | { type: 'send'; text: string }
  | { type: 'retry' }
  | { type: 'event'; event: ChatEvent }
  | { type: 'fail' }
  | { type: 'abort' }
  | { type: 'reset' }
  | { type: 'load'; thread: ChatThread }

export const NETWORK_ERROR = 'تعذّر الاتصال بالمساعد. تحقق من الاتصال ثم أعد المحاولة.'

const nextId = (s: ChatState) => `m${s.items.length}`

/** Append to (or create) the assistant bubble of the current turn. */
function patchTurn(s: ChatState, patch: (a: Extract<ChatItem, { kind: 'assistant' }>) => Extract<ChatItem, { kind: 'assistant' }>): ChatState {
  const existing = s.turnId && s.items.find((i) => i.id === s.turnId)
  if (existing && existing.kind === 'assistant') {
    return { ...s, items: s.items.map((i) => (i.id === s.turnId ? patch(existing) : i)) }
  }
  const id = nextId(s)
  return { ...s, turnId: id, items: [...s.items, patch({ id, kind: 'assistant', text: '', listings: [] })] }
}

function applyEvent(s: ChatState, e: ChatEvent): ChatState {
  switch (e.type) {
    case 'thread': return { ...s, threadId: e.thread_id }
    case 'token': return { ...patchTurn(s, (a) => ({ ...a, text: a.text + e.text })), tool: null }
    case 'tool': return { ...s, tool: e.name }
    case 'listings': return patchTurn(s, (a) => ({ ...a, listings: [...a.listings, ...e.items] }))
    case 'prefs_changed': return { ...s, items: [...s.items, { id: nextId(s), kind: 'notice', text: 'تم تحديث التفضيلات' }] }
    case 'error':
      return { ...s, tool: null, items: [...s.items, { id: nextId(s), kind: 'error', text: e.message, retryable: e.retryable ?? e.message !== BUDGET_MESSAGE }] }
    case 'done': return { ...s, streaming: false, tool: null, turnId: null }
  }
}

export function chatReducer(s: ChatState, a: ChatAction): ChatState {
  switch (a.type) {
    case 'send':
      return { ...s, streaming: true, tool: null, turnId: null, items: [...s.items, { id: nextId(s), kind: 'user', text: a.text }] }
    case 'retry': {
      const items = [...s.items]
      while (items.at(-1)?.kind === 'error') items.pop()
      return { ...s, items, streaming: true, tool: null, turnId: null }
    }
    case 'event': return s.streaming || a.event.type === 'thread' ? applyEvent(s, a.event) : s
    case 'fail':
      return { ...s, streaming: false, tool: null, turnId: null, items: [...s.items, { id: nextId(s), kind: 'error', text: NETWORK_ERROR, retryable: true }] }
    case 'abort': return { ...s, streaming: false, tool: null, turnId: null }
    case 'reset': return initialChatState
    case 'load':
      return {
        ...initialChatState, threadId: a.thread.id,
        items: a.thread.messages.map((m, i): ChatItem => m.role === 'user'
          ? { id: `m${i}`, kind: 'user', text: m.text }
          : { id: `m${i}`, kind: 'assistant', text: m.text, listings: m.listings ?? [] }),
      }
  }
}
