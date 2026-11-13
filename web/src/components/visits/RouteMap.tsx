import { useEffect, useState } from 'react'
import { Layer, Marker, Source } from '@vis.gl/react-maplibre'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { House } from 'lucide-react'
import type { TripStop } from '../../api/types'
import { BaseMap, RIYADH } from '../map/BaseMap'
import { cn } from '@/lib/utils'

export interface LatLng { lat: number; lng: number }
interface Props { stops: TripStop[]; origin: LatLng | null; activeId: number | null; onSelect: (stopId: number) => void; className?: string }

/** Numbered markers in visit order plus the origin, joined by straight dashed lines in that order (a guide to the
 *  sequence, not the roads driven). Tapping a marker selects its stop (the page scrolls to it). */
export function RouteMap({ stops, origin, activeId, onSelect, className }: Props) {
  const [map, setMap] = useState<MapLibreMap | null>(null)
  const pts = [...stops].sort((a, b) => a.position - b.position)
    .flatMap((s) => (s.listing.lat != null && s.listing.lng != null ? [{ stop: s, at: { lat: s.listing.lat, lng: s.listing.lng } }] : []))
  const path = [...(origin ? [origin] : []), ...pts.map((p) => p.at), ...(origin ? [origin] : [])]
  const coords = path.map((p) => [p.lng, p.lat])
  const fitKey = JSON.stringify(coords)

  // fit every point whenever they change (the origin arrives after the trip, from the places query)
  useEffect(() => {
    const c = JSON.parse(fitKey) as number[][]
    if (!map || !c.length) return
    const lngs = c.map((p) => p[0]), lats = c.map((p) => p[1])
    map.fitBounds([Math.min(...lngs), Math.min(...lats), Math.max(...lngs), Math.max(...lats)], { padding: { top: 64, bottom: 72, left: 56, right: 56 }, maxZoom: 15, duration: 0 })
  }, [map, fitKey])

  const line = { type: 'Feature' as const, properties: {}, geometry: { type: 'LineString' as const, coordinates: coords } }
  return (
    <BaseMap initialViewState={{ latitude: RIYADH.lat, longitude: RIYADH.lng, zoom: 11 }} onLoad={(e) => setMap(e.target)}
             className={cn('overflow-hidden rounded-2xl bg-muted', className)}>
      {path.length > 1 && (
        <Source id="route" type="geojson" data={line}>
          <Layer id="route-line" type="line" layout={{ 'line-join': 'round', 'line-cap': 'round' }}
                 paint={{ 'line-color': '#0f766e', 'line-width': 3, 'line-opacity': 0.7, 'line-dasharray': [2, 1.5] }} />
        </Source>
      )}
      {origin && (
        <Marker latitude={origin.lat} longitude={origin.lng}>
          <div title="نقطة الانطلاق" className="rounded-full bg-card p-1.5 text-foreground shadow-sm ring-2 ring-foreground"><House className="size-5" strokeWidth={1.75} aria-hidden /></div>
        </Marker>
      )}
      {pts.map(({ stop, at }) => (
        <Marker key={stop.id} latitude={at.lat} longitude={at.lng} style={stop.id === activeId ? { zIndex: 1 } : undefined}
                onClick={(e) => { e.originalEvent.stopPropagation(); onSelect(stop.id) }}>
          <button type="button" title={stop.listing.title ?? undefined} aria-label={`المحطة ${stop.position + 1}`}
                  className={cn('flex size-8 cursor-pointer items-center justify-center rounded-full bg-primary font-display text-sm font-bold text-primary-foreground shadow-sm transition-transform motion-reduce:transition-none',
                    stop.id === activeId && 'scale-110 ring-2 ring-background')}>
            <bdi>{stop.position + 1}</bdi>
          </button>
        </Marker>
      ))}
    </BaseMap>
  )
}
