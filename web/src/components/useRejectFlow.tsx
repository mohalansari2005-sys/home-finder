import { useState } from 'react'
import { useReactWithUndo } from '../api/hooks'
import { RejectReasonSheet } from './RejectReasonSheet'

/**
 * Reject → reason sheet → submit → optimistic removal + undo toast (both live in useReactWithUndo).
 * Cancelling the sheet leaves the listing untouched.
 */
export function useRejectFlow() {
  const react = useReactWithUndo()
  const [target, setTarget] = useState<{ id: number; title: string | null } | null>(null)
  const element = (
    <RejectReasonSheet open={target != null} listingTitle={target?.title} onCancel={() => setTarget(null)}
                       onSubmit={(c) => { if (target) react(target.id, 'reject', c); setTarget(null) }} />
  )
  return { ask: (id: number, title: string | null) => setTarget({ id, title }), element }
}
