import { RefreshCw, SearchX } from 'lucide-react'
import { Link } from 'react-router'
import { useFeed, useReactWithUndo } from '../api/hooks'
import type { FeedView } from '../api/types'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ListingCard } from './ListingCard'

interface Props { view: FeedView; district?: string; selectedId: number | null; onOpen: (id: number) => void; columns: 1 | 2 }

function CardSkeleton() {
  return (
    <div className="space-y-3 p-2">
      <Skeleton className="aspect-[4/3] w-full rounded-2xl" />
      <Skeleton className="h-6 w-1/2" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-11 w-full" />
    </div>
  )
}

export function FeedList({ view, district, selectedId, onOpen, columns }: Props) {
  const feed = useFeed(view, district)
  const react = useReactWithUndo()
  const grid = columns === 2 ? 'grid-cols-2' : 'grid-cols-1'
  if (feed.isLoading) return <div className={`grid gap-2 p-2 ${grid}`} aria-busy>{[0, 1, 2].map((i) => <CardSkeleton key={i} />)}</div>
  if (feed.isError) {
    return (
      <div className="flex flex-col items-center gap-3 p-8 text-center">
        <p className="text-destructive">تعذّر تحميل العقارات. تحقق من الاتصال ثم أعد المحاولة.</p>
        <Button variant="outline" onClick={() => feed.refetch()}><RefreshCw aria-hidden />إعادة المحاولة</Button>
      </div>
    )
  }
  const items = feed.data?.pages.flatMap((p) => p.items) ?? []
  if (!items.length) {
    return (
      <div className="flex flex-col items-center gap-3 p-10 text-center text-muted-foreground">
        <SearchX className="size-6" strokeWidth={1.75} aria-hidden />
        <p>لا توجد عقارات تطابق تفضيلاتكم بعد</p>
        <Button asChild variant="secondary"><Link to="/settings">تعديل التفضيلات</Link></Button>
      </div>
    )
  }
  return (
    <div className="space-y-4 p-2">
      <div className={`grid gap-2 ${grid}`}>
        {items.map((l) => (
          <ListingCard key={l.id} listing={l} selected={l.id === selectedId} onOpen={onOpen} onReact={(kind) => react(l.id, kind)} />
        ))}
      </div>
      {feed.hasNextPage && (
        <Button variant="outline" className="w-full" disabled={feed.isFetchingNextPage} onClick={() => feed.fetchNextPage()}>المزيد</Button>
      )}
    </div>
  )
}
