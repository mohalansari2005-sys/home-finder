import { useEffect, useState } from 'react'
import { Bookmark, Check, ChevronLeft, ChevronRight, ExternalLink, MapPin, MessageCircle, Phone, RefreshCw, X } from 'lucide-react'
import { useListing, useReactWithUndo } from '../api/hooks'
import { FACING_AR, formatArea, formatNumber, formatPrice, formatYears, PROPERTY_TYPE_AR } from '../lib/format'
import { REASON_AR } from '../lib/factors'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Carousel, CarouselContent, CarouselItem, type CarouselApi } from '@/components/ui/carousel'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { CommuteChips } from './CommuteChips'
import { ScoreBreakdown } from './ScoreBreakdown'
import { ScoreSeal } from './ScoreSeal'
import { useRejectFlow } from './useRejectFlow'

const yesNo = (v: boolean | null) => (v == null ? null : v ? 'نعم' : 'لا')

function waLink(phone: string, title: string | null) {
  const digits = phone.replace(/\D/g, '').replace(/^0/, '966')
  return `https://wa.me/${digits}?text=${encodeURIComponent(`السلام عليكم، بخصوص إعلانكم: ${title ?? ''}`)}`
}

function Gallery({ photos }: { photos: string[] }) {
  const [api, setApi] = useState<CarouselApi>()
  const [idx, setIdx] = useState(0)
  useEffect(() => {
    if (!api) return
    const on = () => setIdx(api.selectedScrollSnap())
    on()
    api.on('select', on)
    return () => { api.off('select', on) }
  }, [api])
  const slides = photos.length ? photos : [null]
  return (
    <div className="relative">
      <Carousel setApi={setApi} opts={{ direction: 'rtl' }} aria-label="صور العقار">
        <CarouselContent>
          {slides.map((src, i) => (
            <CarouselItem key={i}>
              <div className="aspect-[4/3] overflow-hidden rounded-2xl bg-muted">
                {src && <img src={src} alt={`صورة ${i + 1}`} loading={i ? 'lazy' : 'eager'} width={1600} height={1200} className="size-full object-cover" />}
              </div>
            </CarouselItem>
          ))}
        </CarouselContent>
      </Carousel>
      {slides.length > 1 && (
        <>
          <Button variant="secondary" size="icon" aria-label="الصورة السابقة" onClick={() => api?.scrollPrev()}
                  className="absolute start-2 top-1/2 -translate-y-1/2 rounded-full opacity-90">
            <ChevronRight aria-hidden strokeWidth={1.75} />
          </Button>
          <Button variant="secondary" size="icon" aria-label="الصورة التالية" onClick={() => api?.scrollNext()}
                  className="absolute end-2 top-1/2 -translate-y-1/2 rounded-full opacity-90">
            <ChevronLeft aria-hidden strokeWidth={1.75} />
          </Button>
          <div className="absolute inset-x-0 bottom-3 flex items-center justify-center gap-2">
            <span className="rounded-full bg-background/90 px-2 py-0.5 text-xs font-medium"><bdi>{idx + 1}/{slides.length}</bdi></span>
          </div>
          <div className="mt-2 flex justify-center gap-1.5" role="tablist" aria-label="اختيار الصورة">
            {slides.map((_, i) => (
              <button key={i} role="tab" aria-selected={i === idx} aria-label={`الصورة ${i + 1}`} onClick={() => api?.scrollTo(i)}
                      className="flex size-6 items-center justify-center rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <span className={cn('size-2 rounded-full', i === idx ? 'bg-primary' : 'bg-muted-foreground/40')} />
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export function ListingDetailSkeleton() {
  return (
    <div className="space-y-4 p-4" aria-busy>
      <Skeleton className="aspect-[4/3] w-full rounded-2xl" />
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-5 w-3/4" />
      <Skeleton className="h-11 w-full" />
    </div>
  )
}

export function ListingDetailView({ id, onClose }: { id: number; onClose?: () => void }) {
  const q = useListing(id)
  const react = useReactWithUndo()
  const rejectFlow = useRejectFlow()
  if (q.isLoading) return <ListingDetailSkeleton />
  if (q.isError || !q.data) {
    return (
      <div className="flex flex-col items-center gap-3 p-8 text-center">
        <p className="text-destructive">تعذّر تحميل العقار. تحقق من الاتصال ثم أعد المحاولة.</p>
        <Button variant="outline" onClick={() => q.refetch()}><RefreshCw aria-hidden />إعادة المحاولة</Button>
      </div>
    )
  }
  const l = q.data
  const rows: [string, string | null][] = [
    ['النوع', PROPERTY_TYPE_AR[l.property_type ?? ''] ?? null],
    ['الغرف', l.bedrooms != null ? formatNumber(l.bedrooms) : null],
    ['دورات المياه', l.bathrooms != null ? formatNumber(l.bathrooms) : null],
    ['الصالات', l.livings != null ? formatNumber(l.livings) : null],
    ['مساحة البناء', l.built_area_m2 != null ? formatArea(l.built_area_m2) : null],
    ['مساحة الأرض', l.land_area_m2 != null ? formatArea(l.land_area_m2) : null],
    ['عمر العقار', l.building_age_years != null ? formatYears(l.building_age_years) : null],
    ['عرض الشارع', l.street_width_m != null ? `${formatNumber(l.street_width_m)} م` : null],
    ['الواجهة', l.facing ? FACING_AR[l.facing] : null],
    ['عدد الشوارع', l.street_count != null ? formatNumber(l.street_count) : null],
    ['الصك', l.deed_type === 'electronic' ? 'إلكتروني' : l.deed_type === 'paper' ? 'ورقي' : null],
    ['غرفة خادمة', yesNo(l.has_maid_room)], ['غرفة سائق', yesNo(l.has_driver_room)],
    ['حوش', yesNo(l.has_yard)], ['مصعد', yesNo(l.has_elevator)],
  ]
  const phone = l.sources.find((s) => s.seller_phone)?.seller_phone
  const visited = l.family_status === 'visited'  // already saved; toggling would reset the visit state
  const saved = l.family_status === 'bookmarked' || visited
  return (
    <div className="space-y-5 p-4 pb-10">
      <Gallery photos={l.photos} />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h2 className="text-2xl font-bold"><bdi>{formatPrice(l.price)}</bdi></h2>
          <p className="text-muted-foreground">{l.title}</p>
          <p className="font-medium">{l.district ?? 'حي غير معروف'}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <ScoreSeal score={l.score} size="lg" />
          {onClose && <Button variant="ghost" size="icon" onClick={onClose} aria-label="إغلاق"><X aria-hidden strokeWidth={1.75} /></Button>}
        </div>
      </div>
      <CommuteChips commutes={l.commutes} />
      {!l.passes_filters && l.filter_reasons.length > 0 && (
        <div role="note" className="rounded-2xl bg-warning-soft px-4 py-3 text-sm text-warning">
          <p className="font-medium">لا يطابق شروطكم:</p>
          <ul className="mt-1 list-inside list-disc">{l.filter_reasons.map((r) => <li key={r}>{REASON_AR[r] ?? r}</li>)}</ul>
        </div>
      )}
      <ScoreBreakdown breakdown={l.score_breakdown} />
      {l.lat != null && (
        <a className="inline-flex items-center gap-1.5 text-sm text-accent underline-offset-4 hover:underline" target="_blank" rel="noreferrer"
           href={`https://www.google.com/maps/search/?api=1&query=${l.lat},${l.lng}`}>
          <MapPin className="size-4" strokeWidth={1.75} aria-hidden />عرض الموقع على خرائط Google
        </a>
      )}
      {l.geo_precision === 'district' && <Badge variant="outline" className="border-warning/40 bg-warning-soft text-warning">الموقع تقريبي (مركز الحي)</Badge>}
      <div className="flex gap-2">
        <Button className="flex-1" variant={saved ? 'default' : 'secondary'} aria-pressed={saved} disabled={visited} onClick={() => react(l.id, saved ? 'unreject' : 'bookmark')}>
          {saved ? <><Check aria-hidden />محفوظ</> : <><Bookmark aria-hidden />حفظ</>}
        </Button>
        <Button className="flex-1" variant="outline" onClick={() => rejectFlow.ask(l.id, l.title)}><X aria-hidden />استبعاد</Button>
      </div>
      {phone && (
        <div className="flex gap-2">
          <Button asChild variant="outline" className="flex-1">
            <a href={`tel:${phone}`}><Phone aria-hidden />اتصال <bdi className="text-xs text-muted-foreground">{phone}</bdi></a>
          </Button>
          <Button asChild variant="outline" className="flex-1">
            <a href={waLink(phone, l.title)} target="_blank" rel="noreferrer"><MessageCircle aria-hidden />واتساب</a>
          </Button>
        </div>
      )}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm md:grid-cols-3">
        {rows.map(([k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="mt-0.5">
              {v == null
                ? <span className="rounded-md bg-warning-soft px-1.5 py-0.5 text-warning">غير مذكور</span>
                : <bdi className="font-medium">{v}</bdi>}
            </dd>
          </div>
        ))}
      </dl>
      {l.description && <p className="max-w-prose whitespace-pre-line text-sm leading-7 text-muted-foreground">{l.description}</p>}
      <div className="flex flex-wrap gap-2">
        {l.sources.map((s) => (
          <Button key={s.url} asChild variant="secondary" size="sm">
            <a href={s.url} target="_blank" rel="noreferrer">
              {s.source === 'aqar' ? 'عقار' : s.source === 'haraj' ? 'حراج' : s.source}
              <ExternalLink aria-hidden strokeWidth={1.75} />
            </a>
          </Button>
        ))}
      </div>
      {rejectFlow.element}
    </div>
  )
}
