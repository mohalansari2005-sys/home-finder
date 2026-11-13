import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Direction } from 'radix-ui'
import App from './App'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import './styles.css'

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: true } } })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Direction.DirectionProvider dir="rtl">
      <TooltipProvider>
        <QueryClientProvider client={qc}>
          <BrowserRouter><App /></BrowserRouter>
        </QueryClientProvider>
        <Toaster />
      </TooltipProvider>
    </Direction.DirectionProvider>
  </StrictMode>,
)
