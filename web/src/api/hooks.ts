import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api } from './client'
import type { FeedPage, FeedView, ListingDetail, MapPoint, Place, PreferenceChange, PreferencePatch, Preferences, ReactKind, SystemStatus } from './types'

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

export const usePreferences = () => useQuery({ queryKey: ['preferences'], queryFn: () => api<Preferences>('/api/preferences') })
export const usePreferenceChanges = () =>
  useQuery({ queryKey: ['preference-changes'], queryFn: () => api<PreferenceChange[]>('/api/preferences/changes?limit=20') })

export function useSavePreferences() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (patch: PreferencePatch) => api<Preferences>('/api/preferences', { method: 'PUT', body: JSON.stringify(patch) }),
    onSuccess: (out) => {
      qc.setQueryData(['preferences'], out)
      qc.invalidateQueries({ queryKey: ['preference-changes'] })
      qc.invalidateQueries({ queryKey: ['feed'] })
      qc.invalidateQueries({ queryKey: ['status'] })
      // the server rescores in the background; refetch shortly so the feed order catches up
      setTimeout(() => qc.invalidateQueries({ queryKey: ['feed'] }), 2000)
    },
  })
}

export function useSavePlaces() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (places: Place[]) => api<Place[]>('/api/places', { method: 'PUT', body: JSON.stringify(places) }),
    onSuccess: (out) => {
      qc.setQueryData(['places'], out)
      qc.invalidateQueries({ queryKey: ['map'] })
    },
  })
}

export function useResumeAdapter() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (source: string) => api<void>(`/api/adapters/${source}/resume`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['status'] }),
  })
}

export function useReact() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { id: number; kind: ReactKind; reason_code?: string; note?: string }) =>
      api<{ family_status: string }>(`/api/listings/${v.id}/react`, {
        method: 'POST', body: JSON.stringify({ kind: v.kind, reason_code: v.reason_code, note: v.note }),
      }),
    onMutate: async (v) => {
      if (v.kind !== 'reject') return
      await qc.cancelQueries({ queryKey: ['feed'] })
      // optimistic removal from every cached feed page
      qc.setQueriesData<{ pages: FeedPage[]; pageParams: unknown[] }>({ queryKey: ['feed'] }, (old) =>
        old && { ...old, pages: old.pages.map((p) => ({ ...p, items: p.items.filter((i) => i.id !== v.id) })) })
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['feed'] })
      qc.invalidateQueries({ queryKey: ['map'] })
      qc.invalidateQueries({ queryKey: ['listing'] })
    },
  })
}

/** React to a listing; rejecting shows a toast with undo (better than a confirm dialog). */
export function useReactWithUndo() {
  const react = useReact()
  return (id: number, kind: ReactKind) => {
    react.mutate({ id, kind })
    if (kind === 'reject') {
      toast('تم الاستبعاد', { duration: 5000, action: { label: 'تراجع', onClick: () => react.mutate({ id, kind: 'unreject' }) } })
    }
  }
}
