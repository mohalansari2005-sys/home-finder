import { Marker } from '@vis.gl/react-maplibre'
import { House } from 'lucide-react'
import type { MapPoint, Place } from '../api/types'
import { COMMUTE_ICONS, formatPrice } from '../lib/format'
import { BaseMap, RIYADH } from './map/BaseMap'
import { cn } from '@/lib/utils'

function pinTone(p: MapPoint) {
  if (p.family_status === 'bookmarked') return 'bg-primary text-primary-foreground'
  if (p.score == null) return 'bg-muted-foreground text-background'
  return p.score >= 75 ? 'bg-primary text-primary-foreground' : p.score >= 50 ? 'bg-seal text-seal-foreground' : 'bg-secondary text-secondary-foreground'
}

interface Props { points: MapPoint[]; places: Place[]; selectedId: number | null; onSelect: (id: number) => void }

export function MapView({ points, places, selectedId, onSelect }: Props) {
  return (
    <BaseMap initialViewState={{ latitude: RIYADH.lat, longitude: RIYADH.lng, zoom: 11 }}>
      {places.map((pl) => {
        const Icon = pl.kind === 'home' ? House : COMMUTE_ICONS.find((c) => c.kind === pl.kind)?.Icon
        return (
          <Marker key={pl.kind} latitude={pl.lat} longitude={pl.lng}>
            <div title={pl.name} className="rounded-full bg-card p-1.5 text-foreground shadow-sm ring-2 ring-foreground">
              {Icon && <Icon className="size-5" strokeWidth={1.75} aria-hidden />}
            </div>
          </Marker>
        )
      })}
      {points.map((p) => (
        <Marker key={p.id} latitude={p.lat} longitude={p.lng} style={p.id === selectedId ? { zIndex: 1 } : undefined}
                onClick={(e) => { e.originalEvent.stopPropagation(); onSelect(p.id) }}>
          <button type="button" aria-label={p.price ? formatPrice(p.price) : 'عقار بدون سعر'}
                  className={cn('cursor-pointer rounded-full px-2.5 py-1 text-xs font-semibold shadow-sm transition-transform motion-reduce:transition-none', pinTone(p),
                    p.id === selectedId && 'scale-110 ring-2 ring-background')}>
            <bdi>{p.price ? formatPrice(p.price).replace(' ر.س', '') : '—'}</bdi>
          </button>
        </Marker>
      ))}
    </BaseMap>
  )
}
