import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { useShortcuts } from './useShortcuts'

function Harness({ enabled = true, h }: { enabled?: boolean; h: Record<string, () => void> }) {
  useShortcuts({ enabled, onBookmark: h.b, onReject: h.x, onNext: h.next, onPrev: h.prev, onHelp: h.help })
  return <><input aria-label="حقل" /><textarea aria-label="نص" /><div contentEditable suppressContentEditableWarning role="textbox" aria-label="محرر" /></>
}
const handlers = () => ({ b: vi.fn(), x: vi.fn(), next: vi.fn(), prev: vi.fn(), help: vi.fn() })

it('maps keys; arrows follow RTL reading order', async () => {
  const h = handlers()
  render(<Harness h={h} />)
  await userEvent.keyboard('bBxX')
  await userEvent.keyboard('{ArrowLeft}{ArrowRight}?')
  expect(h.b).toHaveBeenCalledTimes(2)
  expect(h.x).toHaveBeenCalledTimes(2)
  expect(h.next).toHaveBeenCalledTimes(1)
  expect(h.prev).toHaveBeenCalledTimes(1)
  expect(h.help).toHaveBeenCalledTimes(1)
})

it('ignores typing in inputs, textareas and contenteditable', async () => {
  const h = handlers()
  render(<Harness h={h} />)
  for (const name of ['حقل', 'نص', 'محرر']) {
    await userEvent.click(screen.getByLabelText(name))
    await userEvent.keyboard('bx{ArrowLeft}?')
  }
  expect(h.b).not.toHaveBeenCalled()
  expect(h.x).not.toHaveBeenCalled()
  expect(h.next).not.toHaveBeenCalled()
  expect(h.help).not.toHaveBeenCalled()
})

it('ignores modifier combos and does nothing when disabled', async () => {
  const h = handlers()
  const { rerender } = render(<Harness h={h} />)
  await userEvent.keyboard('{Control>}b{/Control}{Meta>}x{/Meta}')
  expect(h.b).not.toHaveBeenCalled()
  expect(h.x).not.toHaveBeenCalled()
  rerender(<Harness h={h} enabled={false} />)
  await userEvent.keyboard('b')
  expect(h.b).not.toHaveBeenCalled()
})

it('ignores keys while a dialog is open', async () => {
  const h = handlers()
  render(<><Harness h={h} /><div role="dialog" /></>)
  await userEvent.keyboard('b')
  expect(h.b).not.toHaveBeenCalled()
})
