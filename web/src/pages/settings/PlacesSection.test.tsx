import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { PlacesSection } from './PlacesSection'

it('lists the current home first, with its saved value', async () => {
  const places = [{ kind: 'home', name: 'بيتنا الحالي', lat: 24.7, lng: 46.6 }, { kind: 'work', name: 'المكتب', lat: 24.8, lng: 46.7 }]
  globalThis.fetch = (async () => new Response(JSON.stringify(places), { status: 200 })) as typeof fetch
  render(<QueryClientProvider client={new QueryClient()}><PlacesSection /></QueryClientProvider>)
  const home = await screen.findByTestId('place-home')
  expect(home).toHaveTextContent('المنزل الحالي')
  expect(screen.getAllByRole('listitem')[0]).toBe(home)
  expect(screen.getByLabelText('الاسم', { selector: '#place-name-home' })).toHaveValue('بيتنا الحالي')
})
