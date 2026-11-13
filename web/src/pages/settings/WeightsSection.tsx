import { useState } from 'react'
import { Lock, LockOpen, RotateCcw, Save } from 'lucide-react'
import type { Preferences } from '../../api/types'
import { FACTOR_AR, type Factor } from '../../lib/factors'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Slider } from '@/components/ui/slider'

interface Props {
  prefs: Preferences
  onSave: (patch: Record<string, unknown>) => void
  pending?: boolean
  error?: string | null
}

const round1 = (n: number) => Math.round(n * 10) / 10

export function WeightsSection({ prefs, onSave, pending, error }: Props) {
  const [draft, setDraft] = useState<Record<string, number>>({})
  const changed = Object.keys(draft).length > 0
  return (
    <Card className="rounded-3xl" aria-labelledby="weights-title" role="region">
      <CardHeader>
        <CardTitle id="weights-title" className="font-display text-lg font-bold">أهمية العوامل</CardTitle>
        <CardDescription>العوامل التي تعدّلها تُثبَّت ولا يغيّرها التعلّم التلقائي.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ul className="space-y-3">
          {(Object.keys(FACTOR_AR) as Factor[]).map((f) => {
            const locked = prefs.locked_weights.includes(f)
            const value = draft[f] ?? prefs.weights[f] ?? 0
            return (
              <li key={f} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-3 gap-y-2 md:grid-cols-[9rem_minmax(0,1fr)_2.5rem_auto]">
                <span className="col-start-1 row-start-1 flex flex-wrap items-center gap-1.5 text-sm">
                  {FACTOR_AR[f]}
                  {locked && (
                    <span role="img" aria-label={`${FACTOR_AR[f]} (مثبت)`} className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
                      <Lock className="size-3" strokeWidth={1.75} aria-hidden />مثبت
                    </span>
                  )}
                </span>
                <Slider dir="rtl" min={0} max={3} step={0.1} value={[value]} aria-label={FACTOR_AR[f]}
                        onValueChange={([v]) => setDraft({ ...draft, [f]: round1(v) })}
                        className="col-span-3 row-start-2 md:col-span-1 md:col-start-2 md:row-start-1" />
                <bdi className="col-start-2 row-start-1 text-end text-sm font-semibold tabular-nums md:col-start-3">{value.toFixed(1)}</bdi>
                {locked ? (
                  <Button variant="secondary" size="icon" aria-pressed aria-label={`إلغاء تثبيت ${FACTOR_AR[f]}`}
                          onClick={() => onSave({ unlock: [f] })} className="col-start-3 row-start-1 bg-primary/10 text-primary md:col-start-4">
                    <Lock aria-hidden strokeWidth={1.75} />
                  </Button>
                ) : (
                  <Button variant="ghost" size="icon" aria-pressed={false} aria-label={`تثبيت ${FACTOR_AR[f]}`}
                          onClick={() => onSave({ weights: { [f]: value } })} className="col-start-3 row-start-1 text-muted-foreground md:col-start-4">
                    <LockOpen aria-hidden strokeWidth={1.75} />
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <div className="flex flex-wrap gap-2">
          <Button disabled={!changed || pending} onClick={() => { onSave({ weights: draft }); setDraft({}) }}>
            <Save aria-hidden />حفظ الأهمية
          </Button>
          <Button variant="outline" disabled={pending} onClick={() => onSave({ reset_weights: true })}>
            <RotateCcw aria-hidden />استعادة الافتراضي
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
