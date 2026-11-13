import { House, Map, Settings, type LucideIcon } from 'lucide-react'

export interface NavItem { to: string; label: string; Icon: LucideIcon }
export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'الرئيسية', Icon: House },
  { to: '/map', label: 'الخريطة', Icon: Map },
  { to: '/settings', label: 'الإعدادات', Icon: Settings },
]
