import { Bot, ChevronDown, ChevronLeft, History, Sparkles, User, type LucideIcon } from 'lucide-react'
import { usePreferenceChanges } from '../../api/hooks'
import type { PreferenceChange } from '../../api/types'
import { fieldLabel } from '../../lib/factors'
import { FACING_AR, formatNumber, formatRelative, PROPERTY_TYPE_AR } from '../../lib/format'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Skeleton } from '@/components/ui/skeleton'

const SOURCE: Record<PreferenceChange['source'], { Icon: LucideIcon; label: string }> = {
  user: { Icon: User, label: 'يدويًا' }, agent: { Icon: Bot, label: 'من المحادثة' }, learner: { Icon: Sparkles, label: 'تعلّم تلقائي' },
}

function formatValue(v: unknown): string {
  if (v == null) return 'بلا حد'
  if (typeof v === 'number') return formatNumber(v)
  if (typeof v === 'boolean') return v ? 'نعم' : 'لا'
  if (Array.isArray(v)) return v.length ? v.map((x) => PROPERTY_TYPE_AR[String(x)] ?? FACING_AR[String(x)] ?? String(x)).join('، ') : 'لا شيء'
  if (typeof v === 'object') return Object.entries(v as Record<string, unknown>).map(([k, x]) => `${k} ${formatValue(x)}`).join('، ')
  return String(v)
}

function Entry({ c }: { c: PreferenceChange }) {
  const { Icon, label } = SOURCE[c.source]
  const rows = Object.entries(c.diff)
  return (
    <li className="border-s-2 ps-3">
      <Collapsible>
        <div className="flex items-start gap-2">
          <Icon className="mt-1 size-4 shrink-0 text-muted-foreground" strokeWidth={1.75} aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="text-sm">{c.explanation}</p>
            <p className="text-xs text-muted-foreground"><span>{label}</span> <span>{formatRelative(new Date(c.at))}</span></p>
          </div>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="عرض التفاصيل" className="group -my-2 shrink-0">
              <ChevronDown className="size-4 transition-transform group-data-[state=open]:rotate-180 motion-reduce:transition-none" strokeWidth={1.75} aria-hidden />
            </Button>
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent>
          <ul className="mt-2 space-y-1.5 text-sm">
            {rows.map(([k, d]) => (
              <li key={k} className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span className="font-medium">{fieldLabel(k)}</span>
                <span className="inline-flex items-center gap-1 text-muted-foreground">
                  <bdi>{formatValue(d.from)}</bdi><ChevronLeft className="size-3.5" strokeWidth={1.75} aria-hidden /><bdi className="text-foreground">{formatValue(d.to)}</bdi>
                </span>
              </li>
            ))}
          </ul>
        </CollapsibleContent>
      </Collapsible>
    </li>
  )
}

function HistoryList({ changes }: { changes: PreferenceChange[] }) {
  const learned = changes.filter((c) => c.source === 'learner')
  const manual = changes.filter((c) => c.source !== 'learner')
  const list = (items: PreferenceChange[]) => <ol className="space-y-4">{items.map((c, i) => <Entry key={`${c.at}-${i}`} c={c} />)}</ol>
  if (!learned.length) return list(manual)
  return (
    <div className="space-y-6">
      <section aria-labelledby="learned-title" className="space-y-3">
        <h3 id="learned-title" className="flex items-center gap-2 text-base font-semibold">
          <Sparkles className="size-4 text-primary" strokeWidth={1.75} aria-hidden />ما تعلّمه التطبيق
        </h3>
        {list(learned)}
      </section>
      {manual.length > 0 && (
        <section aria-labelledby="manual-title" className="space-y-3">
          <h3 id="manual-title" className="text-base font-semibold">تعديلاتكم وتعديلات المساعد</h3>
          {list(manual)}
        </section>
      )}
    </div>
  )
}

export function HistorySection() {
  const q = usePreferenceChanges()
  return (
    <Card className="rounded-3xl" role="region" aria-labelledby="history-title">
      <CardHeader><CardTitle id="history-title" className="font-display text-lg font-bold">سجل التغييرات</CardTitle></CardHeader>
      <CardContent>
        {q.isError ? (
          <div className="flex flex-col items-start gap-3">
            <p className="text-destructive">تعذّر تحميل السجل.</p>
            <Button variant="outline" onClick={() => q.refetch()}>إعادة المحاولة</Button>
          </div>
        ) : !q.data ? (
          <div className="space-y-3" aria-busy><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-full" /></div>
        ) : q.data.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-4 text-center text-muted-foreground">
            <History className="size-6" strokeWidth={1.75} aria-hidden />
            <p>لا توجد تغييرات بعد. ستظهر هنا تعديلاتكم وتعديلات المساعد.</p>
          </div>
        ) : (
          <HistoryList changes={q.data} />
        )}
      </CardContent>
    </Card>
  )
}
