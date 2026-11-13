import { useRef, useState } from 'react'
import { MessageCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { ChatPanel } from './ChatPanel'

/** Tablet (and narrow desktop): floating button that opens the chat as a slide-over on the end side. */
export function ChatOverlay() {
  const [open, setOpen] = useState(false)
  const content = useRef<HTMLDivElement>(null)
  return (
    <>
      <Sheet open={open} onOpenChange={setOpen}>
        {/* A real trigger lets Radix return focus to the button when the panel closes. */}
        <SheetTrigger asChild>
          <Button className="fixed bottom-7 end-7 z-20 h-14 gap-2 rounded-full px-5 text-base font-semibold shadow-xl">
            <MessageCircle className="size-5" aria-hidden strokeWidth={1.75} />
            اسأل المساعد
          </Button>
        </SheetTrigger>
        <SheetContent ref={content} side="left" showCloseButton={false}
                      onOpenAutoFocus={(e) => { e.preventDefault(); content.current?.querySelector('textarea')?.focus() }}
                      className="data-[side=left]:w-[min(420px,100vw)] gap-0 overflow-hidden rounded-s-3xl p-0 data-[side=left]:sm:max-w-none">
          <SheetTitle className="sr-only">المساعد</SheetTitle>
          <SheetDescription className="sr-only">محادثة مع المساعد حول العقارات والتفضيلات</SheetDescription>
          <ChatPanel variant="overlay" onClose={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
    </>
  )
}
