import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { History, MessageCircle, PanelLeftClose, Plus, Send, Square, X } from 'lucide-react'
import { api } from '../../api/client'
import type { ChatThreadSummary } from '../../api/chat'
import { formatDateTime } from '../../lib/format'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { useChat } from './ChatProvider'
import { ChatMessage, ToolStatus, toolLabel } from './ChatMessage'

export type ChatVariant = 'page' | 'docked' | 'overlay'
export const SUGGESTIONS = ['وش أفضل البيوت حالياً؟', 'غيّر الميزانية', 'دوّر إعلانات جديدة']

function Threads({ onPick }: { onPick: (id: string) => void }) {
  const [open, setOpen] = useState(false)
  const q = useQuery({ queryKey: ['chat-threads'], queryFn: () => api<ChatThreadSummary[]>('/api/chat/threads'), enabled: open })
  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="icon" aria-label="المحادثات السابقة" className="size-10"><History aria-hidden strokeWidth={1.75} /></Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="max-h-80 w-72">
        <DropdownMenuLabel>المحادثات السابقة</DropdownMenuLabel>
        {q.isLoading && <div className="space-y-2 p-2" aria-busy><Skeleton className="h-5 w-full" /><Skeleton className="h-5 w-2/3" /></div>}
        {q.isError && <p className="p-2 text-sm text-destructive">تعذّر تحميل المحادثات</p>}
        {q.data?.length === 0 && <p className="p-2 text-sm text-muted-foreground">لا توجد محادثات سابقة</p>}
        {q.data?.map((t) => (
          <DropdownMenuItem key={t.id} onSelect={() => onPick(t.id)} className="flex-col items-start gap-0">
            <span className="line-clamp-1 w-full">{t.title || 'محادثة'}</span>
            <span className="text-xs text-muted-foreground"><bdi>{formatDateTime(new Date(t.updated_at))}</bdi></span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

interface Props { variant: ChatVariant; onClose?: () => void }

export function ChatPanel({ variant, onClose }: Props) {
  const chat = useChat()
  const { items, streaming, tool, send, stop, retry, newChat, openThread, restore } = chat
  const [draft, setDraft] = useState('')
  const input = useRef<HTMLTextAreaElement>(null)
  const end = useRef<HTMLDivElement>(null)
  const page = variant === 'page'

  useEffect(() => { restore() }, [restore])
  useEffect(() => { end.current?.scrollIntoView?.({ block: 'end' }) }, [items, tool, streaming])

  const last = items.at(-1)
  const answering = last?.kind === 'assistant' && last.text !== ''
  const showStatus = streaming && (tool != null || !answering)

  const submit = (text = draft) => {
    if (!text.trim() || streaming) return
    send(text)
    setDraft('')
    input.current?.focus()
  }
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit() }
  }

  return (
    <section aria-label="المساعد" className={cn('flex h-full min-h-0 flex-col', page ? 'bg-background' : 'bg-card')}>
      <header className="flex items-center justify-between gap-2 border-b bg-card px-4 py-3">
        <h2 className={cn('font-display font-bold', page ? 'text-xl' : 'text-lg')}>المساعد</h2>
        <div className="flex items-center gap-2">
          <Threads onPick={(id) => { void openThread(id) }} />
          <Button variant="outline" className="h-10 px-3 text-sm" onClick={() => { newChat(); input.current?.focus() }}>
            <Plus aria-hidden strokeWidth={1.75} />محادثة جديدة
          </Button>
          {onClose && (
            <Button variant="ghost" size="icon" className="size-10" onClick={onClose}
                    aria-label={variant === 'docked' ? 'طي المساعد' : 'إغلاق'}>
              {variant === 'docked' ? <PanelLeftClose aria-hidden strokeWidth={1.75} /> : <X aria-hidden strokeWidth={1.75} />}
            </Button>
          )}
        </div>
      </header>

      <ScrollArea className="min-h-0 flex-1 [&_[data-slot=scroll-area-viewport]>div]:!block">
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-3.5 px-4 pb-4 pt-4">
          {items.length === 0 && (
            <div className="flex flex-col items-center gap-3 px-4 py-8 text-center text-muted-foreground">
              <MessageCircle className="size-6" strokeWidth={1.75} aria-hidden />
              <p>اسألوا المساعد عن العقارات، أو اطلبوا منه تعديل التفضيلات.</p>
            </div>
          )}
          <div role="log" aria-live="polite" aria-relevant="additions text" aria-busy={streaming} aria-label="المحادثة" className="flex flex-col gap-3.5">
            {items.map((i) => (
              <ChatMessage key={i.id} item={i} onRetry={retry} onOpenListing={variant === 'overlay' ? onClose : undefined}
                           bubbleClass={page ? 'bg-card' : 'bg-background'} />
            ))}
            {showStatus && <ToolStatus label={toolLabel(tool)} />}
          </div>
          {items.length === 0 && (
            <div className="flex flex-wrap justify-center gap-2" aria-label="اقتراحات">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" onClick={() => submit(s)}
                        className="h-9 rounded-full border border-primary/30 bg-card px-3 text-sm font-medium text-primary outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring">
                  {s}
                </button>
              ))}
            </div>
          )}
          <div ref={end} />
        </div>
      </ScrollArea>

      <form onSubmit={(e) => { e.preventDefault(); submit() }}
            className="flex items-end gap-2 border-t bg-card px-4 pb-[calc(0.625rem+env(safe-area-inset-bottom))] pt-2.5 md:pb-3">
        <label className="flex-1">
          <span className="sr-only">رسالتك</span>
          <Textarea ref={input} rows={1} maxLength={2000} value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={onKeyDown}
                    placeholder="اكتب ما تبحثون عنه" enterKeyHint="send"
                    className="max-h-32 min-h-11 resize-none rounded-[22px] bg-background px-3.5 py-2.5 text-base md:text-base" />
        </label>
        {streaming
          ? <Button type="button" size="icon" className="size-11 rounded-full" aria-label="إيقاف" onClick={stop}><Square className="fill-current" aria-hidden strokeWidth={1.75} /></Button>
          : <Button type="submit" size="icon" className="size-11 rounded-full" aria-label="إرسال" disabled={!draft.trim()}><Send className="rtl:-scale-x-100" aria-hidden strokeWidth={1.75} /></Button>}
      </form>
    </section>
  )
}
