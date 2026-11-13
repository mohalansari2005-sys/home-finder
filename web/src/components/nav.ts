export interface NavItem { to: string; label: string; icon: string }
export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'الرئيسية', icon: '🏠' },
  { to: '/map', label: 'الخريطة', icon: '🗺️' },
  { to: '/settings', label: 'الإعدادات', icon: '⚙️' },
]
