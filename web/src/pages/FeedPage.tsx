import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { Columns2 } from 'lucide-react'
import { toast } from 'sonner'
import { useFeed, useMapPoints, usePlaces, useReactWithUndo } from '../api/hooks'
import type { FeedView } from '../api/types'
import { CompareBar } from '../components/CompareBar'
import { FeedList } from '../components/FeedList'
import { ListingDetailView } from '../components/ListingDetailView'
import { MapView } from '../components/MapView'
import { ShortcutsHelp } from '../components/ShortcutsHelp'
import { SuggestionBanner } from '../components/SuggestionBanner'
import { useRejectFlow } from '../components/useRejectFlow'
import { useBreakpoint } from '../lib/breakpoint'
import { maxCompare, parseIds } from '../lib/compare'
import { useShortcuts } from '../lib/useShortcuts'
import { Button } from '@/components/ui/button'
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
  const [helpOpen, setHelpOpen] = useState(false)

  // compare mode lives in the URL: ?compare= (mode on, nothing picked) or ?compare=1,2
  const compareMode = params.has('compare')
  const compareIds = parseIds(params.get('compare'))
  const limit = maxCompare(bp)

  const setParam = (k: string, v: string | null) => {
    const p = new URLSearchParams(params)
    if (v == null) p.delete(k)
    else p.set(k, v)
    setParams(p, { replace: k === 'compare' })
  }
  const toggleCompare = (id: number) => {
    if (compareIds.includes(id)) return setParam('compare', compareIds.filter((x) => x !== id).join(','))
    if (compareIds.length >= limit) return void toast(`الحد الأقصى للمقارنة ${limit}`)
    setParam('compare', [...compareIds, id].join(','))
  }
  const open = (id: number) => (bp === 'phone' ? nav(`/listing/${id}`) : setParam('id', String(id)))

  // keyboard shortcuts (desktop only): move through the loaded items, bookmark or reject the selected one
  const feed = useFeed(view)
  const items = feed.data?.pages.flatMap((p) => p.items) ?? []
  const react = useReactWithUndo()
  const rejectFlow = useRejectFlow()
  const current = items.find((i) => i.id === selected)
  const step = (d: 1 | -1) => {
    if (!items.length) return
    const at = items.findIndex((i) => i.id === selected)
    const next = at < 0 ? (d === 1 ? 0 : items.length - 1) : Math.min(items.length - 1, Math.max(0, at + d))
    setParam('id', String(items[next].id))
  }
  useShortcuts({
    enabled: bp === 'desktop',
    onNext: () => step(1), onPrev: () => step(-1), onHelp: () => setHelpOpen(true),
    onBookmark: current && current.family_status !== 'visited'
      ? () => react(current.id, current.family_status === 'bookmarked' ? 'unreject' : 'bookmark') : undefined,
    onReject: current && (() => rejectFlow.ask(current.id, current.title)),
    onWhatsApp: current?.whatsapp_url ? () => window.open(current.whatsapp_url!, '_blank', 'noreferrer') : undefined,
  })

  const tabs = (
    <div className="flex flex-wrap items-center justify-between gap-2 px-4 pt-4">
      <Tabs value={view} onValueChange={(v) => setParam('view', v)}>
        <TabsList aria-label="عرض العقارات">
          {VIEWS.map(([v, label]) => <TabsTrigger key={v} value={v}>{label}</TabsTrigger>)}
        </TabsList>
      </Tabs>
      <div className="flex items-center gap-1">
        <Button variant={compareMode ? 'default' : 'outline'} size="sm" aria-pressed={compareMode} className="h-9"
                onClick={() => setParam('compare', compareMode ? null : '')}>
          <Columns2 aria-hidden />وضع المقارنة
        </Button>
        {bp === 'desktop' && <ShortcutsHelp open={helpOpen} onOpenChange={setHelpOpen} />}
      </div>
    </div>
  )
  const list = (cols: 1 | 2) => (
    <>
      {tabs}
      <SuggestionBanner />
      <FeedList view={view} selectedId={selected} onOpen={open} columns={cols}
                compare={compareMode ? { ids: compareIds, onToggle: toggleCompare } : undefined} />
      {compareMode && (
        <CompareBar count={compareIds.length} max={limit} onClear={() => setParam('compare', '')}
                    onCompare={() => nav(`/compare?ids=${compareIds.join(',')}`)} />
      )}
      {rejectFlow.element}
    </>
  )

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
