import { formatClock } from '../../lib/format'

/** "16:10" -> <bdi>4:10</bdi> م. Digits are an LTR island; the period stays Arabic. */
export function Clock({ at }: { at: string | null | undefined }) {
  const c = formatClock(at)
  if (!c) return <span aria-label="الوقت غير محدد">—</span>
  return <><bdi>{c.time}</bdi> {c.period}</>
}

/** "4:10 – 4:40 م" (the period is repeated only when it changes). */
export function ClockRange({ from, to, ...rest }: { from: string | null; to: string | null } & React.HTMLAttributes<HTMLSpanElement>) {
  const a = formatClock(from)
  const b = formatClock(to)
  if (!a) return <span {...rest}>—</span>
  if (!b) return <span {...rest}><Clock at={from} /></span>
  return (
    <span {...rest}>
      <bdi>{a.time}</bdi>{a.period !== b.period && ` ${a.period}`} – <bdi>{b.time}</bdi> {b.period}
    </span>
  )
}
