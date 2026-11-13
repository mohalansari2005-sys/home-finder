import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useReducer, useRef, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, ApiError } from '../../api/client'
import { streamChat, type ChatEvent, type ChatThread } from '../../api/chat'
import { chatReducer, initialChatState, type ChatState } from './chatState'

const THREAD_KEY = 'hf_thread'
const readThread = () => { try { return localStorage.getItem(THREAD_KEY) } catch { return null } }
const writeThread = (id: string | null) => {
  try { if (id) localStorage.setItem(THREAD_KEY, id); else localStorage.removeItem(THREAD_KEY) } catch { /* storage unavailable */ }
}

interface ChatApi extends ChatState {
  send: (text: string) => void
  stop: () => void
  retry: () => void
  newChat: () => void
  openThread: (id: string) => Promise<void>
  /** Load the stored thread once (called by the first mounted panel, i.e. only when logged in). */
  restore: () => void
}

const Ctx = createContext<ChatApi | null>(null)
export function useChat(): ChatApi {
  const c = useContext(Ctx)
  if (!c) throw new Error('useChat must be used inside ChatProvider')
  return c
}

/** One conversation shared by the page, docked and overlay panels, so it survives route and layout changes. */
export function ChatProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const [state, dispatch] = useReducer(chatReducer, undefined, () => ({ ...initialChatState, threadId: readThread() }))
  const live = useRef(state)
  useLayoutEffect(() => { live.current = state })
  const ctl = useRef<AbortController | null>(null)
  const restored = useRef(false)

  useEffect(() => { writeThread(state.threadId) }, [state.threadId])

  const run = useCallback(async (text: string) => {
    const c = new AbortController()
    ctl.current = c
    const onEvent = (event: ChatEvent) => {
      if (c.signal.aborted) return
      dispatch({ type: 'event', event })
      if (event.type === 'prefs_changed') {
        for (const key of ['feed', 'map', 'preferences']) qc.invalidateQueries({ queryKey: [key] })
      }
    }
    try {
      await streamChat(text, live.current.threadId, onEvent, c.signal)
      if (!c.signal.aborted) dispatch({ type: 'event', event: { type: 'done' } })
    } catch {
      dispatch({ type: c.signal.aborted ? 'abort' : 'fail' })
    } finally {
      if (ctl.current === c) ctl.current = null
      qc.invalidateQueries({ queryKey: ['chat-threads'] })
    }
  }, [qc])

  const send = useCallback((raw: string) => {
    const text = raw.trim()
    if (!text || live.current.streaming) return
    dispatch({ type: 'send', text })
    void run(text)
  }, [run])

  const retry = useCallback(() => {
    const last = [...live.current.items].reverse().find((i) => i.kind === 'user')
    if (!last || live.current.streaming) return
    dispatch({ type: 'retry' })
    void run(last.text)
  }, [run])

  const stop = useCallback(() => { ctl.current?.abort() }, [])

  const newChat = useCallback(() => {
    ctl.current?.abort()
    dispatch({ type: 'reset' })
    writeThread(null)
  }, [])

  const openThread = useCallback(async (id: string) => {
    ctl.current?.abort()
    try {
      dispatch({ type: 'load', thread: await api<ChatThread>(`/api/chat/threads/${id}`) })
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        if (live.current.threadId === id) dispatch({ type: 'reset' })
        toast.error('المحادثة غير موجودة')
      } else {
        toast.error('تعذّر تحميل المحادثة')
      }
    }
  }, [])

  const restore = useCallback(() => {
    const id = live.current.threadId
    if (restored.current || !id || live.current.items.length) return
    restored.current = true
    api<ChatThread>(`/api/chat/threads/${id}`)
      .then((thread) => { if (!live.current.items.length) dispatch({ type: 'load', thread }) })
      .catch((e) => { if (e instanceof ApiError && e.status === 404) { dispatch({ type: 'reset' }); writeThread(null) } })
  }, [])

  const value = useMemo(() => ({ ...state, send, stop, retry, newChat, openThread, restore }), [state, send, stop, retry, newChat, openThread, restore])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
