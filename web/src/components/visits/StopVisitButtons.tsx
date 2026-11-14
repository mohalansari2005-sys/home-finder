import { CircleCheck, Navigation } from 'lucide-react'
import type { StopPatch, TripStop } from '../../api/types'
import { Button, buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface Props {
  stop: Pick<TripStop, 'contact_status' | 'maps_url'>
  onPatch: (p: StopPatch) => void
  className?: string
}

/** Directions in Google Maps and a one-tap "visited" for a trip stop (trip page and the listing opened from it). */
export function StopVisitButtons({ stop, onPatch, className }: Props) {
  const visited = stop.contact_status === 'visited'
  return (
    <div className={cn('flex gap-2', className)}>
      {stop.maps_url && (
        <a href={stop.maps_url} target="_blank" rel="noopener noreferrer"
           className={cn(buttonVariants({ variant: 'outline' }), 'h-11 flex-1 rounded-xl')}>
          <Navigation aria-hidden strokeWidth={1.75} />خرائط Google
        </a>
      )}
      <Button variant={visited ? 'default' : 'secondary'} aria-pressed={visited} disabled={visited}
              onClick={() => onPatch({ contact_status: 'visited' })} className="h-11 flex-1 rounded-xl disabled:opacity-100">
        <CircleCheck aria-hidden strokeWidth={1.75} />تمت الزيارة
      </Button>
    </div>
  )
}
