import { Columns2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { formatNumber } from '../lib/format'

interface Props { count: number; max: number; onCompare: () => void; onClear: () => void }

/** Pinned to the bottom of the feed scroller while in compare mode. Needs 2 listings to open. */
export function CompareBar({ count, max, onCompare, onClear }: Props) {
  return (
    <div className="pointer-events-none sticky bottom-[calc(1rem+env(safe-area-inset-bottom))] z-10 flex justify-center px-4 pb-1 xl:bottom-4">
      <div role="region" aria-label="شريط المقارنة"
           className="pointer-events-auto flex items-center gap-2 rounded-full border bg-card p-1.5 ps-4 shadow-sm">
        <span className="text-sm text-muted-foreground">
          {count < 2 ? 'اختاروا عقارين على الأقل' : <>الحد الأقصى <bdi>{formatNumber(max)}</bdi></>}
        </span>
        <Button variant="ghost" size="icon" aria-label="مسح الاختيار" disabled={count === 0} onClick={onClear} className="size-11 rounded-full">
          <X aria-hidden />
        </Button>
        <Button disabled={count < 2} onClick={onCompare} className="h-11 rounded-full px-5">
          <Columns2 aria-hidden />
          <span>قارن (<bdi>{formatNumber(count)}</bdi>)</span>
        </Button>
      </div>
    </div>
  )
}
