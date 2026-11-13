import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useMapPoints, usePlaces } from '../api/hooks'
import type { FeedView } from '../api/types'
import { FeedList } from '../components/FeedList'
import { ListingDetailView } from '../components/ListingDetailView'
import { MapView } from '../components/MapView'
import { useBreakpoint } from '../lib/breakpoint'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

const VIEWS: [FeedView, string][] = [['all', 'الكل'], ['new', 'جديد'], ['bookmarked', 'المحفوظة']]

function useLandscape() {
  const [l, setL] = useState(() => window.innerWidth >= 1024)
  useEffect(() => {
    const on = () => setL(window.innerWidth >= 1024)
    addEventListener('resize', on)
    return () => removeEventListener('resize', on)
  }, [])
  return l
}

export function FeedPage() {
  const bp = useBreakpoint()
  const landscape = useLandscape()
  const nav = useNavigate()
  const [params, setParams] = useSearchParams()
  const view = (params.get('view') as FeedView) || 'all'
  const selected = params.get('id') ? Number(params.get('id')) : null
  const points = useMapPoints()
  const places = usePlaces()

  const setParam = (k: string, v: string | null) => {
    const p = new URLSearchParams(params)
    if (v == null) p.delete(k)
    else p.set(k, v)
    setParams(p)
  }
  const open = (id: number) => (bp === 'phone' ? nav(`/listing/${id}`) : setParam('id', String(id)))

  const tabs = (
    <div className="px-4 pt-4">
      <Tabs value={view} onValueChange={(v) => setParam('view', v)}>
        <TabsList aria-label="عرض العقارات">
          {VIEWS.map(([v, label]) => <TabsTrigger key={v} value={v}>{label}</TabsTrigger>)}
        </TabsList>
      </Tabs>
    </div>
  )
  const list = (cols: 1 | 2) => <>{tabs}<FeedList view={view} selectedId={selected} onOpen={open} columns={cols} /></>

  if (bp === 'phone') return list(1)
  if (bp === 'tablet' && !landscape) {
    return (
      <div className="h-full">
        {list(2)}
        <Sheet open={selected != null} onOpenChange={(o) => !o && setParam('id', null)}>
          <SheetContent side="left" showCloseButton={false} className="w-[min(560px,92vw)] overflow-y-auto rounded-s-3xl sm:max-w-none">
            <SheetTitle className="sr-only">تفاصيل العقار</SheetTitle>
            <SheetDescription className="sr-only">معلومات العقار المحدد</SheetDescription>
            {selected != null && <ListingDetailView id={selected} onClose={() => setParam('id', null)} />}
          </SheetContent>
        </Sheet>
      </div>
    )
  }
  return (
    <div className="flex h-full">
      <div className={`h-full overflow-y-auto ${bp === 'desktop' ? 'w-[440px]' : 'w-1/2'} shrink-0 border-e`}>{list(1)}</div>
      <div className="h-full min-w-0 flex-1 overflow-y-auto">
        {selected != null
          ? <div className="mx-auto max-w-3xl"><ListingDetailView id={selected} onClose={() => setParam('id', null)} /></div>
          : bp === 'desktop'
            ? <MapView points={points.data ?? []} places={places.data ?? []} selectedId={selected} onSelect={open} />
            : <p className="p-6 text-muted-foreground">اختر عقاراً لعرض التفاصيل</p>}
      </div>
    </div>
  )
}
