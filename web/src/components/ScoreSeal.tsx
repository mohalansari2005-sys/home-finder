import { cn } from '@/lib/utils'

/** Tier by score: palm >= 75, sand-dark 50-74, muted < 50. The number is always shown, colour is never the only signal. */
export function scoreTier(score: number): 'high' | 'mid' | 'low' {
  return score >= 75 ? 'high' : score >= 50 ? 'mid' : 'low'
}
const RING: Record<'high' | 'mid' | 'low', string> = {
  high: 'stroke-primary', mid: 'stroke-warning', low: 'stroke-muted-foreground',
}

/** The fit score as a sand medallion with the number in Kufi and a ring segment showing the tier. */
export function ScoreSeal({ score, size = 'md', className }: { score: number | null; size?: 'md' | 'lg'; className?: string }) {
  if (score == null) return null
  const v = Math.max(0, Math.min(100, Math.round(score)))
  const r = 20
  const c = 2 * Math.PI * r
  const dim = size === 'lg' ? 'size-16 text-2xl' : 'size-11 text-base'
  return (
    <span role="img" aria-label={`درجة الملاءمة ${v}`}
          className={cn('relative inline-flex items-center justify-center rounded-full bg-seal font-display font-bold text-seal-foreground shadow-sm', dim, className)}>
      <svg viewBox="0 0 48 48" aria-hidden className="absolute inset-0 size-full -rotate-90">
        <circle cx="24" cy="24" r={r} fill="none" strokeWidth="3" className="stroke-seal-foreground/15" />
        <circle cx="24" cy="24" r={r} fill="none" strokeWidth="3" strokeLinecap="round" className={RING[scoreTier(v)]}
                strokeDasharray={`${(c * v) / 100} ${c}`} />
      </svg>
      <span className="relative" aria-hidden>{v}</span>
    </span>
  )
}
