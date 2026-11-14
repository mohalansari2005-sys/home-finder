import { useNavigate, useParams, useSearchParams } from 'react-router'
import { ChevronRight } from 'lucide-react'
import { toast } from 'sonner'
import { ListingDetailView } from '../components/ListingDetailView'
import { StopVisitButtons } from '../components/visits/StopVisitButtons'
import { usePatchStop, useTrip } from '../api/hooks'
import { Button } from '@/components/ui/button'
import { useBreakpoint } from '../lib/breakpoint'
import { cn } from '@/lib/utils'

/** Opened from a trip stop (?trip=&stop=): directions and "visited" stay at hand while reading the listing. */
function VisitBar({ tripId, stopId }: { tripId: number; stopId: number }) {
  const trip = useTrip(tripId)
  const patch = usePatchStop(tripId)
  const phone = useBreakpoint() === 'phone'
  const stop = trip.data?.stops.find((s) => s.id === stopId)
  if (!stop) return null
  return (
    // on phones it rides just above the bottom tabs (min-h-14 plus the safe area)
    <div className={cn('sticky z-20 border-t bg-background/95 p-3 backdrop-blur',
                       phone ? 'bottom-[calc(3.5rem+env(safe-area-inset-bottom))]' : 'bottom-0')}>
      <StopVisitButtons stop={stop} className="mx-auto max-w-3xl"
                        onPatch={(p) => patch.mutate({ stopId, patch: p }, {
                          onSuccess: () => toast('تم تسجيل الزيارة'),
                          onError: () => toast.error('تعذّر حفظ التغيير. حاولوا مرة أخرى.'),
                        })} />
    </div>
  )
}

export function ListingPage() {
  const { id } = useParams()
  const [params] = useSearchParams()
  const nav = useNavigate()
  const tripId = Number(params.get('trip'))
  const stopId = Number(params.get('stop'))
  return (
    <>
      <div className="mx-auto max-w-3xl">
        <Button variant="outline" onClick={() => nav(-1)} className="m-4 mb-0">
          {/* chevron points to the right = "back" in RTL; flipped in LTR */}
          <ChevronRight aria-hidden className="ltr:-scale-x-100" strokeWidth={1.75} />
          رجوع
        </Button>
        <ListingDetailView id={Number(id)} />
      </div>
      {tripId > 0 && stopId > 0 && <VisitBar tripId={tripId} stopId={stopId} />}
    </>
  )
}
