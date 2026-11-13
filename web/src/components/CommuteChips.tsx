import type { ListingCard } from '../api/types'
import { COMMUTE_ICONS, formatMinutes } from '../lib/format'

export function CommuteChips({ commutes }: { commutes: ListingCard['commutes'] }) {
  return (
    <ul className="flex flex-wrap gap-2 text-sm text-muted-foreground">
      {COMMUTE_ICONS.map(({ kind, Icon, label }) => {
        const v = formatMinutes(commutes?.[kind])
        return (
          <li key={kind} aria-label={`${label}: ${v}`} className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1">
            <Icon className="size-4" strokeWidth={1.75} aria-hidden />
            <bdi>{v}</bdi>
          </li>
        )
      })}
    </ul>
  )
}
