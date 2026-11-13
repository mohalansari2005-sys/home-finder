import { CalendarPlus, Home } from 'lucide-react'
import type { VisitGroup } from '../../api/types'
import { formatNumber, pluralAr } from '../../lib/format'
import { ScoreSeal } from '../ScoreSeal'
import { Button } from '@/components/ui/button'

export function GroupCard({ group, onPlan }: { group: VisitGroup; onPlan: (g: VisitGroup) => void }) {
  const n = group.count
  const c = formatNumber(n)
  const count = pluralAr(n, { zero: 'لا توجد عقارات', one: 'عقار واحد', two: 'عقاران', few: `${c} عقارات`, many: `${c} عقارًا`, other: `${c} عقار` })
  const thumbs = group.listings.slice(0, 3)
  return (
    <li className="flex flex-col gap-3 rounded-2xl border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-display text-lg font-bold leading-snug text-balance">{group.districts.join('، ')}</h3>
          <p className="text-sm text-muted-foreground">{count}</p>
        </div>
        {group.avg_score != null && (
          <div className="flex shrink-0 items-center gap-2 text-sm text-muted-foreground">
            <span>متوسط الملاءمة</span>
            <ScoreSeal score={group.avg_score} size="sm" />
          </div>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2">
        {thumbs.map((l) => (
          <span key={l.id} className="flex aspect-[4/3] items-center justify-center overflow-hidden rounded-xl bg-muted text-muted-foreground">
            {l.photo_url
              ? <img src={l.photo_url} alt="" loading="lazy" width={320} height={240} className="size-full object-cover" />
              : <Home className="size-5" strokeWidth={1.75} aria-hidden />}
          </span>
        ))}
      </div>
      <Button size="lg" className="h-11 rounded-xl" onClick={() => onPlan(group)}>
        <CalendarPlus aria-hidden />خطط زيارة
      </Button>
    </li>
  )
}
