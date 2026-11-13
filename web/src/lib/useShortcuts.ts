import { useEffect, useRef } from 'react'

export interface ShortcutHandlers {
  enabled?: boolean
  onBookmark?: () => void
  onReject?: () => void
  onNext?: () => void
  onPrev?: () => void
  onHelp?: () => void
}

function isTyping(t: EventTarget | null): boolean {
  if (!(t instanceof HTMLElement)) return false
  return t.isContentEditable || t.closest('input, textarea, select, [contenteditable=""], [contenteditable="true"]') != null
}

/**
 * Desktop keyboard shortcuts. Never fires while typing, with a modifier held, or while a dialog is open.
 * Arrow keys follow RTL reading order: ArrowLeft is next, ArrowRight is previous.
 */
export function useShortcuts(h: ShortcutHandlers) {
  const ref = useRef(h)
  useEffect(() => { ref.current = h })
  const enabled = h.enabled ?? true
  useEffect(() => {
    if (!enabled) return
    const on = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.repeat || e.ctrlKey || e.metaKey || e.altKey) return
      if (isTyping(e.target) || document.querySelector('[role="dialog"]:not([data-state="closed"]), [role="alertdialog"]:not([data-state="closed"])')) return
      const c = ref.current
      const act = (fn?: () => void) => { if (fn) { e.preventDefault(); fn() } }
      // physical key codes too, so the shortcuts also work on an Arabic keyboard layout
      switch (e.code === 'KeyB' ? 'b' : e.code === 'KeyX' ? 'x' : e.key) {
        case 'b': case 'B': return act(c.onBookmark)
        case 'x': case 'X': return act(c.onReject)
        case 'ArrowLeft': return act(c.onNext)
        case 'ArrowRight': return act(c.onPrev)
        case '?': return act(c.onHelp)
      }
    }
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [enabled])
}
