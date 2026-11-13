import { useEffect, useRef, useState } from 'react'
import { MessageCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ChatPanel } from './ChatPanel'

const KEY = 'hf_chat_open'
const read = () => { try { return localStorage.getItem(KEY) !== '0' } catch { return true } }
const write = (v: boolean) => { try { localStorage.setItem(KEY, v ? '1' : '0') } catch { /* storage unavailable */ } }

/** Desktop: chat docked on the end side, collapsible to a 48px rail. */
export function ChatDock() {
  const [open, setOpen] = useState(read)
  const rail = useRef<HTMLButtonElement>(null)
  const moved = useRef(false)
  const toggle = (v: boolean) => { moved.current = true; setOpen(v); write(v) }

  // Move focus with the control the user just used (the old button unmounts).
  useEffect(() => {
    if (!moved.current) return
    if (open) document.querySelector<HTMLTextAreaElement>('[data-chat-dock] textarea')?.focus()
    else rail.current?.focus()
  }, [open])

  return (
    <aside data-chat-dock data-testid="chat-dock" aria-label="المساعد"
           className={open ? 'h-dvh w-[380px] shrink-0 border-s' : 'flex h-dvh w-12 shrink-0 flex-col items-center border-s bg-card pt-3'}>
      {open
        ? <ChatPanel variant="docked" onClose={() => toggle(false)} />
        : (
          <Button ref={rail} variant="ghost" size="icon" aria-label="فتح المساعد" aria-expanded={false} onClick={() => toggle(true)}>
            <MessageCircle aria-hidden strokeWidth={1.75} className="size-5" />
          </Button>
        )}
    </aside>
  )
}
