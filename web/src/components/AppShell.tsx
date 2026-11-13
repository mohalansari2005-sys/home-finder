import { useState, type ReactNode } from 'react'
import { NavLink } from 'react-router'
import { useBreakpoint } from '../lib/breakpoint'
import { IconMenu } from './Icons'
import { NAV_ITEMS } from './nav'

const linkCls = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-3 rounded-xl px-3 py-2 ${isActive ? 'bg-brand-soft text-brand font-semibold' : 'text-slate-700'}`

function SideNav({ compact }: { compact: boolean }) {
  return (
    <nav data-testid="side-nav" className="flex flex-col gap-1 p-3">
      <div className="px-3 py-4 text-xl font-semibold text-brand">بيتنا</div>
      {NAV_ITEMS.map((i) => (
        <NavLink key={i.to} to={i.to} end={i.to === '/'} className={linkCls} title={i.label}>
          <span aria-hidden>{i.icon}</span>
          {!compact && <span>{i.label}</span>}
        </NavLink>
      ))}
    </nav>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const bp = useBreakpoint()
  const [open, setOpen] = useState(false)

  if (bp === 'phone') {
    return (
      <div className="flex h-full flex-col">
        <main className="flex-1 overflow-y-auto pb-20">{children}</main>
        <nav data-testid="bottom-tabs"
             className="fixed inset-x-0 bottom-0 z-20 flex border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)]">
          {NAV_ITEMS.map((i) => (
            <NavLink key={i.to} to={i.to} end={i.to === '/'}
                     className={({ isActive }) => `flex flex-1 flex-col items-center py-2 text-xs ${isActive ? 'text-brand font-semibold' : 'text-slate-500'}`}>
              <span className="text-xl" aria-hidden>{i.icon}</span>{i.label}
            </NavLink>
          ))}
        </nav>
      </div>
    )
  }
  const compact = bp === 'tablet' && !open
  return (
    <div className="flex h-full">
      <aside className={`shrink-0 border-e border-slate-200 bg-white ${compact ? 'w-20' : 'w-60'}`}>
        {bp === 'tablet' && (
          <button aria-label="القائمة" onClick={() => setOpen((o) => !o)} className="m-3 rounded-lg p-2 text-xl"><IconMenu /></button>
        )}
        <SideNav compact={compact} />
      </aside>
      <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  )
}
