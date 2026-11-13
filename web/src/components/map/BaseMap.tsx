import { useState, type ReactNode } from 'react'
import { Map, NavigationControl, type MapProps } from '@vis.gl/react-maplibre'
import type { ExpressionSpecification, Map as MapLibreMap } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { Map as MapIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

/** OpenFreeMap: free vector tiles, no key. Its attribution (OpenFreeMap, OpenMapTiles, OpenStreetMap) comes with the style. */
export const MAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty'
export const RIYADH = { lat: 24.7136, lng: 46.6753 }

const ARABIC_NAME: ExpressionSpecification = ['coalesce', ['get', 'name:ar'], ['get', 'name']]
const LOCALE = {
  'NavigationControl.ZoomIn': 'تكبير',
  'NavigationControl.ZoomOut': 'تصغير',
  'AttributionControl.ToggleAttribution': 'مصادر الخريطة',
  'Map.Title': 'خريطة',
}

let mapLib: Promise<typeof import('maplibre-gl')> | null = null
/** maplibre-gl in its own chunk, loaded on the first map; its worker is a separate file Vite has to be told about. */
function loadMapLib() {
  mapLib ??= Promise.all([import('maplibre-gl'), import('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url')])
    .then(([lib, worker]) => { lib.setWorkerUrl(worker.default); return lib })
  return mapLib
}

/** Street and place labels in Arabic where OpenStreetMap has an Arabic name; road numbers and house numbers stay as they are. */
function preferArabicLabels(map: MapLibreMap) {
  for (const layer of map.getStyle().layers ?? []) {
    if (layer.type !== 'symbol') continue
    const field = map.getLayoutProperty(layer.id, 'text-field')
    if (field != null && JSON.stringify(field).includes('name')) map.setLayoutProperty(layer.id, 'text-field', ARABIC_NAME)
  }
}

export function MapUnavailable({ className }: { className?: string }) {
  return (
    <div className={cn('flex h-full w-full min-h-48 flex-col items-center justify-center gap-2 bg-muted text-muted-foreground', className)}>
      <MapIcon className="size-6" strokeWidth={1.75} aria-hidden />
      <p>الخريطة غير متاحة</p>
    </div>
  )
}

type Props = Omit<MapProps, 'mapStyle' | 'onError' | 'style'> & { className?: string; children?: ReactNode }

/** MapLibre on OpenFreeMap tiles. Falls back to a «الخريطة غير متاحة» panel when the browser cannot start a map (no WebGL). */
export function BaseMap({ className, onLoad, children, ...rest }: Props) {
  const [failed, setFailed] = useState(false)
  if (failed) return <MapUnavailable className={className} />
  return (
    <div className={cn('h-full w-full', className)}>
      <Map mapLib={loadMapLib()} mapStyle={MAP_STYLE} locale={LOCALE} dragRotate={false} touchPitch={false} pitchWithRotate={false}
           style={{ width: '100%', height: '100%' }} {...rest}
           onLoad={(e) => { preferArabicLabels(e.target); onLoad?.(e) }}
           onError={(e) => { if (!e.target) setFailed(true) }}>
        <NavigationControl position="top-left" showCompass={false} />
        {children}
      </Map>
    </div>
  )
}
