import { useEffect, useState, type ReactNode } from 'react'
import { Car, ChevronRight, CircleCheck, Clock as ClockIcon, Loader2, MapPin, RefreshCw, ShieldCheck, TriangleAlert } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { toast } from 'sonner'
import { usePatchStop, usePatchTripStatus, usePlaces, usePrecheckTrip, useReplanTrip, useTrip, useUploadStopPhoto } from '../api/hooks'
import type { Trip } from '../api/types'
import { ClockRange } from '../components/visits/Clock'
import { RouteMap } from '../components/visits/RouteMap'
import { StopCard } from '../components/visits/StopCard'
import { formatNumber, formatTripDate, pluralAr } from '../lib/format'
import { photoUploadError, tripWarnings, TRIP_STATUS_AR } from '../lib/visits'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

function useMediaQuery(q: string) {
  const [m, setM] = useState(() => window.matchMedia(q).matches)
  useEffect(() => {
    const mq = window.matchMedia(q)
    const on = () => setM(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [q])
  return m
}

const chip = 'inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-sm'

function minutesLong(n: number): ReactNode {
  const w = pluralAr(n, { zero: 'دقيقة', one: 'دقيقة واحدة', two: 'دقيقتان', few: 'دقائق', many: 'دقيقة', other: 'دقيقة' })
  return n === 1 || n === 2 ? w : <><bdi>{formatNumber(n)}</bdi> {w}</>
}

function Summary({ trip }: { trip: Trip }) {
  const n = trip.stops.length
  const c = formatNumber(n)
  const count = pluralAr(n, { zero: 'لا توجد عقارات', one: 'عقار واحد', two: 'عقاران', few: '', many: '', other: '' })
  const word = pluralAr(n, { zero: '', one: '', two: '', few: 'عقارات', many: 'عقارًا', other: 'عقار' })
  const first = trip.stops.find((s) => s.eta_local)?.eta_local ?? null
  const last = [...trip.stops].reverse().find((s) => s.etd_local)?.etd_local ?? null
  return (
    <ul aria-label="ملخص الرحلة" className="flex flex-wrap gap-1.5">
      <li className={chip}>{count || <><bdi>{c}</bdi> {word}</>}</li>
      {trip.total_drive_min != null && (
        <li className={chip}><Car className="size-3.5" strokeWidth={1.75} aria-hidden />{minutesLong(trip.total_drive_min)} <span>قيادة</span></li>
      )}
      {first && last && (
        <li className={chip}><ClockIcon className="size-3.5" strokeWidth={1.75} aria-hidden /><ClockRange from={first} to={last} /></li>
      )}
    </ul>
  )
}

function Skeletons() {
  return (
    <div className="mx-auto max-w-7xl space-y-4 px-4 py-5 md:px-6" aria-busy>
      <Skeleton className="h-10 w-48 rounded-xl" /><Skeleton className="h-24 w-full rounded-2xl" /><Skeleton className="h-64 w-full rounded-2xl" />
    </div>
  )
}

export function TripPage() {
  const id = Number(useParams().id)
  const q = useTrip(Number.isFinite(id) ? id : null)
  const places = usePlaces()
  const patch = usePatchStop(id)
  const upload = useUploadStopPhoto(id)
  const replan = useReplanTrip(id)
  const precheck = usePrecheckTrip(id)
  const setStatus = usePatchTripStatus(id)
  const wide = useMediaQuery('(min-width: 1024px)')
  const [active, setActive] = useState<number | null>(null)

  if (q.isError) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-3 p-10 text-center">
        <p className="text-destructive">تعذّر تحميل الرحلة.</p>
        <Button variant="outline" className="h-11 rounded-xl" onClick={() => q.refetch()}><RefreshCw aria-hidden />إعادة المحاولة</Button>
        <Link to="/visits" className="text-accent underline underline-offset-4">كل الرحلات</Link>
      </div>
    )
  }
  const trip = q.data
  if (!trip) return <Skeletons />

  const warnings = tripWarnings(trip)
  const pending = warnings.some((w) => w.code === 'precheck_pending') && !q.stalled
  const districts = [...new Set(trip.stops.map((s) => s.listing.district).filter((d): d is string => !!d))]
  const origin = places.data?.find((p) => p.kind === trip.origin_kind)
  const select = (stopId: number) => {
    setActive(stopId)
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    document.getElementById(`stop-${stopId}`)?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' })
  }
  const onPrecheck = () => precheck.mutate(undefined, {
    onSuccess: () => { q.restart(); toast('سيتم التحقق عند اتصال جهاز التحديث') },
    onError: () => toast.error('تعذّر بدء التحقق. حاولوا مرة أخرى.'),
  })

  return (
    <div className="mx-auto min-w-0 max-w-7xl px-4 py-5 md:px-6 xl:px-8 lg:grid lg:grid-cols-2 lg:items-start lg:gap-8">
      <div className="min-w-0">
        <header className="flex flex-col gap-3 pb-3">
          <Link to="/visits" className="inline-flex min-h-11 w-fit items-center gap-1 text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
            <ChevronRight className="size-4" strokeWidth={1.75} aria-hidden />كل الرحلات
          </Link>
          <div className="flex flex-col">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-display text-2xl font-bold leading-tight text-balance">{trip.title}</h1>
              {trip.status !== 'planned' && <Badge variant="secondary" className="rounded-full">{TRIP_STATUS_AR[trip.status]}</Badge>}
            </div>
            <p className="flex flex-wrap items-center gap-x-3 text-sm text-muted-foreground">
              <span>{formatTripDate(trip.date)}</span>
              {districts.length > 0 && <span className="inline-flex items-center gap-1"><MapPin className="size-4" strokeWidth={1.75} aria-hidden />حي {districts.join('، ')}</span>}
            </p>
          </div>
          <Summary trip={trip} />

          {warnings.filter((w) => w.code !== 'precheck_pending').map((w) => (
            <div key={w.code} role="status" className="flex items-center gap-2 rounded-xl bg-warning-soft px-3 py-2 text-sm text-warning">
              <TriangleAlert className="size-4 shrink-0" strokeWidth={1.75} aria-hidden />{w.text}
            </div>
          ))}
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" className="h-11 rounded-xl" disabled={replan.isPending} onClick={() => replan.mutate(undefined, { onError: () => toast.error('تعذّرت إعادة الترتيب.') })}>
              {replan.isPending ? <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden /> : <RefreshCw aria-hidden strokeWidth={1.75} />}إعادة الترتيب
            </Button>
            {trip.status === 'planned' && (
              <Button variant="ghost" className="h-11 rounded-xl" disabled={setStatus.isPending} onClick={() => setStatus.mutate('done', { onSuccess: () => toast('تم إنهاء الرحلة') })}>
                <CircleCheck aria-hidden strokeWidth={1.75} />إنهاء الرحلة
              </Button>
            )}
          </div>
        </header>

        <ol aria-label="محطات الزيارة" className="relative mt-2">
          <span aria-hidden className="absolute bottom-10 start-[15px] top-5 w-0.5 bg-border" />
          {trip.stops.map((s) => (
            <StopCard key={s.id} tripId={id} stop={s} active={active === s.id}
                      onPatch={(p) => patch.mutate({ stopId: s.id, patch: p }, { onError: () => toast.error('تعذّر حفظ التغيير. حاولوا مرة أخرى.') })}
                      onUpload={(file) => upload.mutate({ stopId: s.id, file }, {
                        onSuccess: () => toast('تم رفع الصورة'), onError: (e) => toast.error(photoUploadError(e)) })} />
          ))}
        </ol>

        {/* the listing check runs on its own 3 h before the trip; its results show on the stops (removed / price changed) */}
        <section aria-labelledby="precheck-title" className="flex flex-col gap-2 rounded-2xl border border-dashed p-3 text-sm">
          <div className="flex items-center justify-between gap-2">
            <h2 id="precheck-title" className="font-medium">التحقق من الإعلانات</h2>
            {pending && (
              <span role="status" className="inline-flex items-center gap-1.5 text-muted-foreground">
                <Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden />جارٍ التحقق من الإعلانات
              </span>
            )}
            {q.stalled && <span role="status" className="text-muted-foreground">لم يكتمل التحقق بعد</span>}
          </div>
          <p className="text-muted-foreground">يتحقق تلقائيًا قبل الرحلة بثلاث ساعات أن الإعلانات ما زالت قائمة وأن أسعارها لم تتغير.</p>
          <Button variant="outline" className="h-11 rounded-xl" disabled={precheck.isPending} onClick={onPrecheck}>
            {precheck.isPending ? <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden /> : <ShieldCheck aria-hidden strokeWidth={1.75} />}تحقق من الإعلانات الآن
          </Button>
        </section>
      </div>
      {wide && (
        <aside aria-label="خريطة المسار" className="sticky top-4 min-w-0">
          <RouteMap stops={trip.stops} origin={origin ?? null} activeId={active} onSelect={select} className="h-[calc(100dvh-2rem)]" />
        </aside>
      )}
    </div>
  )
}
