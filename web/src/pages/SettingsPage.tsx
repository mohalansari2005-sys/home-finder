import { RefreshCw } from 'lucide-react'
import { errorDetail } from '../api/client'
import { usePreferences, useSavePreferences } from '../api/hooks'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { toast } from 'sonner'
import { useState } from 'react'
import { FiltersSection } from './settings/FiltersSection'
import { HistorySection } from './settings/HistorySection'
import { PlacesSection } from './settings/PlacesSection'
import { StatusSection } from './settings/StatusSection'
import { WeightsSection } from './settings/WeightsSection'

function PrefsSections() {
  const q = usePreferences()
  const save = useSavePreferences()
  const [error, setError] = useState<string | null>(null)
  if (q.isError) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-3xl bg-card p-6 ring-1 ring-foreground/10">
        <p className="text-destructive">تعذّر تحميل التفضيلات. تحقق من الاتصال ثم أعد المحاولة.</p>
        <Button variant="outline" onClick={() => q.refetch()}><RefreshCw aria-hidden />إعادة المحاولة</Button>
      </div>
    )
  }
  if (!q.data) {
    return <><Skeleton className="h-72 rounded-3xl" /><Skeleton className="h-72 rounded-3xl" /></>
  }
  return (
    <>
      <FiltersSection prefs={q.data} />
      <WeightsSection prefs={q.data} pending={save.isPending} error={error}
                      onSave={(patch) => { setError(null); save.mutate(patch, { onSuccess: () => toast.success('تم الحفظ'), onError: (e) => setError(errorDetail(e)) }) }} />
    </>
  )
}

export function SettingsPage() {
  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 md:px-6 xl:px-8">
      <h1 className="font-display text-2xl font-bold text-balance">التفضيلات</h1>
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_22.5rem]">
        <div className="grid min-w-0 items-start gap-6">
          <PlacesSection />
          <PrefsSections />
        </div>
        <div className="grid min-w-0 items-start gap-6 md:max-xl:grid-cols-2">
          <HistorySection />
          <StatusSection />
        </div>
      </div>
    </div>
  )
}
