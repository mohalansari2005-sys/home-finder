import { useState, type ReactNode } from 'react'
import { Check, Plus, Save, X } from 'lucide-react'
import { toast } from 'sonner'
import { errorDetail } from '../../api/client'
import { useSavePreferences } from '../../api/hooks'
import type { CommuteKind, Preferences } from '../../api/types'
import { COMMUTE_ICONS, FACING_AR, PROPERTY_TYPE_AR } from '../../lib/format'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Toggle } from '@/components/ui/toggle'

const toNum = (s: string): number | null => (s.trim() === '' ? null : Number(s))
const str = (n: unknown) => (n == null ? '' : String(n))

function NumberField({ id, label, unit, value, onChange }: { id: string; label: string; unit?: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <Input id={id} type="number" inputMode="decimal" min={0} value={value} onChange={(e) => onChange(e.target.value)} className={unit ? 'pe-12' : undefined} />
        {unit && <span className="pointer-events-none absolute inset-y-0 end-3 flex items-center text-sm text-muted-foreground">{unit}</span>}
      </div>
    </div>
  )
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="min-w-0 space-y-2">
      <legend className="mb-2 text-sm font-medium">{title}</legend>
      {children}
    </fieldset>
  )
}

export function FiltersSection({ prefs }: { prefs: Preferences }) {
  const hf = prefs.hard_filters
  const [types, setTypes] = useState<string[]>(hf.property_types ?? ['villa'])
  const [districts, setDistricts] = useState<string[]>(hf.districts ?? [])
  const [districtText, setDistrictText] = useState('')
  const [priceMax, setPriceMax] = useState(str(hf.price_max))
  const [minBed, setMinBed] = useState(str(hf.min_bedrooms))
  const [ageMax, setAgeMax] = useState(str(hf.building_age_max))
  const [streetMin, setStreetMin] = useState(str(hf.street_width_min))
  const [commute, setCommute] = useState<Record<string, string>>(
    Object.fromEntries(COMMUTE_ICONS.map(({ kind }) => [kind, str(hf.max_commute?.[kind])])))
  const [facings, setFacings] = useState<string[]>((prefs.targets.preferred_facings as string[] | undefined) ?? [])
  const [error, setError] = useState<string | null>(null)
  const save = useSavePreferences()

  const addDistrict = () => {
    const d = districtText.trim()
    if (d && !districts.includes(d)) setDistricts([...districts, d])
    setDistrictText('')
  }
  const toggle = (list: string[], set: (v: string[]) => void, v: string) => set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v])

  const submit = () => {
    if (types.length === 0) { setError('اختر نوع عقار واحدًا على الأقل'); return }
    setError(null)
    const max_commute: Partial<Record<CommuteKind, number>> = {}
    for (const { kind } of COMMUTE_ICONS) { const n = toNum(commute[kind]); if (n != null) max_commute[kind] = n }
    save.mutate({
      hard_filters: { property_types: types, districts, price_max: toNum(priceMax), min_bedrooms: toNum(minBed),
        building_age_max: toNum(ageMax), street_width_min: toNum(streetMin), max_commute },
      targets: { preferred_facings: facings },
    }, { onSuccess: () => toast.success('تم الحفظ'), onError: (e) => setError(errorDetail(e)) })
  }

  return (
    <Card className="rounded-3xl" role="region" aria-labelledby="filters-title">
      <CardHeader><CardTitle id="filters-title" className="font-display text-lg font-bold">الفلاتر الأساسية</CardTitle></CardHeader>
      <CardContent className="space-y-6">
        <Group title="نوع العقار">
          <div className="flex flex-wrap gap-2">
            {Object.entries(PROPERTY_TYPE_AR).map(([k, label]) => (
              <Toggle key={k} variant="outline" pressed={types.includes(k)} onPressedChange={() => toggle(types, setTypes, k)}
                      className="h-11 rounded-full px-4 text-base data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-primary-foreground">
                {types.includes(k) && <Check aria-hidden strokeWidth={1.75} />}{label}
              </Toggle>
            ))}
          </div>
        </Group>

        <Group title="الأحياء">
          {districts.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {districts.map((d) => (
                <li key={d} className="inline-flex h-10 items-center gap-1 rounded-lg bg-muted ps-3 text-sm">
                  {d}
                  <button type="button" aria-label={`إزالة ${d}`} onClick={() => setDistricts(districts.filter((x) => x !== d))}
                          className="flex size-10 items-center justify-center rounded-lg text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
                    <X className="size-4" strokeWidth={1.75} aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-2">
            <div className="min-w-0 flex-1 space-y-2">
              <Label htmlFor="district-input">حي</Label>
              <Input id="district-input" value={districtText} autoComplete="off" onChange={(e) => setDistrictText(e.target.value)}
                     onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addDistrict() } }} />
            </div>
            <Button type="button" variant="secondary" onClick={addDistrict} className="self-end"><Plus aria-hidden />إضافة</Button>
          </div>
          <p className="text-sm text-muted-foreground">اتركها فارغة للبحث في كل أحياء المدينة.</p>
        </Group>

        <div className="grid gap-4 sm:grid-cols-2">
          <NumberField id="f-price" label="أعلى سعر" unit="ر.س" value={priceMax} onChange={setPriceMax} />
          <NumberField id="f-bed" label="أقل عدد غرف" value={minBed} onChange={setMinBed} />
          <NumberField id="f-age" label="أكبر عمر للمبنى" unit="سنة" value={ageMax} onChange={setAgeMax} />
          <NumberField id="f-street" label="أقل عرض للشارع" unit="م" value={streetMin} onChange={setStreetMin} />
        </div>

        <Group title="أقصى مدة وصول بالدقائق (اتركها فارغة بلا حد)">
          <div className="grid gap-4 sm:grid-cols-2">
            {COMMUTE_ICONS.map(({ kind, label }) => (
              <NumberField key={kind} id={`f-commute-${kind}`} label={label} unit="د" value={commute[kind]}
                           onChange={(v) => setCommute({ ...commute, [kind]: v })} />
            ))}
          </div>
        </Group>

        <Group title="الواجهات المفضلة">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
            {Object.entries(FACING_AR).map(([k, label]) => (
              <Label key={k} htmlFor={`facing-${k}`} className="min-h-11 cursor-pointer gap-3 font-normal">
                <Checkbox id={`facing-${k}`} checked={facings.includes(k)} onCheckedChange={() => toggle(facings, setFacings, k)} />
                {label}
              </Label>
            ))}
          </div>
        </Group>

        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <Button disabled={save.isPending} onClick={submit}><Save aria-hidden />حفظ الفلاتر</Button>
      </CardContent>
    </Card>
  )
}
