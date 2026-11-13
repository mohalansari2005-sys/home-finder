import { Check, ChevronRight, Columns2, House, RefreshCw, X } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { useCompare } from '../api/hooks'
import type { ListingDetail } from '../api/types'
import { ScoreSeal } from '../components/ScoreSeal'
import { COMPARE_ROWS, bestIndex, parseIds } from '../lib/compare'
import { PROPERTY_TYPE_AR, pluralAr } from '../lib/format'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

const title = (l: ListingDetail) => l.title ?? `${PROPERTY_TYPE_AR[l.property_type ?? ''] ?? 'عقار'} ${l.district ? `في ${l.district}` : ''}`.trim()
const LABEL_COL = 'sticky start-0 z-10 w-28 min-w-28 border-e bg-card md:w-36 md:min-w-36'

function Empty({ back }: { back: string }) {
  return (
    <div className="flex flex-col items-center gap-3 p-10 text-center text-muted-foreground">
      <Columns2 className="size-6" strokeWidth={1.75} aria-hidden />
      <p>اختاروا عقارين على الأقل من القائمة للمقارنة بينها</p>
      <Button asChild variant="secondary"><Link to={back}>العودة إلى العقارات</Link></Button>
    </div>
  )
}

function TableSkeleton() {
  return (
    <div className="space-y-3" aria-busy>
      <Skeleton className="h-40 w-full rounded-3xl" />
      <Skeleton className="h-64 w-full rounded-3xl" />
    </div>
  )
}

export function ComparePage() {
  const [params, setParams] = useSearchParams()
  const nav = useNavigate()
  const ids = parseIds(params.get('ids'))
  const q = useCompare(ids)
  const back = ids.length ? `/?compare=${ids.join(',')}` : '/?compare='

  const remove = (id: number) => {
    const rest = ids.filter((x) => x !== id)
    if (rest.length < 2) return nav(rest.length ? `/?compare=${rest.join(',')}` : '/?compare=', { replace: true })
    setParams({ ids: rest.join(',') }, { replace: true })
  }

  if (ids.length < 2) return <div className="mx-auto max-w-6xl"><Empty back={back} /></div>
  const list = q.data ?? []
  const n = list.length || ids.length
  const heading = `مقارنة ${pluralAr(n, { zero: 'العقارات', one: 'عقار واحد', two: 'عقارين', few: `${n} عقارات`, many: `${n} عقارًا`, other: `${n} عقار` })}`

  return (
    <div className="mx-auto min-w-0 max-w-6xl space-y-5 px-4 py-5 md:px-6 xl:px-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1">
          <Button asChild variant="ghost" size="icon" aria-label="العودة إلى العقارات" className="size-11">
            <Link to={back}><ChevronRight aria-hidden /></Link>
          </Button>
          <h1 className="font-display text-xl font-bold md:text-2xl">{heading}</h1>
        </div>
        <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
          <span className="size-3.5 rounded bg-primary/10 ring-1 ring-primary" aria-hidden />الأفضل في كل صف
        </span>
      </div>

      {q.isLoading ? <TableSkeleton /> : q.isError || list.length < 2 ? (
        <div className="flex flex-col items-center gap-3 p-8 text-center">
          <p className="text-destructive">تعذّر تحميل المقارنة. تحقق من الاتصال ثم أعد المحاولة.</p>
          <Button variant="outline" onClick={() => q.refetch()}><RefreshCw aria-hidden />إعادة المحاولة</Button>
        </div>
      ) : (
        // own scroll container: wide tables never widen the page; the label column stays pinned while scrolling
        <div className="min-w-0 overflow-x-auto rounded-3xl border bg-card" data-testid="compare-scroll">
          <table className="w-full border-separate border-spacing-0 text-[15px]">
            <thead>
              <tr>
                <th scope="col" className={cn(LABEL_COL, 'border-b p-3 text-start align-bottom font-medium text-muted-foreground md:p-4')}>
                  <span className="sr-only">الخاصية</span>
                </th>
                {list.map((l) => (
                  <th key={l.id} scope="col" className="min-w-44 border-b border-s p-3 text-start align-top font-normal md:min-w-44 md:p-4">
                    <div className="space-y-2.5">
                      <div className="relative h-28 overflow-hidden rounded-xl bg-muted md:h-32">
                        {l.photo_url
                          ? <img src={l.photo_url} alt="" loading="lazy" width={320} height={240} className="size-full object-cover" />
                          : <div className="flex size-full items-center justify-center text-muted-foreground"><House className="size-6" strokeWidth={1.75} aria-hidden /></div>}
                        <ScoreSeal score={l.score} className="absolute start-2 top-2" />
                        <Button variant="secondary" size="icon" aria-label={`إزالة ${title(l)} من المقارنة`} onClick={() => remove(l.id)}
                                className="absolute end-1 top-1 size-11 rounded-full bg-card shadow-sm hover:bg-card/90">
                          <X className="size-4" aria-hidden />
                        </Button>
                      </div>
                      <Link to={`/listing/${l.id}`} className="block rounded-md font-display font-bold underline-offset-4 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring">
                        {title(l)}
                      </Link>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {COMPARE_ROWS.map((r) => {
                const vals = list.map(r.value)
                const best = bestIndex(vals.map((v) => (typeof v === 'number' ? v : null)), r.better)
                return (
                  <tr key={r.key}>
                    <th scope="row" className={cn(LABEL_COL, 'border-t p-3 text-start font-medium text-muted-foreground md:px-4')}>{r.label}</th>
                    {vals.map((v, i) => (
                      <td key={list[i].id} data-testid={best === i ? 'best-cell' : undefined}
                          className={cn('border-s border-t p-3 md:px-4', best === i && 'bg-primary/10 font-semibold')}>
                        {v == null
                          ? <span className="rounded-md bg-warning-soft px-1.5 py-0.5 text-warning">غير مذكور</span>
                          : (
                            <span className="inline-flex items-center gap-1.5">
                              <bdi>{r.fmt(v)}</bdi>
                              {best === i && <Check className="size-4 text-primary" strokeWidth={2} aria-label="الأفضل" />}
                            </span>
                          )}
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
