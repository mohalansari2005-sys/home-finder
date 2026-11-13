import { useState } from 'react'
import { ChevronDown, Minus, Plus } from 'lucide-react'
import type { ScoreBreakdown as Breakdown } from '../api/types'
import { FACTOR_AR, type Factor } from '../lib/factors'
import { formatNumber } from '../lib/format'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

const label = (f: string) => FACTOR_AR[f as Factor] ?? f

function Reason({ factor, positive }: { factor: string; positive: boolean }) {
  const Icon = positive ? Plus : Minus
  return (
    <li className="flex items-center gap-2 text-[15px]">
      <span aria-hidden className={cn('flex size-6 shrink-0 items-center justify-center rounded-full',
        positive ? 'bg-primary/10 text-primary' : 'bg-destructive/10 text-destructive')}>
        <Icon className="size-3.5" strokeWidth={2.5} />
      </span>
      <span data-testid={positive ? 'plus' : 'minus'}>{label(factor)}</span>
      <span className="sr-only">{positive ? 'يرفع التقييم' : 'يخفض التقييم'}</span>
    </li>
  )
}

/** "Why this score": the three biggest pluses and minuses, with every factor behind a toggle. */
export function ScoreBreakdown({ breakdown }: { breakdown: Breakdown | null }) {
  const [open, setOpen] = useState(false)
  if (!breakdown || breakdown.total == null) {
    return <p className="text-sm text-muted-foreground">لا يوجد تقييم بعد</p>
  }
  const pluses = breakdown.contributions.filter((c) => c.delta > 0).sort((a, b) => b.delta - a.delta).slice(0, 3)
  const minuses = breakdown.contributions.filter((c) => c.delta < 0).sort((a, b) => a.delta - b.delta).slice(0, 3)
  return (
    <section aria-labelledby="why-score" className="space-y-3 rounded-3xl bg-card p-4 ring-1 ring-foreground/10">
      <h2 id="why-score" className="text-[17px] font-semibold">لماذا <bdi>{formatNumber(Math.round(breakdown.total))}</bdi>؟</h2>
      <Collapsible open={open} onOpenChange={setOpen} className="space-y-3">
        <ul className="space-y-2">
          {pluses.map((c) => <Reason key={c.factor} factor={c.factor} positive />)}
          {minuses.map((c) => <Reason key={c.factor} factor={c.factor} positive={false} />)}
        </ul>
        <CollapsibleTrigger asChild>
          <Button variant="ghost" className="-ms-3 text-accent">
            كل التفاصيل
            <ChevronDown aria-hidden className={cn('transition-transform motion-reduce:transition-none', open && 'rotate-180')} strokeWidth={1.75} />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="space-y-3">
          <ul className="space-y-2.5">
            {breakdown.contributions.map((c) => (
              <li key={c.factor} className="grid grid-cols-[8rem_minmax(0,1fr)_2.5rem] items-center gap-3 text-sm">
                <span>{label(c.factor)}</span>
                <Progress value={Math.round(c.value * 100)} aria-label={`${label(c.factor)}: ${Math.round(c.value * 100)}%`}
                          className={cn('h-2', c.delta < 0 && '[&>div]:bg-destructive')} />
                <bdi className="text-end text-muted-foreground">{c.delta > 0 ? '+' : ''}{c.delta.toFixed(1)}</bdi>
              </li>
            ))}
          </ul>
          {breakdown.missing.length > 0 && (
            <p className="rounded-xl bg-warning-soft px-3 py-2 text-sm text-warning">
              بيانات ناقصة: {breakdown.missing.map(label).join('، ')}
            </p>
          )}
        </CollapsibleContent>
      </Collapsible>
    </section>
  )
}
