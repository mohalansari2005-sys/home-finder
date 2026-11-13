import { Star } from 'lucide-react'
import { cn } from '@/lib/utils'

/** 1-5 stars as a group of buttons: native buttons give Tab + Enter/Space; `aria-pressed` marks the chosen value. */
export function StarRating({ value, onChange, disabled }: { value: number | null; onChange: (n: number) => void; disabled?: boolean }) {
  return (
    <div role="group" aria-label="تقييم الزيارة" className="flex items-center">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" aria-label={`${n} من 5`} aria-pressed={value === n} disabled={disabled} onClick={() => onChange(n)}
                className="flex size-11 items-center justify-center rounded-xl text-seal-foreground outline-none transition-transform focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 active:scale-95 motion-reduce:transition-none">
          <Star aria-hidden strokeWidth={1.75} className={cn('size-6', value != null && n <= value ? 'fill-seal stroke-seal-foreground' : 'stroke-muted-foreground')} />
        </button>
      ))}
    </div>
  )
}
