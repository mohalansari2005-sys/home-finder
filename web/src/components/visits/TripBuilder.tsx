import { useId, useState } from 'react'
import { Loader2, X } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { errorDetail } from '../../api/client'
import { useCreateTrip, usePlaces } from '../../api/hooks'
import type { TripOrigin, VisitGroup } from '../../api/types'
import { useBreakpoint } from '../../lib/breakpoint'
import { formatClock, formatNumber, formatPrice, formatTripDate, PLACE_LABEL_AR } from '../../lib/format'
import { nextSaturday } from '../../lib/visits'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from '@/components/ui/drawer'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'

const ORIGINS: TripOrigin[] = ['home', 'school', 'work', 'university']
const MINUTES = [15, 30, 45, 60]
const MAX_STOPS = 15
const chip = 'h-11 rounded-full px-4 text-base data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-primary-foreground'

function Body({ group }: { group: VisitGroup }) {
  const nav = useNavigate()
  const places = usePlaces()
  const create = useCreateTrip()
  const ids = useId()
  const [picked, setPicked] = useState<number[]>(() => group.listing_ids.slice(0, MAX_STOPS))
  const [date, setDate] = useState(() => nextSaturday())
  const [time, setTime] = useState('16:00')
  const [origin, setOrigin] = useState<TripOrigin | null>(null)
  const [minutes, setMinutes] = useState(30)
  const [error, setError] = useState<string | null>(null)

  const available = ORIGINS.filter((k) => places.data?.some((p) => p.kind === k))
  const homeMissing = !!places.data && !available.includes('home')
  const chosen = origin && available.includes(origin) ? origin : (available[0] ?? null)
  const clock = formatClock(time)
  const toggle = (id: number, on: boolean) => setPicked((p) => (on ? [...p, id] : p.filter((x) => x !== id)))
  const canSubmit = !create.isPending && picked.length > 0 && !!chosen && !!date && !!time

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!chosen) return
    setError(null)
    create.mutate(
      { listing_ids: group.listing_ids.filter((i) => picked.includes(i)), date, start_time: time, origin_kind: chosen, minutes_per_visit: minutes },
      { onSuccess: (t) => nav(`/visits/${t.id}`), onError: (er) => setError(errorDetail(er)) },
    )
  }

  return (
    <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 space-y-5 overflow-y-auto px-4 pb-4">
        <fieldset className="space-y-2">
          <legend className="mb-2 text-sm font-medium">العقارات في الرحلة</legend>
          <ul className="space-y-1">
            {group.listings.map((l) => {
              const on = picked.includes(l.id)
              const cid = `${ids}-l${l.id}`
              return (
                <li key={l.id}>
                  <label htmlFor={cid} className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl px-2 hover:bg-muted">
                    <Checkbox id={cid} checked={on} disabled={!on && picked.length >= MAX_STOPS} onCheckedChange={(v) => toggle(l.id, v === true)} />
                    <span className="flex min-w-0 flex-1 flex-col text-sm">
                      <span className="truncate font-medium">{l.title ?? `عقار ${l.district ?? ''}`}</span>
                      <span className="text-muted-foreground">{l.district && <span className="me-3">{l.district}</span>}<bdi>{formatPrice(l.price).replace(' ر.س', '')}</bdi> ر.س</span>
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>
          {picked.length === 0 && <p className="text-sm text-muted-foreground">اختاروا عقارًا واحدًا على الأقل.</p>}
        </fieldset>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor={`${ids}-date`}>التاريخ</Label>
            <Input id={`${ids}-date`} type="date" value={date} required onChange={(e) => setDate(e.target.value)} className="h-11 rounded-xl" />
            {date && <p className="text-sm text-muted-foreground">{formatTripDate(date)}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${ids}-time`}>وقت البدء</Label>
            <Input id={`${ids}-time`} type="time" value={time} required onChange={(e) => setTime(e.target.value)} className="h-11 rounded-xl" />
            {clock && <p className="text-sm text-muted-foreground"><bdi>{clock.time}</bdi> {clock.period}</p>}
          </div>
        </div>

        <div className="space-y-2">
          <Label id={`${ids}-origin`}>نقطة الانطلاق</Label>
          {places.isLoading ? <Skeleton className="h-11 w-full rounded-xl" /> : (
            <>
              {available.length > 0 && (
                <ToggleGroup type="single" aria-labelledby={`${ids}-origin`} variant="outline" spacing={2} className="w-full flex-wrap"
                             value={chosen ?? ''} onValueChange={(v) => v && setOrigin(v as TripOrigin)}>
                  {available.map((k) => <ToggleGroupItem key={k} value={k} className={chip}>{PLACE_LABEL_AR[k]}</ToggleGroupItem>)}
                </ToggleGroup>
              )}
              {homeMissing && (
                <p className="text-sm text-muted-foreground">
                  لم يُحدَّد المنزل الحالي بعد. <Link to="/settings" className="font-medium text-accent underline underline-offset-4">تحديده من الإعدادات</Link>
                </p>
              )}
            </>
          )}
        </div>

        <div className="space-y-2">
          <Label id={`${ids}-min`}>مدة كل زيارة (بالدقائق)</Label>
          <ToggleGroup type="single" aria-labelledby={`${ids}-min`} variant="outline" spacing={2} className="w-full flex-wrap"
                       value={String(minutes)} onValueChange={(v) => v && setMinutes(Number(v))}>
            {MINUTES.map((m) => <ToggleGroupItem key={m} value={String(m)} className={chip}><bdi>{formatNumber(m)}</bdi></ToggleGroupItem>)}
          </ToggleGroup>
        </div>

        {error && <p role="alert" className="rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
      </div>
      <div className="border-t p-4 pb-[calc(1rem+env(safe-area-inset-bottom))]">
        <Button type="submit" size="lg" disabled={!canSubmit} className="h-11 w-full rounded-xl">
          {create.isPending && <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden />}إنشاء الرحلة
        </Button>
      </div>
    </form>
  )
}

/** Plan a visit for one district group: bottom drawer on phone, side sheet on tablet/desktop. */
export function TripBuilder({ group, onClose }: { group: VisitGroup | null; onClose: () => void }) {
  const bp = useBreakpoint()
  const open = group != null
  const desc = group ? group.districts.join('، ') : ''
  const change = (o: boolean) => { if (!o) onClose() }
  if (bp === 'phone') {
    return (
      <Drawer open={open} onOpenChange={change}>
        <DrawerContent aria-modal="true" className="rounded-t-3xl data-[vaul-drawer-direction=bottom]:max-h-[90dvh]">
          <DrawerHeader className="text-start">
            <DrawerTitle className="font-display text-lg font-bold">تخطيط زيارة</DrawerTitle>
            <DrawerDescription>{desc}</DrawerDescription>
          </DrawerHeader>
          {group && <Body key={group.key} group={group} />}
        </DrawerContent>
      </Drawer>
    )
  }
  return (
    <Sheet open={open} onOpenChange={change}>
      <SheetContent side="left" showCloseButton={false} className="gap-0 rounded-e-3xl shadow-xl data-[side=left]:sm:max-w-md">
        <SheetHeader className="flex-row items-start justify-between gap-3 p-4">
          <div>
            <SheetTitle className="font-display text-lg font-bold">تخطيط زيارة</SheetTitle>
            <SheetDescription>{desc}</SheetDescription>
          </div>
          <SheetClose asChild><Button variant="ghost" size="icon" aria-label="إغلاق" className="size-11"><X aria-hidden /></Button></SheetClose>
        </SheetHeader>
        {group && <Body key={group.key} group={group} />}
      </SheetContent>
    </Sheet>
  )
}
