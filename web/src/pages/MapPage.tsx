import { useState } from 'react'
import { useNavigate } from 'react-router'
import { X } from 'lucide-react'
import { useMapPoints, usePlaces } from '../api/hooks'
import { MapView } from '../components/MapView'
import { useBreakpoint } from '../lib/breakpoint'
import { formatPrice } from '../lib/format'
import { Button } from '@/components/ui/button'
import { Drawer, DrawerContent, DrawerDescription, DrawerTitle } from '@/components/ui/drawer'
import type { MapPoint } from '../api/types'

function PointSummary({ p, onOpen }: { p: MapPoint; onOpen: () => void }) {
  return (
    <div className="flex gap-3">
      {p.photo_url && <img src={p.photo_url} alt="" width={96} height={80} className="h-20 w-24 rounded-2xl object-cover" />}
      <div className="min-w-0 flex-1 space-y-1">
        <div className="font-display text-lg font-bold"><bdi>{formatPrice(p.price)}</bdi></div>
        <div className="truncate text-sm text-muted-foreground">{p.title} {p.district}</div>
        <Button size="sm" variant="secondary" onClick={onOpen}>التفاصيل</Button>
      </div>
    </div>
  )
}

export function MapPage() {
  const points = useMapPoints()
  const places = usePlaces()
  const bp = useBreakpoint()
  const [sel, setSel] = useState<number | null>(null)
  const nav = useNavigate()
  const p = points.data?.find((x) => x.id === sel)
  return (
    <div className="relative h-dvh">
      <MapView points={points.data ?? []} places={places.data ?? []} selectedId={sel} onSelect={setSel} />
      {bp === 'phone' ? (
        <Drawer open={!!p} onOpenChange={(o) => !o && setSel(null)} modal={false}>
          <DrawerContent data-testid="map-sheet" className="rounded-t-3xl p-4 pb-20">
            <DrawerTitle className="sr-only">العقار المحدد</DrawerTitle>
            <DrawerDescription className="sr-only">ملخص العقار المحدد على الخريطة</DrawerDescription>
            {p && <PointSummary p={p} onOpen={() => nav(`/listing/${p.id}`)} />}
          </DrawerContent>
        </Drawer>
      ) : (
        p && (
          <div data-testid="map-sheet" className="absolute bottom-4 end-4 z-10 w-96 max-w-[calc(100%-2rem)] rounded-3xl border bg-card p-4 shadow-xl">
            <Button variant="ghost" size="icon" aria-label="إغلاق" onClick={() => setSel(null)} className="absolute end-1 top-1"><X aria-hidden strokeWidth={1.75} /></Button>
            <PointSummary p={p} onOpen={() => nav(`/listing/${p.id}`)} />
          </div>
        )
      )}
    </div>
  )
}
