import { render } from '@testing-library/react'
import { useRef } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAutoGrow } from './useAutoGrow'

function Box({ value, scrollHeight }: { value: string; scrollHeight: number }) {
  const ref = useRef<HTMLTextAreaElement>(null)
  useAutoGrow(ref, value)
  return <textarea ref={(el) => { if (el) Object.defineProperty(el, 'scrollHeight', { value: scrollHeight, configurable: true }); ref.current = el }} readOnly value={value} />
}
const ta = (c: HTMLElement) => c.querySelector('textarea')!
const stub = (supported: boolean) => vi.stubGlobal('CSS', { supports: vi.fn(() => supported) })
afterEach(() => vi.unstubAllGlobals())

describe('useAutoGrow', () => {
  it('does nothing when field-sizing is supported', () => {
    stub(true)
    const { container } = render(<Box value="x" scrollHeight={80} />)
    expect(ta(container).style.height).toBe('')
  })
  it('grows to scrollHeight without a scrollbar when field-sizing is unsupported', () => {
    stub(false)
    const { container, rerender } = render(<Box value="x" scrollHeight={44} />)
    expect(CSS.supports).toHaveBeenCalledWith('field-sizing', 'content')
    expect(ta(container).style.height).toBe('44px')
    expect(ta(container).style.overflowY).toBe('hidden')
    rerender(<Box value="x y" scrollHeight={80} />)
    expect(ta(container).style.height).toBe('80px')
  })
  it('caps at about 5 lines and then scrolls', () => {
    stub(false)
    const { container } = render(<Box value="long" scrollHeight={400} />)
    expect(ta(container).style.height).toBe('120px')
    expect(ta(container).style.overflowY).toBe('auto')
  })
})
