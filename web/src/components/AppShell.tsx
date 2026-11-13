import { useEffect, useRef, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router'
import { PanelRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Sidebar, SidebarContent, SidebarHeader, SidebarInset, SidebarMenu, SidebarMenuButton, SidebarMenuItem,
  SidebarProvider, useSidebar,
} from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { useBreakpoint, useChatLayout } from '../lib/breakpoint'
import { ChatDock } from './chat/ChatDock'
import { ChatOverlay } from './chat/ChatOverlay'
import { NAV_ITEMS } from './nav'

function MenuToggle() {
  const { toggleSidebar } = useSidebar()
  return (
    <Button variant="ghost" size="icon" aria-label="القائمة" onClick={toggleSidebar} className="m-2">
      <PanelRight aria-hidden strokeWidth={1.75} />
    </Button>
  )
}

function SideNav({ toggle }: { toggle: boolean }) {
  return (
    <Sidebar side="right" collapsible={toggle ? 'icon' : 'none'} className="h-dvh border-s">
      <SidebarHeader>
        {toggle && <MenuToggle />}
        <div className="px-3 py-2 font-display text-xl font-semibold text-primary group-data-[collapsible=icon]:hidden">بيتنا</div>
      </SidebarHeader>
      <SidebarContent data-testid="side-nav">
        <SidebarMenu className="gap-1 p-2">
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <SidebarMenuItem key={to}>
              <NavLink to={to} end={to === '/'}>
                {({ isActive }) => (
                  <SidebarMenuButton asChild isActive={isActive} tooltip={label} size="lg" className="h-11 text-base">
                    <span><Icon strokeWidth={1.75} className="size-5" aria-hidden /><span className="group-data-[collapsible=icon]:hidden">{label}</span></span>
                  </SidebarMenuButton>
                )}
              </NavLink>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarContent>
    </Sidebar>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const bp = useBreakpoint()
  const layout = useChatLayout()
  const { pathname } = useLocation()
  const main = useRef<HTMLElement>(null)
  useEffect(() => { main.current?.focus({ preventScroll: true }) }, [pathname])

  if (bp === 'phone') {
    return (
      <div className="flex min-h-dvh flex-col">
        <main ref={main} tabIndex={-1} className="flex-1 pb-[calc(4.5rem+env(safe-area-inset-bottom))] outline-none">{children}</main>
        <nav data-testid="bottom-tabs" aria-label="التنقل الرئيسي"
             className="fixed inset-x-0 bottom-0 z-20 flex border-t bg-card pb-[env(safe-area-inset-bottom)] shadow-sm">
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <NavLink key={to} to={to} end={to === '/'}
                     className={({ isActive }) => cn('relative flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring',
                       isActive ? 'font-semibold text-primary' : 'text-muted-foreground')}>
              {({ isActive }) => (
                <>
                  {isActive && <span className="absolute inset-x-6 top-0 h-0.5 rounded-full bg-primary" aria-hidden />}
                  <Icon className="size-5" strokeWidth={1.75} aria-hidden />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </div>
    )
  }
  return (
    <TooltipProvider>
    <SidebarProvider key={bp} defaultOpen={bp === 'desktop'} className="min-h-dvh">
      <SideNav toggle={bp === 'tablet'} />
      <SidebarInset className="min-w-0">
        <main ref={main} tabIndex={-1} className="h-dvh min-w-0 overflow-y-auto outline-none">{children}</main>
      </SidebarInset>
      {pathname !== '/assistant' && (layout === 'docked' ? <ChatDock /> : <ChatOverlay />)}
    </SidebarProvider>
    </TooltipProvider>
  )
}
