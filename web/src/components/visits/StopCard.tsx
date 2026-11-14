import { useId, useState } from 'react'
import { Camera, Car, FileText, Home, MessageCircle, Phone, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router'
import type { ContactStatus, StopPatch, TripStop } from '../../api/types'
import { ScoreSeal } from '../ScoreSeal'
import { formatNumber, formatRooms, PROPERTY_TYPE_AR } from '../../lib/format'
import { CONTACT_STATUSES, MAX_PHOTO_BYTES } from '../../lib/visits'
import { buttonVariants } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { cn } from '@/lib/utils'
import { ClockRange } from './Clock'
import { StarRating } from './StarRating'
import { StopVisitButtons } from './StopVisitButtons'

interface Props {
  tripId: number
  stop: TripStop
  onPatch: (p: StopPatch) => void
  onUpload: (f: File) => void
  active?: boolean
}

const rowTone = 'flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm'

export function StopCard({ tripId, stop, onPatch, onUpload, active }: Props) {
  const l = stop.listing
  const notesId = useId()
  const [notes, setNotes] = useState(stop.notes ?? '')
  const [photoError, setPhotoError] = useState<string | null>(null)
  const removed = stop.flags.includes('removed') || l.status === 'removed'
  const priceChanged = stop.flags.includes('price_changed')
  const visited = stop.contact_status === 'visited'
  const listingPath = `/listing/${l.id}?trip=${tripId}&stop=${stop.id}`
  const title = l.title ?? `${PROPERTY_TYPE_AR[l.property_type ?? ''] ?? 'عقار'}${l.district ? ` في ${l.district}` : ''}`

  const pickPhoto = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    if (f.size > MAX_PHOTO_BYTES) { setPhotoError('حجم الصورة يتجاوز 8 ميغابايت'); return }
    setPhotoError(null)
    onUpload(f)
  }

  return (
    <li id={`stop-${stop.id}`} className="relative flex scroll-mt-4 gap-3 pb-4">
      <span className="z-10 flex size-8 shrink-0 items-center justify-center rounded-full bg-primary font-display text-sm font-bold text-primary-foreground ring-4 ring-background">
        <bdi>{stop.position + 1}</bdi>
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-center justify-between gap-2 text-sm">
          <ClockRange data-testid="stop-time" from={stop.eta_local} to={stop.etd_local} className="font-semibold" />
          {stop.drive_min != null && (
            <span className="inline-flex items-center gap-1 text-muted-foreground">
              <Car className="size-4" strokeWidth={1.75} aria-hidden /><span className="sr-only">مدة القيادة</span><bdi>{formatNumber(stop.drive_min)}</bdi> د
            </span>
          )}
        </div>

        <div className={cn('flex flex-col gap-3 rounded-2xl border bg-card p-3', active && 'ring-2 ring-ring', removed && 'opacity-90')}>
          <Link to={listingPath} className="flex gap-3 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <span className="flex h-14 w-[72px] shrink-0 items-center justify-center overflow-hidden rounded-xl bg-muted text-muted-foreground">
              {l.photo_url
                ? <img src={l.photo_url} alt="" loading="lazy" width={144} height={112} className={cn('size-full object-cover', removed && 'grayscale')} />
                : <Home className="size-5" strokeWidth={1.75} aria-hidden />}
            </span>
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="font-display text-base font-bold">
                {l.price != null ? <><bdi>{formatNumber(l.price)}</bdi> <span className="font-sans text-xs font-normal text-muted-foreground">ر.س</span></> : <span className="font-sans text-sm font-normal text-muted-foreground">السعر غير مذكور</span>}
              </span>
              <span className="truncate text-sm text-muted-foreground">{title}</span>
              <span className="flex flex-wrap gap-x-3 text-sm text-muted-foreground">
                {l.district && <span>{l.district}</span>}
                {l.bedrooms != null && <span>{formatRooms(l.bedrooms)}</span>}
              </span>
            </span>
            <ScoreSeal score={l.score} size="sm" className="shrink-0 self-start" />
          </Link>

          {removed && (
            <div role="status" className={cn(rowTone, 'bg-destructive/10 text-destructive')}>
              <TriangleAlert className="size-4 shrink-0" strokeWidth={1.75} aria-hidden />الإعلان محذوف
            </div>
          )}
          {priceChanged && (
            <div role="status" className={cn(rowTone, 'bg-warning-soft text-warning')}>
              <TriangleAlert className="size-4 shrink-0" strokeWidth={1.75} aria-hidden />
              <span>تغيّر السعر{stop.old_price != null && <> من <bdi>{formatNumber(stop.old_price)}</bdi> ر.س</>}</span>
            </div>
          )}

          <ToggleGroup type="single" aria-label="حالة التواصل" spacing={2} value={stop.contact_status}
                       onValueChange={(v) => { if (v && v !== stop.contact_status) onPatch({ contact_status: v as ContactStatus }) }}
                       className="flex w-full flex-wrap rounded-xl bg-muted p-[3px]">
            {CONTACT_STATUSES.map((s) => (
              <ToggleGroupItem key={s.value} value={s.value}
                               className="h-11 min-w-0 grow basis-[28%] rounded-lg px-1 text-sm font-normal hover:bg-background/60 data-[state=on]:bg-background data-[state=on]:font-semibold data-[state=on]:text-primary">
                {s.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>

          <Link to={listingPath} className={cn(buttonVariants({ variant: 'secondary' }), 'h-11 rounded-xl')}><FileText aria-hidden strokeWidth={1.75} />فتح الإعلان</Link>
          <StopVisitButtons stop={stop} onPatch={onPatch} />
          {(stop.whatsapp_url || stop.phone) && (
            <div className="flex gap-2">
              {stop.whatsapp_url && (
                <a href={stop.whatsapp_url} target="_blank" rel="noopener noreferrer" aria-label="مراسلة المعلن عبر واتساب"
                   className={cn(buttonVariants({ variant: 'secondary' }), 'h-11 flex-1 rounded-xl bg-primary/10 text-primary hover:bg-primary/15')}>
                  <MessageCircle aria-hidden strokeWidth={1.75} />واتساب
                </a>
              )}
              {stop.phone && (
                <a href={`tel:+${stop.phone.replace(/^\+/, '')}`} aria-label="الاتصال بالمعلن"
                   className={cn(buttonVariants({ variant: 'outline' }), 'h-11 flex-1 rounded-xl')}>
                  <Phone aria-hidden strokeWidth={1.75} />اتصال
                </a>
              )}
            </div>
          )}

          {visited && (
            <div className="space-y-3 border-t pt-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">التقييم</span>
                <StarRating value={stop.rating} onChange={(rating) => onPatch({ rating })} />
              </div>
              <div className="space-y-2">
                <Label htmlFor={notesId}>ملاحظات الزيارة</Label>
                <Textarea id={notesId} value={notes} rows={3} maxLength={2000} className="resize-none rounded-xl text-base"
                          onChange={(e) => setNotes(e.target.value)}
                          onBlur={() => { if (notes !== (stop.notes ?? '')) onPatch({ notes }) }} />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <label className={cn(buttonVariants({ variant: 'outline' }), 'h-11 cursor-pointer rounded-xl has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring')}>
                  <Camera aria-hidden strokeWidth={1.75} />إضافة صورة
                  <input type="file" accept="image/*" capture="environment" className="sr-only" onChange={pickPhoto} />
                </label>
                {stop.photos.map((u, i) => (
                  <a key={u} href={u} target="_blank" rel="noopener noreferrer" className="size-14 overflow-hidden rounded-xl bg-muted outline-none focus-visible:ring-2 focus-visible:ring-ring">
                    <img src={u} alt={`صورة الزيارة ${i + 1}`} loading="lazy" width={112} height={112} className="size-full object-cover" />
                  </a>
                ))}
              </div>
              {photoError && <p role="alert" className="text-sm text-destructive">{photoError}</p>}
            </div>
          )}
        </div>
      </div>
    </li>
  )
}
