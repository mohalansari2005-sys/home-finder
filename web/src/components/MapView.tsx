import { AdvancedMarker, APIProvider, Map } from '@vis.gl/react-google-maps'
import { Map as MapIcon } from 'lucide-react'
import type { MapPoint, Place } from '../api/types'
import { COMMUTE_ICONS, formatPrice } from '../lib/format'
import { cn } from '@/lib/utils'

const KEY = import.meta.env.VITE_GOOGLE_MAPS_KEY as string | undefined
const MAP_ID = (import.meta.env.VITE_GOOGLE_MAP_ID as string | undefined) || 'DEMO_MAP_ID'
const RIYADH = { lat: 24.7136, lng: 46.6753 }

function pinTone(p: MapPoint) {
  if (p.family_status === 'bookmarked') return 'bg-primary text-primary-foreground'
  if (p.score == null) return 'bg-muted-foreground text-background'
  return p.score >= 75 ? 'bg-primary text-primary-foreground' : p.score >= 50 ? 'bg-seal text-seal-foreground' : 'bg-secondary text-secondary-foreground'
}

interface Props { points: MapPoint[]; places: Place[]; selectedId: number | null; onSelect: (id: number) => void }

export function MapView({ points, places, selectedId, onSelect }: Props) {
  if (!KEY) {
    return (
      <div className="flex h-full min-h-48 flex-col items-center justify-center gap-2 bg-muted text-muted-foreground">
        <MapIcon className="size-6" strokeWidth={1.75} aria-hidden />
        <p>الخريطة غير متاحة</p>
      </div>
    )
  }
  return (
    <APIProvider apiKey={KEY} language="ar" region="SA">
      <Map defaultCenter={RIYADH} defaultZoom={11} mapId={MAP_ID} gestureHandling="greedy" disableDefaultUI={false} className="size-full">
        {points.map((p) => (
          <AdvancedMarker key={p.id} position={{ lat: p.lat, lng: p.lng }} onClick={() => onSelect(p.id)} zIndex={p.id === selectedId ? 1000 : undefined}>
            <div className={cn('rounded-full px-2.5 py-1 text-xs font-semibold shadow-sm transition-transform', pinTone(p),
              p.id === selectedId && 'scale-110 ring-2 ring-background')}>
              <bdi>{p.price ? formatPrice(p.price).replace(' ر.س', '') : '—'}</bdi>
            </div>
          </AdvancedMarker>
        ))}
        {places.map((pl) => {
          const Icon = COMMUTE_ICONS.find((c) => c.kind === pl.kind)?.Icon
          return (
            <AdvancedMarker key={pl.kind} position={{ lat: pl.lat, lng: pl.lng }} title={pl.name}>
              <div className="rounded-full bg-card p-1.5 text-foreground shadow-sm ring-2 ring-foreground">
                {Icon && <Icon className="size-5" strokeWidth={1.75} aria-hidden />}
              </div>
            </AdvancedMarker>
          )
        })}
      </Map>
    </APIProvider>
  )
}
