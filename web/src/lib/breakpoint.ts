import { useEffect, useState } from 'react'

export type Breakpoint = 'phone' | 'tablet' | 'desktop'
export const getBreakpoint = (w: number): Breakpoint => (w >= 1200 ? 'desktop' : w >= 768 ? 'tablet' : 'phone')

export function useBreakpoint(): Breakpoint {
  const [bp, setBp] = useState(() => getBreakpoint(window.innerWidth))
  useEffect(() => {
    const on = () => setBp(getBreakpoint(window.innerWidth))
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [])
  return bp
}

/** How the assistant is presented: own page (phone), floating button + slide-over, or docked column (>= 1280px). */
export type ChatLayout = 'page' | 'overlay' | 'docked'
export const getChatLayout = (w: number): ChatLayout => (w >= 1280 ? 'docked' : w >= 768 ? 'overlay' : 'page')
export function useChatLayout(): ChatLayout {
  const [l, setL] = useState(() => getChatLayout(window.innerWidth))
  useEffect(() => {
    const on = () => setL(getChatLayout(window.innerWidth))
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [])
  return l
}
