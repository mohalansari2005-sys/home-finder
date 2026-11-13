import { AdvancedMarker, APIProvider, Map } from '@vis.gl/react-google-maps'
import { House, Map as MapIcon } from 'lucide-react'
import type { TripStop } from '../../api/types'
import { cn } from '@/lib/utils'

const KEY = import.meta.env.VITE_GOOGLE_MAPS_KEY as string | undefined
const MAP_ID = (import.meta.env.VITE_GOOGLE_MAP_ID as string | undefined) || 'DEMO_MAP_ID'
const RIYADH = { lat: 24.7136, lng: 46.6753 }

export interface LatLng { lat: number; lng: number }
interface Props { stops: TripStop[]; origin: LatLng | null; activeId: number | null; onSelect: (stopId: number) => void; className?: string }

/** Numbered markers in visit order plus the origin. Tapping a marker selects its stop (the page scrolls to it). */
export function RouteMap({ stops, origin, activeId, onSelect, className }: Props) {
  const pts = stops.flatMap((s) => (s.listing.lat != null && s.listing.lng != null ? [{ stop: s, at: { lat: s.listing.lat, lng: s.listing.lng } }] : []))
  if (!KEY) {
    return (
      <div className={cn('flex min-h-48 flex-col items-center justify-center gap-2 rounded-2xl bg-muted text-muted-foreground', className)}>
        <MapIcon className="size-6" strokeWidth={1.75} aria-hidden />
        <p>الخريطة غير متاحة</p>
      </div>
    )
  }
  const all = [...pts.map((p) => p.at), ...(origin ? [origin] : [])]
  const bounds = all.length ? {
    north: Math.max(...all.map((p) => p.lat)), south: Math.min(...all.map((p) => p.lat)),
    east: Math.max(...all.map((p) => p.lng)), west: Math.min(...all.map((p) => p.lng)),
  } : null
  return (
    <div className={cn('overflow-hidden rounded-2xl bg-muted', className)}>
      <APIProvider apiKey={KEY} language="ar" region="SA">
        <Map {...(bounds ? { defaultBounds: { ...bounds, top: 48, bottom: 48, left: 48, right: 48 } } : { defaultCenter: RIYADH, defaultZoom: 11 })}
             mapId={MAP_ID} gestureHandling="greedy" className="size-full">
          {origin && (
            <AdvancedMarker position={origin} title="نقطة الانطلاق">
              <div className="rounded-full bg-card p-1.5 text-foreground shadow-sm ring-2 ring-foreground"><House className="size-5" strokeWidth={1.75} aria-hidden /></div>
            </AdvancedMarker>
          )}
          {pts.map(({ stop, at }) => (
            <AdvancedMarker key={stop.id} position={at} onClick={() => onSelect(stop.id)} zIndex={stop.id === activeId ? 1000 : undefined} title={stop.listing.title ?? undefined}>
              <div className={cn('flex size-8 items-center justify-center rounded-full bg-primary font-display text-sm font-bold text-primary-foreground shadow-sm transition-transform motion-reduce:transition-none',
                stop.id === activeId && 'scale-110 ring-2 ring-background')}>
                <bdi>{stop.position + 1}</bdi>
              </div>
            </AdvancedMarker>
          ))}
        </Map>
      </APIProvider>
    </div>
  )
}
