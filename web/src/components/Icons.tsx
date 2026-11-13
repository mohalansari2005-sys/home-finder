// Small inline SVG icons for controls (typed symbols may be missing from the Arabic font).
// Directional icons use currentColor and rely on the RTL layout: ChevronBack points to the START side's opposite
// (i.e. "back" in RTL points right), implemented by flipping horizontally only when the page is LTR.
import type { SVGProps } from 'react'

const base = { width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2,
  strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true } as const
type P = SVGProps<SVGSVGElement>

export const IconClose = (p: P) => <svg {...base} {...p}><path d="M6 6l12 12M18 6L6 18" /></svg>
export const IconMenu = (p: P) => <svg {...base} {...p}><path d="M4 7h16M4 12h16M4 17h16" /></svg>
export const IconCheck = (p: P) => <svg {...base} {...p}><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
export const IconExternal = (p: P) => <svg {...base} {...p}><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></svg>
/** Back arrow: in RTL "back" points to the right (towards the start edge). Flipped via rtl:/ltr: variants. */
export const IconBack = (p: P) => (
  <svg {...base} {...p} className={`ltr:-scale-x-100 ${p.className ?? ''}`}><path d="M9 5l7 7-7 7" /></svg>
)
