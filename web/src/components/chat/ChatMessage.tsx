import { Check, Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { ChatListingStrip } from './ChatListingStrip'
import type { ChatItem } from './chatState'

export const TOOL_LABELS: Record<string, string> = {
  search_listings: 'يبحث في العقارات…',
  get_listing: 'يقرأ التفاصيل…',
  update_preferences: 'يحدّث التفضيلات…',
  get_preferences: 'يراجع التفضيلات…',
  compare_listings: 'يقارن…',
  request_scrape: 'يطلب إعلانات جديدة…',
}
export const toolLabel = (name: string | null) => (name && TOOL_LABELS[name]) || 'جارٍ العمل…'

const pill = 'inline-flex items-center gap-1.5 self-center rounded-full bg-muted px-3 py-1 text-[13px] text-muted-foreground'

export function ToolStatus({ label }: { label: string }) {
  return (
    <div role="status" className={pill}>
      <Loader2 className="size-3.5 animate-spin motion-reduce:animate-none" strokeWidth={2} aria-hidden />
      {label}
    </div>
  )
}

interface Props { item: ChatItem; /** Assistant bubble surface: bg-card on the page, bg-background inside the card-coloured docked/overlay panels. */
  bubbleClass: string; onRetry: () => void; onOpenListing?: () => void }

export function ChatMessage({ item, bubbleClass, onRetry, onOpenListing }: Props) {
  switch (item.kind) {
    case 'user':
      return (
        <div className="max-w-[82%] self-start whitespace-pre-wrap break-words rounded-2xl rounded-ee-[4px] bg-primary px-3.5 py-2.5 text-[15px] text-primary-foreground">
          {item.text}
        </div>
      )
    case 'assistant':
      return (
        <>
          {item.text && (
            <div className={cn('max-w-[88%] self-end whitespace-pre-wrap break-words rounded-2xl rounded-es-[4px] border px-3.5 py-2.5 text-[15px]', bubbleClass)}>
              {item.text}
            </div>
          )}
          <ChatListingStrip items={item.listings} onOpen={onOpenListing} />
        </>
      )
    case 'notice':
      return (
        <div role="status" className={pill}>
          <Check className="size-3.5 text-success" strokeWidth={2} aria-hidden />
          {item.text}
        </div>
      )
    case 'error':
      return (
        <div role="alert" className="flex max-w-[92%] flex-col items-start gap-2 self-center rounded-2xl border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[15px] text-destructive">
          <p>{item.text}</p>
          {item.retryable && (
            <Button variant="outline" size="sm" onClick={onRetry}><RefreshCw aria-hidden />إعادة المحاولة</Button>
          )}
        </div>
      )
  }
}
