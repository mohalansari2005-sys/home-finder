import { Lightbulb } from 'lucide-react'
import { useApplySuggestion, useDismissSuggestion, useSuggestions } from '../api/hooks'
import { Button } from '@/components/ui/button'

/** Amber card per filter suggestion learned from repeated reject reasons. Renders nothing when there are none. */
export function SuggestionBanner() {
  const q = useSuggestions()
  const apply = useApplySuggestion()
  const dismiss = useDismissSuggestion()
  const items = q.data ?? []
  if (!items.length) return null
  const busy = apply.isPending || dismiss.isPending
  return (
    <div className="space-y-3 px-4 pt-4">
      {items.map((s) => (
        <section key={s.code} aria-label="اقتراح" className="space-y-2.5 rounded-2xl bg-warning-soft p-4 text-warning">
          <div className="flex items-start gap-2.5">
            <Lightbulb className="mt-1 size-4 shrink-0" strokeWidth={1.75} aria-hidden />
            <p className="text-[15px]">{s.text}</p>
          </div>
          <div className="flex gap-2">
            <Button size="sm" className="h-10 px-4" disabled={busy} onClick={() => apply.mutate(s.code)}>تطبيق</Button>
            <Button size="sm" variant="ghost" className="h-10 px-4 text-warning hover:bg-warning/10 hover:text-warning" disabled={busy}
                    onClick={() => dismiss.mutate(s.code)}>لا شكراً</Button>
          </div>
        </section>
      ))}
    </div>
  )
}
