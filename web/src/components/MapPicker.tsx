import { useState } from 'react'
import { Marker } from '@vis.gl/react-maplibre'
import { Map as MapIcon } from 'lucide-react'
import { parseLatLng } from '../lib/factors'
import { formatDecimal } from '../lib/format'
import { BaseMap, RIYADH } from './map/BaseMap'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export interface LatLng { lat: number; lng: number }
interface Props { value: LatLng | null; onChange: (v: LatLng | null) => void; id: string }

const fmt = (v: LatLng | null) => (v ? `${formatDecimal(v.lat, 5)}, ${formatDecimal(v.lng, 5)}` : '')

/** Tap the map to drop a marker; the text field (coordinates or a Google Maps link) always works too. */
export function MapPicker({ value, onChange, id }: Props) {
  const [text, setText] = useState(fmt(value))
  const [invalid, setInvalid] = useState(false)
  const [showMap, setShowMap] = useState(false)

  const setValue = (v: LatLng) => { setText(fmt(v)); setInvalid(false); onChange(v) }
  const onText = (t: string) => {
    setText(t)
    if (!t.trim()) { setInvalid(false); onChange(null); return }
    const p = parseLatLng(t)
    setInvalid(!p)
    if (p) onChange(p)
  }
  const start = value ?? RIYADH
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>الإحداثيات أو رابط الخرائط</Label>
      <Input id={id} value={text} onChange={(e) => onText(e.target.value)} aria-invalid={invalid} aria-describedby={invalid ? `${id}-err` : undefined}
             placeholder="الصق إحداثيات أو رابط خرائط Google" inputMode="text" autoComplete="off" dir="auto" />
      {invalid && <p id={`${id}-err`} className="text-sm text-destructive">صيغة غير صحيحة</p>}
      <Button type="button" variant="outline" size="sm" aria-expanded={showMap} onClick={() => setShowMap(!showMap)}>
        <MapIcon aria-hidden />{showMap ? 'إخفاء الخريطة' : 'اختيار من الخريطة'}
      </Button>
      {showMap && (
        <BaseMap className="h-60 overflow-hidden rounded-2xl" initialViewState={{ latitude: start.lat, longitude: start.lng, zoom: value ? 14 : 10 }}
                 cursor="crosshair" onClick={(e) => setValue({ lat: e.lngLat.lat, lng: e.lngLat.lng })}>
          {value && <Marker latitude={value.lat} longitude={value.lng} color="#0f766e" />}
        </BaseMap>
      )}
    </div>
  )
}
