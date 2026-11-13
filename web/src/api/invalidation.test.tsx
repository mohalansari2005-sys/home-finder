import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { act, type ReactNode } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { usePatchStop, useReact, useSavePreferences } from './hooks'

afterEach(() => vi.restoreAllMocks())

function setup() {
  const qc = new QueryClient()
  const spy = vi.spyOn(qc, 'invalidateQueries')
  vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify({ id: 1, stops: [], family_status: 'seen' }), { status: 200 }))
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  const keys = () => spy.mock.calls.map((c) => (c[0] as { queryKey: string[] }).queryKey[0])
  return { wrapper, keys }
}

it('a reject refreshes the suggestions banner (M14)', async () => {
  const { wrapper, keys } = setup()
  const { result } = renderHook(() => useReact(), { wrapper })
  await act(async () => { result.current.mutate({ id: 1, kind: 'reject' }) })
  await waitFor(() => expect(keys()).toContain('suggestions'))
})

it('changing a trip stop refreshes the feed, listing and visit groups (M14)', async () => {
  const { wrapper, keys } = setup()
  const { result } = renderHook(() => usePatchStop(1), { wrapper })
  await act(async () => { result.current.mutate({ stopId: 3, patch: { contact_status: 'visited' } }) })
  await waitFor(() => expect(keys()).toEqual(expect.arrayContaining(['feed', 'listing', 'visit-groups', 'trips'])))
})

it('saving preferences refreshes the map too (M14)', async () => {
  const { wrapper, keys } = setup()
  const { result } = renderHook(() => useSavePreferences(), { wrapper })
  await act(async () => { result.current.mutate({}) })
  await waitFor(() => expect(keys()).toContain('map'))
})
