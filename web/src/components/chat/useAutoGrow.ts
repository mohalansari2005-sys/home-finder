import { useLayoutEffect, type RefObject } from 'react'

const MAX_LINES = 5

/**
 * Fallback for browsers without `field-sizing: content` (Safari / older iOS): grow the textarea with its
 * content up to about 5 lines, then scroll. A no-op where CSS handles it.
 */
export function useAutoGrow(ref: RefObject<HTMLTextAreaElement | null>, value: string) {
  useLayoutEffect(() => {
    const el = ref.current
    if (!el || (typeof CSS !== 'undefined' && typeof CSS.supports === 'function' && CSS.supports('field-sizing', 'content'))) return
    const cs = getComputedStyle(el)
    const line = parseFloat(cs.lineHeight) || 24
    const pad = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0)
    const max = line * MAX_LINES + pad
    el.style.height = 'auto'
    const next = Math.min(el.scrollHeight, max)
    el.style.height = `${next}px`
    el.style.overflowY = el.scrollHeight > max ? 'auto' : 'hidden'
  }, [ref, value])
}
