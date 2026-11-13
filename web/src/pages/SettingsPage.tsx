import { RefreshCw } from 'lucide-react'
import { useStatus } from '../api/hooks'
import { formatDateTime } from '../lib/format'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

export function SettingsPage() {
  const s = useStatus()
  if (s.isError) {
    return (
      <div className="flex flex-col items-center gap-3 p-8 text-center">
        <p className="text-destructive">تعذّر تحميل حالة النظام.</p>
        <Button variant="outline" onClick={() => s.refetch()}><RefreshCw aria-hidden />إعادة المحاولة</Button>
      </div>
    )
  }
  if (!s.data) {
    return <div className="max-w-2xl space-y-4 p-4" aria-busy><Skeleton className="h-8 w-40" /><Skeleton className="h-32 w-full rounded-2xl" /></div>
  }
  const { worker, jobs, adapters, failed_jobs } = s.data
  return (
    <div className="mx-auto max-w-2xl space-y-4 px-4 py-6 md:px-6">
      <h1 className="text-2xl font-semibold">حالة النظام</h1>
      <Card className="rounded-2xl">
        <CardHeader><CardTitle className="flex items-center gap-2 text-base">
          جهاز التحديث
          {worker.online ? <Badge className="bg-success text-background">متصل</Badge> : <Badge variant="destructive">غير متصل</Badge>}
        </CardTitle></CardHeader>
        <CardContent className="space-y-1 text-sm">
          <p className="text-muted-foreground">آخر ظهور: {worker.last_seen ? <bdi>{formatDateTime(new Date(worker.last_seen))}</bdi> : '—'}</p>
          <p className="flex flex-wrap gap-x-4"><span>مهام بالانتظار: <bdi>{jobs.pending}</bdi></span><span>قيد التنفيذ: <bdi>{jobs.claimed}</bdi></span><span>فاشلة: <bdi>{jobs.failed}</bdi></span></p>
        </CardContent>
      </Card>
      {adapters.map((a) => (
        <Card key={a.source} className="rounded-2xl">
          <CardContent className="flex flex-wrap items-center gap-2 pt-4 text-sm">
            <span className="font-medium">{a.source}</span>
            {a.status === 'ok'
              ? <Badge className="bg-success text-background">يعمل</Badge>
              : <><Badge variant="destructive">متوقف</Badge><span className="text-muted-foreground">{a.reason}</span></>}
          </CardContent>
        </Card>
      ))}
      {failed_jobs.length > 0 && (
        <Card className="rounded-2xl">
          <CardHeader><CardTitle className="text-base">آخر الأخطاء</CardTitle></CardHeader>
          <CardContent><ul className="space-y-1 text-sm">{failed_jobs.map((j) => <li key={j.id} className="truncate"><bdi>{j.type}: {j.error}</bdi></li>)}</ul></CardContent>
        </Card>
      )}
    </div>
  )
}
