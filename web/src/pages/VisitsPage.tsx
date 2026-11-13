import { useState } from 'react'
import { CalendarCheck, Home, MapPinOff, RefreshCw } from 'lucide-react'
import { Link } from 'react-router'
import { useTrips, useVisitGroups } from '../api/hooks'
import type { Trip } from '../api/types'
import { GroupCard } from '../components/visits/GroupCard'
import { TripBuilder } from '../components/visits/TripBuilder'
import { formatNumber, formatTripDate, pluralAr } from '../lib/format'
import { riyadhToday, TRIP_STATUS_AR } from '../lib/visits'
import type { VisitGroup } from '../api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

const stopsText = (n: number) => {
  const c = formatNumber(n)
  return pluralAr(n, { zero: 'لا توجد محطات', one: 'محطة واحدة', two: 'محطتان', few: `${c} محطات`, many: `${c} محطة`, other: `${c} محطة` })
}

function TripRow({ t }: { t: Trip }) {
  return (
    <li>
      <Link to={`/visits/${t.id}`} className="flex min-h-14 items-center gap-3 rounded-2xl border bg-card p-3 outline-none transition-transform focus-visible:ring-2 focus-visible:ring-ring active:scale-[0.98] motion-reduce:transition-none">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-muted"><CalendarCheck className="size-5" strokeWidth={1.75} aria-hidden /></span>
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="font-semibold">{formatTripDate(t.date)}</span>
          <span className="text-sm text-muted-foreground">{stopsText(t.stops.length)}</span>
        </span>
        <Badge variant={t.status === 'planned' ? 'default' : 'secondary'} className="rounded-full">{TRIP_STATUS_AR[t.status] ?? t.status}</Badge>
      </Link>
    </li>
  )
}

function Skeletons() {
  return <div className="space-y-3" aria-busy><Skeleton className="h-48 w-full rounded-2xl" /><Skeleton className="h-48 w-full rounded-2xl" /></div>
}

function Retry({ what, onRetry }: { what: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-2xl border bg-card p-4">
      <p className="text-destructive">{what}</p>
      <Button variant="outline" className="h-11 rounded-xl" onClick={onRetry}><RefreshCw aria-hidden />إعادة المحاولة</Button>
    </div>
  )
}

export function VisitsPage() {
  const groups = useVisitGroups()
  const trips = useTrips()
  const [plan, setPlan] = useState<VisitGroup | null>(null)
  const today = riyadhToday()
  const all = trips.data ?? []
  const upcoming = all.filter((t) => t.status === 'planned' && t.date >= today).sort((a, b) => a.date.localeCompare(b.date))
  const past = all.filter((t) => !(t.status === 'planned' && t.date >= today)).sort((a, b) => b.date.localeCompare(a.date))
  const g = groups.data
  const nothingSaved = !!g && g.groups.length === 0 && g.no_location.length === 0

  return (
    <div className="mx-auto min-w-0 max-w-7xl space-y-6 px-4 py-5 md:px-6 xl:px-8">
      <h1 className="font-display text-2xl font-bold text-balance">الزيارات</h1>
      <div className="grid min-w-0 gap-8 md:grid-cols-2 md:items-start">
        <section aria-labelledby="groups-title" className="min-w-0 space-y-3">
          <h2 id="groups-title" className="font-display text-lg font-semibold">مقترحات حسب الحي</h2>
          {groups.isError ? <Retry what="تعذّر تحميل المقترحات." onRetry={() => groups.refetch()} />
            : !g ? <Skeletons />
            : nothingSaved ? (
              <div className="flex flex-col items-center gap-3 rounded-2xl border bg-card p-8 text-center text-muted-foreground">
                <Home className="size-6" strokeWidth={1.75} aria-hidden />
                <p>احفظ بعض العقارات أولاً لتخطيط زيارة</p>
                <Button asChild variant="secondary" className="h-11 rounded-xl"><Link to="/">تصفح العقارات</Link></Button>
              </div>
            ) : (
              <>
                {g.groups.length > 0 && <ul className="space-y-3">{g.groups.map((gr) => <GroupCard key={gr.key} group={gr} onPlan={setPlan} />)}</ul>}
                {g.no_location.length > 0 && (
                  <div className="space-y-2 rounded-2xl bg-muted p-4">
                    <h3 className="flex items-center gap-2 font-semibold"><MapPinOff className="size-4" strokeWidth={1.75} aria-hidden />بدون موقع</h3>
                    <p className="text-sm text-muted-foreground">لا يمكن إضافتها لمسار لعدم توفر موقع</p>
                    <ul className="space-y-1 text-sm">
                      {g.no_location.map((l) => (
                        <li key={l.id}><Link to={`/listing/${l.id}`} className="inline-flex min-h-11 items-center underline-offset-4 hover:underline">{l.title ?? `عقار ${l.district ?? ''}`}</Link></li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
        </section>

        <section aria-labelledby="trips-title" className="min-w-0 space-y-3">
          <h2 id="trips-title" className="font-display text-lg font-semibold">الرحلات</h2>
          {trips.isError ? <Retry what="تعذّر تحميل الرحلات." onRetry={() => trips.refetch()} />
            : !trips.data ? <Skeletons />
            : all.length === 0 ? (
              <div className="flex flex-col items-center gap-2 rounded-2xl border bg-card p-8 text-center text-muted-foreground">
                <CalendarCheck className="size-6" strokeWidth={1.75} aria-hidden />
                <p>لا توجد رحلات بعد</p>
              </div>
            ) : (
              <>
                {upcoming.length > 0 && (
                  <div className="space-y-2"><h3 className="text-sm font-medium text-muted-foreground">القادمة</h3><ul className="space-y-2">{upcoming.map((t) => <TripRow key={t.id} t={t} />)}</ul></div>
                )}
                {past.length > 0 && (
                  <div className="space-y-2"><h3 className="text-sm font-medium text-muted-foreground">السابقة</h3><ul className="space-y-2">{past.map((t) => <TripRow key={t.id} t={t} />)}</ul></div>
                )}
              </>
            )}
        </section>
      </div>
      <TripBuilder group={plan} onClose={() => setPlan(null)} />
    </div>
  )
}
