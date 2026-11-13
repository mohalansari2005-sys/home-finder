import { Bath, BedDouble, Bookmark, BookmarkCheck, House, Ruler, TrendingDown, X } from 'lucide-react'
import type { ListingCard as T, ReactKind } from '../api/types'
import { formatArea, formatNumber, formatPrice, formatRooms, PROPERTY_TYPE_AR } from '../lib/format'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { CommuteChips } from './CommuteChips'
import { ScoreSeal } from './ScoreSeal'

interface Props { listing: T; selected?: boolean; onOpen: (id: number) => void; onReact: (k: ReactKind) => void }

/** Flat tile: photo with the seal, then text on the page background. No shadow. */
export function ListingCard({ listing: l, selected, onOpen, onReact }: Props) {
  const saved = l.family_status === 'bookmarked'
  const area = l.built_area_m2 ?? l.land_area_m2
  return (
    <article onClick={() => onOpen(l.id)}
             className={cn('cursor-pointer space-y-3 rounded-2xl border p-2 transition-transform active:scale-[0.99] motion-reduce:active:scale-100',
               selected ? 'border-primary' : 'border-transparent')}>
      <div className="relative aspect-[4/3] overflow-hidden rounded-2xl bg-muted">
        {l.photo_url
          ? <img src={l.photo_url} alt="" loading="lazy" width={640} height={480} className="size-full object-cover" />
          : <div className="flex size-full items-center justify-center text-muted-foreground"><House className="size-6" strokeWidth={1.75} aria-hidden /></div>}
        <ScoreSeal score={l.score} className="absolute start-2 top-2" />
        <div className="absolute end-2 top-2 flex flex-col items-end gap-1.5">
          {l.family_status === 'new' && <Badge>جديد</Badge>}
          {l.price_drop && (
            <Badge data-testid="price-drop" className="h-6 bg-card px-2.5 text-sm font-semibold text-success">
              <TrendingDown strokeWidth={2} aria-hidden />
              انخفض <bdi>{formatNumber(l.price_drop.from - l.price_drop.to)}</bdi> ر.س
            </Badge>
          )}
          {l.status === 'removed' && <Badge variant="secondary" className="bg-muted text-muted-foreground">الإعلان محذوف</Badge>}
        </div>
      </div>
      <div className="space-y-2 px-1">
        <div className="flex items-baseline gap-2">
          <span className="font-display text-xl font-bold"><bdi>{formatPrice(l.price)}</bdi></span>
          {l.price_drop && <del className="text-sm text-muted-foreground"><bdi>{formatPrice(l.price_drop.from)}</bdi></del>}
        </div>
        {l.title && <p className="line-clamp-1 text-sm text-muted-foreground">{l.title}</p>}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          <span>{PROPERTY_TYPE_AR[l.property_type ?? ''] ?? 'عقار'}</span>
          <span className="font-medium">{l.district ?? 'حي غير معروف'}</span>
          {l.bedrooms != null && <span className="inline-flex items-center gap-1"><BedDouble className="size-4 text-muted-foreground" strokeWidth={1.75} aria-hidden /><bdi>{formatRooms(l.bedrooms)}</bdi></span>}
          {l.bathrooms != null && <span className="inline-flex items-center gap-1"><Bath className="size-4 text-muted-foreground" strokeWidth={1.75} aria-hidden /><bdi>{l.bathrooms}</bdi></span>}
          <span className="inline-flex items-center gap-1"><Ruler className="size-4 text-muted-foreground" strokeWidth={1.75} aria-hidden /><bdi>{formatArea(area)}</bdi></span>
        </div>
        <CommuteChips commutes={l.commutes} />
        <div className="flex gap-2 pt-1">
          <Button variant={saved ? 'default' : 'secondary'} aria-pressed={saved} className="flex-1"
                  onClick={(e) => { e.stopPropagation(); onReact(saved ? 'unreject' : 'bookmark') }}>
            {saved ? <BookmarkCheck aria-hidden /> : <Bookmark aria-hidden />}
            {saved ? 'محفوظ' : 'حفظ'}
          </Button>
          <Button variant="outline" className="flex-1" onClick={(e) => { e.stopPropagation(); onReact('reject') }}>
            <X aria-hidden />
            استبعاد
          </Button>
        </div>
      </div>
    </article>
  )
}
