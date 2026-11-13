import { House } from 'lucide-react'
import { Link } from 'react-router'
import type { ListingCard } from '../../api/types'
import { formatNumber, PROPERTY_TYPE_AR } from '../../lib/format'
import { useBreakpoint } from '../../lib/breakpoint'
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area'
import { ScoreSeal } from '../ScoreSeal'

interface Props { items: ListingCard[]; onOpen?: () => void }

/** Horizontal strip of compact listing cards inside an assistant answer. */
export function ChatListingStrip({ items, onOpen }: Props) {
  const bp = useBreakpoint()
  if (!items.length) return null
  return (
    <ScrollArea className="-mx-4 w-[calc(100%+2rem)]" data-testid="chat-listings">
      <ul aria-label="عقارات مقترحة" className="flex w-max gap-2.5 px-4 pb-3">
        {items.map((l) => {
          const type = PROPERTY_TYPE_AR[l.property_type ?? ''] ?? 'عقار'
          return (
            <li key={l.id} className="w-[200px] shrink-0">
              <Link to={bp === 'phone' ? `/listing/${l.id}` : `/?id=${l.id}`} onClick={onOpen}
                    className="flex h-full flex-col overflow-hidden rounded-2xl border bg-card text-card-foreground outline-none transition-transform focus-visible:ring-2 focus-visible:ring-ring active:scale-[0.98] motion-reduce:active:scale-100">
                <div className="relative h-[92px] bg-muted">
                  {l.photo_url
                    ? <img src={l.photo_url} alt="" loading="lazy" width={200} height={92} className="size-full object-cover" />
                    : <div className="flex size-full items-center justify-center text-muted-foreground"><House className="size-6" strokeWidth={1.75} aria-hidden /></div>}
                  <ScoreSeal score={l.score} size="sm" className="absolute start-2 top-2" />
                </div>
                <div className="flex flex-col px-2.5 pb-2.5 pt-2">
                  <span className="font-display text-base font-bold">
                    <bdi>{l.price == null ? 'السعر غير مذكور' : formatNumber(l.price)}</bdi>
                    {l.price != null && <span className="ms-1 font-sans text-xs font-normal text-muted-foreground">ر.س</span>}
                  </span>
                  <span className="line-clamp-1 text-[13px] text-muted-foreground">{l.district ? `${type} في ${l.district}` : type}</span>
                </div>
              </Link>
            </li>
          )
        })}
      </ul>
      <ScrollBar orientation="horizontal" />
    </ScrollArea>
  )
}
