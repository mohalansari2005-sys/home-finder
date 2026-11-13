import { useState } from 'react'
import { Save } from 'lucide-react'
import { toast } from 'sonner'
import { errorDetail } from '../../api/client'
import { usePlaces, useSavePlaces } from '../../api/hooks'
import type { CommuteKind, Place } from '../../api/types'
import { MapPicker, type LatLng } from '../../components/MapPicker'
import { COMMUTE_ICONS } from '../../lib/format'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'

type Draft = Record<CommuteKind, { name: string; at: LatLng | null }>

function toDraft(places: Place[]): Draft {
  const d = Object.fromEntries(COMMUTE_ICONS.map((c) => [c.kind, { name: '', at: null }])) as Draft
  for (const p of places) d[p.kind] = { name: p.name, at: { lat: p.lat, lng: p.lng } }
  return d
}

function PlacesForm({ places }: { places: Place[] }) {
  const [draft, setDraft] = useState<Draft>(() => toDraft(places))
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const save = useSavePlaces()

  const submit = () => {
    const body = COMMUTE_ICONS.flatMap(({ kind }) => {
      const d = draft[kind]
      return d.name.trim() && d.at ? [{ kind, name: d.name.trim(), lat: d.at.lat, lng: d.at.lng }] : []
    })
    setError(null)
    save.mutate(body, {
      onSuccess: () => { setSaved(true); toast.success('تم الحفظ') },
      onError: (e) => setError(errorDetail(e)),
    })
  }
  return (
    <CardContent className="space-y-6">
      <ul className="space-y-6">
        {COMMUTE_ICONS.map(({ kind, Icon, label }) => (
          <li key={kind} data-testid={`place-${kind}`} className="space-y-3 border-t pt-4 first:border-t-0 first:pt-0">
            <div className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl bg-muted"><Icon className="size-5" strokeWidth={1.75} aria-hidden /></span>
              <h3 className="font-semibold">{label}</h3>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor={`place-name-${kind}`}>الاسم</Label>
                <Input id={`place-name-${kind}`} value={draft[kind].name} autoComplete="off"
                       onChange={(e) => { setSaved(false); setDraft({ ...draft, [kind]: { ...draft[kind], name: e.target.value } }) }} />
              </div>
              <MapPicker id={`place-at-${kind}`} value={draft[kind].at}
                         onChange={(at) => { setSaved(false); setDraft((d) => ({ ...d, [kind]: { ...d[kind], at } })) }} />
            </div>
          </li>
        ))}
      </ul>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {saved && <p role="status" className="text-sm text-muted-foreground">سيُعاد حساب المسافات عند اتصال جهاز التحديث</p>}
      <Button disabled={save.isPending} onClick={submit}><Save aria-hidden />حفظ الأماكن</Button>
    </CardContent>
  )
}

export function PlacesSection() {
  const q = usePlaces()
  return (
    <Card className="rounded-3xl" role="region" aria-labelledby="places-title">
      <CardHeader>
        <CardTitle id="places-title" className="font-display text-lg font-bold">الأماكن</CardTitle>
        <CardDescription>تُحسب منها مدة الوصول لكل عقار.</CardDescription>
      </CardHeader>
      {q.isError ? (
        <CardContent className="flex flex-col items-start gap-3">
          <p className="text-destructive">تعذّر تحميل الأماكن.</p>
          <Button variant="outline" onClick={() => q.refetch()}>إعادة المحاولة</Button>
        </CardContent>
      ) : !q.data ? (
        <CardContent className="space-y-3" aria-busy><Skeleton className="h-16 w-full rounded-xl" /><Skeleton className="h-16 w-full rounded-xl" /></CardContent>
      ) : <PlacesForm places={q.data} />}
    </Card>
  )
}
