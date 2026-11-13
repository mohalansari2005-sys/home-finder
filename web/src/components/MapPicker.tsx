import { useState } from 'react'
import { AdvancedMarker, APIProvider, Map } from '@vis.gl/react-google-maps'
import { Map as MapIcon } from 'lucide-react'
import { parseLatLng } from '../lib/factors'
import { formatDecimal } from '../lib/format'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const KEY = import.meta.env.VITE_GOOGLE_MAPS_KEY as string | undefined
const MAP_ID = (import.meta.env.VITE_GOOGLE_MAP_ID as string | undefined) || 'DEMO_MAP_ID'
const RIYADH = { lat: 24.7136, lng: 46.6753 }

export interface LatLng { lat: number; lng: number }
interface Props { value: LatLng | null; onChange: (v: LatLng | null) => void; id: string }

const fmt = (v: LatLng | null) => (v ? `${formatDecimal(v.lat, 5)}, ${formatDecimal(v.lng, 5)}` : '')

/** Tap the map to drop a marker; the text field (coordinates or a Google Maps link) always works, with or without a Maps key. */
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
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>الإحداثيات أو رابط الخرائط</Label>
      <Input id={id} value={text} onChange={(e) => onText(e.target.value)} aria-invalid={invalid} aria-describedby={invalid ? `${id}-err` : undefined}
             placeholder="الصق إحداثيات أو رابط خرائط Google" inputMode="text" autoComplete="off" dir="auto" />
      {invalid && <p id={`${id}-err`} className="text-sm text-destructive">صيغة غير صحيحة</p>}
      {KEY && (
        <>
          <Button type="button" variant="outline" size="sm" aria-expanded={showMap} onClick={() => setShowMap(!showMap)}>
            <MapIcon aria-hidden />{showMap ? 'إخفاء الخريطة' : 'اختيار من الخريطة'}
          </Button>
          {showMap && (
            <div className="h-60 overflow-hidden rounded-2xl">
              <APIProvider apiKey={KEY} language="ar" region="SA">
                <Map defaultCenter={value ?? RIYADH} defaultZoom={value ? 14 : 10} mapId={MAP_ID} gestureHandling="greedy"
                     onClick={(ev) => { const ll = ev.detail.latLng; if (ll) setValue({ lat: ll.lat, lng: ll.lng }) }} className="size-full">
                  {value && <AdvancedMarker position={value} />}
                </Map>
              </APIProvider>
            </div>
          )}
        </>
      )}
    </div>
  )
}
