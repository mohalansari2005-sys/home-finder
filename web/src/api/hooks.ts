import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { FeedPage, FeedView, ListingDetail, MapPoint, Place, ReactKind, SystemStatus } from './types'

export const useMe = () => useQuery({ queryKey: ['me'], queryFn: () => api<{ ok: boolean }>('/api/me'), retry: false })

export const useFeed = (view: FeedView, district?: string) =>
  useInfiniteQuery({
    queryKey: ['feed', view, district ?? ''],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => {
      const p = new URLSearchParams({ view, offset: String(pageParam), limit: '30' })
      if (district) p.set('district', district)
      return api<FeedPage>(`/api/feed?${p}`)
    },
    getNextPageParam: (last) => last.next_offset ?? undefined,
  })

export const useListing = (id: number | null) =>
  useQuery({ queryKey: ['listing', id], queryFn: () => api<ListingDetail>(`/api/listings/${id}`), enabled: id != null })

export const useMapPoints = () => useQuery({ queryKey: ['map'], queryFn: () => api<MapPoint[]>('/api/map') })
export const usePlaces = () => useQuery({ queryKey: ['places'], queryFn: () => api<Place[]>('/api/places') })
export const useStatus = () =>
  useQuery({ queryKey: ['status'], queryFn: () => api<SystemStatus>('/api/status'), refetchInterval: 30_000 })

export function useReact() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { id: number; kind: ReactKind; reason_code?: string; note?: string }) =>
      api<{ family_status: string }>(`/api/listings/${v.id}/react`, {
        method: 'POST', body: JSON.stringify({ kind: v.kind, reason_code: v.reason_code, note: v.note }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['feed'] })
      qc.invalidateQueries({ queryKey: ['map'] })
      qc.invalidateQueries({ queryKey: ['listing'] })
    },
  })
}
