import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, it, vi } from 'vitest'
import { LoginPage } from './LoginPage'

afterEach(() => vi.restoreAllMocks())

async function attempt(fetchImpl: () => Promise<Response>) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(fetchImpl)
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><LoginPage /></MemoryRouter></QueryClientProvider>)
  await userEvent.type(screen.getByLabelText('كلمة مرور العائلة'), 'abc')
  await userEvent.click(screen.getByRole('button', { name: 'دخول' }))
  return screen.findByRole('alert')
}

it('says the password is wrong only for a 401', async () => {
  expect(await attempt(async () => new Response('{}', { status: 401 }))).toHaveTextContent('كلمة المرور غير صحيحة')
})

it('says too many attempts for a 429', async () => {
  expect(await attempt(async () => new Response('{}', { status: 429 }))).toHaveTextContent('محاولات كثيرة')
})

it('does not blame the password when offline or the server fails (M16)', async () => {
  expect(await attempt(async () => { throw new TypeError('Failed to fetch') })).toHaveTextContent('تعذّر الاتصال بالخادم')
})

it('does not blame the password on a 500', async () => {
  expect(await attempt(async () => new Response('boom', { status: 502 }))).toHaveTextContent('تعذّر الاتصال بالخادم')
})
