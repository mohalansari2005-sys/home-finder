import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { act, type ReactNode } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { PRECHECK_POLL_MS, useTrip } from './hooks'

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks() })

const wrap = ({ children }: { children: ReactNode }) => <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
const respond = (warnings: string[]) => vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify({ id: 1, warnings, stops: [] }), { status: 200 }))

it('polls the trip every 30 s only while precheck_pending is in warnings', async () => {
  const f = respond(['precheck_pending'])
  vi.useFakeTimers({ shouldAdvanceTime: true })
  renderHook(() => useTrip(1), { wrapper: wrap })
  await waitFor(() => expect(f).toHaveBeenCalledTimes(1))
  await act(async () => { await vi.advanceTimersByTimeAsync(PRECHECK_POLL_MS + 100) })
  expect(f.mock.calls.length).toBeGreaterThanOrEqual(2)
  f.mockClear()
  respond([]) // check finished: the next poll sees no pending warning, so polling stops
  await act(async () => { await vi.advanceTimersByTimeAsync(PRECHECK_POLL_MS + 100) })
  const afterFinish = vi.mocked(globalThis.fetch).mock.calls.length
  await act(async () => { await vi.advanceTimersByTimeAsync(PRECHECK_POLL_MS * 3) })
  expect(vi.mocked(globalThis.fetch).mock.calls.length).toBe(afterFinish)
})

it('does not poll without precheck_pending', async () => {
  const f = respond([])
  vi.useFakeTimers({ shouldAdvanceTime: true })
  renderHook(() => useTrip(1), { wrapper: wrap })
  await waitFor(() => expect(f).toHaveBeenCalledTimes(1))
  await act(async () => { await vi.advanceTimersByTimeAsync(PRECHECK_POLL_MS * 3) })
  expect(f).toHaveBeenCalledTimes(1)
})
