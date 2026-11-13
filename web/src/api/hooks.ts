import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ApiError, api } from './client'
import type { FeedPage, FeedView, ListingDetail, MapPoint, Place, PreferenceChange, PreferencePatch, Preferences, ReactExtra, ReactKind, StopPatch, Suggestion, SystemStatus, Trip, TripCreate, TripStatus, VisitGroups } from './types'

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
    mutationFn: (v: { id: number; kind: ReactKind } & ReactExtra) =>
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
  return (id: number, kind: ReactKind, extra: ReactExtra = {}) => {
    react.mutate({ id, kind, ...extra })
    if (kind === 'reject') {
      toast('تم الاستبعاد', { duration: 5000, action: { label: 'تراجع', onClick: () => react.mutate({ id, kind: 'unreject' }) } })
    }
  }
}

export const useSuggestions = () => useQuery({ queryKey: ['suggestions'], queryFn: () => api<Suggestion[]>('/api/suggestions') })

function useSuggestionAction(action: 'apply' | 'dismiss') {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (code: string) => api<unknown>(`/api/suggestions/${encodeURIComponent(code)}/${action}`, { method: 'POST' }),
    onSuccess: () => {
      if (action === 'apply') toast('تم تطبيق الاقتراح')
      for (const k of ['suggestions', 'preferences', 'preference-changes', 'feed']) qc.invalidateQueries({ queryKey: [k] })
      // apply rescores in the background; refetch shortly so the feed order catches up
      if (action === 'apply') setTimeout(() => qc.invalidateQueries({ queryKey: ['feed'] }), 2000)
    },
    onError: () => toast.error('تعذّر تنفيذ الإجراء. حاولوا مرة أخرى.'),
  })
}
export const useApplySuggestion = () => useSuggestionAction('apply')
export const useDismissSuggestion = () => useSuggestionAction('dismiss')

/** 2-4 listings side by side; the key carries the ids so a changed selection refetches. */
export const useCompare = (ids: number[]) =>
  useQuery({
    queryKey: ['compare', ids],
    queryFn: () => api<ListingDetail[]>(`/api/compare?ids=${ids.join(',')}`),
    enabled: ids.length >= 2,
  })

// ---- visits (M5) ----
export const useVisitGroups = () => useQuery({ queryKey: ['visit-groups'], queryFn: () => api<VisitGroups>('/api/visits/groups') })
export const useTrips = () => useQuery({ queryKey: ['trips'], queryFn: () => api<Trip[]>('/api/visits/trips?status=all') })

/** The server runs the listing re-check in the background; poll every 30 s while it reports precheck_pending. */
export const PRECHECK_POLL_MS = 30_000
export const useTrip = (id: number | null) =>
  useQuery({
    queryKey: ['trip', id],
    queryFn: () => api<Trip>(`/api/visits/trips/${id}`),
    enabled: id != null,
    refetchInterval: (q) => (q.state.data?.warnings.includes('precheck_pending') ? PRECHECK_POLL_MS : false),
  })

function useTripWrite<V>(id: number, fn: (v: V) => Promise<Trip | void>, invalidateOnly = false) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (out) => {
      if (out && !invalidateOnly) qc.setQueryData(['trip', id], out)
      else qc.invalidateQueries({ queryKey: ['trip', id] })
      qc.invalidateQueries({ queryKey: ['trips'] })
    },
  })
}

export function useCreateTrip() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (b: TripCreate) => api<Trip>('/api/visits/trips', { method: 'POST', body: JSON.stringify(b) }),
    onSuccess: (t) => {
      qc.setQueryData(['trip', t.id], t)
      qc.invalidateQueries({ queryKey: ['trips'] })
    },
  })
}
export const usePatchStop = (tripId: number) =>
  useTripWrite(tripId, (v: { stopId: number; patch: StopPatch }) =>
    api<Trip>(`/api/visits/stops/${v.stopId}`, { method: 'PATCH', body: JSON.stringify(v.patch) }))
export const useReplanTrip = (tripId: number) =>
  useTripWrite(tripId, () => api<Trip>(`/api/visits/trips/${tripId}/replan`, { method: 'POST' }))
export const usePatchTripStatus = (tripId: number) =>
  useTripWrite(tripId, (status: TripStatus) => api<Trip>(`/api/visits/trips/${tripId}`, { method: 'PATCH', body: JSON.stringify({ status }) }))
export const usePrecheckTrip = (tripId: number) =>
  useTripWrite(tripId, () => api<void>(`/api/visits/trips/${tripId}/precheck`, { method: 'POST' }), true)

/** multipart upload: the browser sets the content-type boundary, so this bypasses the JSON `api()` helper. */
export const useUploadStopPhoto = (tripId: number) =>
  useTripWrite(tripId, async (v: { stopId: number; file: File }) => {
    const body = new FormData()
    body.append('file', v.file)
    const r = await fetch(`/api/visits/stops/${v.stopId}/photos`, { method: 'POST', body, credentials: 'include' })
    if (!r.ok) throw new ApiError(r.status, await r.text())
  }, true)
