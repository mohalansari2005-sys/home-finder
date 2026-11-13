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
