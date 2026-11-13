import { CircleAlert, Play, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { useResumeAdapter, useStatus } from '../../api/hooks'
import { formatNumber, formatRelative } from '../../lib/format'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

const SOURCE_AR: Record<string, string> = { aqar: 'عقار', haraj: 'حراج' }
const COUNTS: [keyof import('../../api/types').SystemStatus['counts'], string][] = [
  ['active', 'نشطة'], ['passing', 'مطابقة للشروط'], ['new', 'جديدة'], ['bookmarked', 'محفوظة'], ['rejected', 'مستبعدة'],
]

export function StatusSection() {
  const s = useStatus()
  const resume = useResumeAdapter()
  return (
    <Card className="rounded-3xl" role="region" aria-labelledby="status-title">
      <CardHeader><CardTitle id="status-title" className="font-display text-lg font-bold">حالة النظام</CardTitle></CardHeader>
      <CardContent className="space-y-5 text-sm">
        {s.isError ? (
          <div className="flex flex-col items-start gap-3">
            <p className="text-destructive">تعذّر تحميل حالة النظام.</p>
            <Button variant="outline" onClick={() => s.refetch()}><RefreshCw aria-hidden />إعادة المحاولة</Button>
          </div>
        ) : !s.data ? (
          <div className="space-y-3" aria-busy><Skeleton className="h-6 w-full" /><Skeleton className="h-6 w-2/3" /></div>
        ) : (() => {
          const { worker, jobs, adapters, failed_jobs, counts } = s.data
          return (
            <>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">جهاز التحديث</span>
                  {worker.online ? <Badge className="bg-success text-background">متصل</Badge>
                    : <Badge variant="outline" className="border-warning/40 bg-warning-soft text-warning"><CircleAlert aria-hidden />غير متصل</Badge>}
                </div>
                <p className="text-muted-foreground">آخر ظهور: {worker.last_seen ? formatRelative(new Date(worker.last_seen)) : '—'}</p>
                <p className="flex flex-wrap gap-x-4 text-muted-foreground">
                  <span>بالانتظار: <bdi>{formatNumber(jobs.pending)}</bdi></span>
                  <span>قيد التنفيذ: <bdi>{formatNumber(jobs.claimed)}</bdi></span>
                  <span>فاشلة: <bdi>{formatNumber(jobs.failed)}</bdi></span>
                </p>
              </div>
              <ul className="space-y-3">
                {adapters.map((a) => (
                  <li key={a.source} className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">{SOURCE_AR[a.source] ?? a.source}</span>
                    {a.status === 'ok' ? (
                      <span className="inline-flex items-center gap-2 text-muted-foreground">
                        <span className="size-2 rounded-full bg-success" aria-hidden />
                        {a.last_scrape_at ? <>آخر تحديث {formatRelative(new Date(a.last_scrape_at))}</> : 'يعمل'}
                      </span>
                    ) : (
                      <span className="flex flex-wrap items-center gap-2">
                        <Badge variant="destructive">متوقف</Badge>
                        <Button size="sm" variant="outline" disabled={resume.isPending}
                                onClick={() => resume.mutate(a.source, { onSuccess: () => toast.success('تم الاستئناف') })}>
                          <Play aria-hidden />استئناف
                        </Button>
                        {a.reason && <span className="basis-full text-muted-foreground"><bdi>{a.reason}</bdi></span>}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 border-t pt-4">
                {COUNTS.map(([k, label]) => (
                  <div key={k} className="flex items-baseline justify-between gap-2"><dt className="text-muted-foreground">{label}</dt><dd className="font-semibold"><bdi>{formatNumber(counts[k])}</bdi></dd></div>
                ))}
              </dl>
              {failed_jobs.length > 0 && (
                <div className="space-y-1 border-t pt-4">
                  <h3 className="font-medium">آخر الأخطاء</h3>
                  <ul className="space-y-1 text-muted-foreground">{failed_jobs.map((j) => <li key={j.id} className="truncate"><bdi>{j.type}: {j.error}</bdi></li>)}</ul>
                </div>
              )}
            </>
          )
        })()}
      </CardContent>
    </Card>
  )
}
