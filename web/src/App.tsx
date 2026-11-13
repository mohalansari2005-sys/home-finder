import { Navigate, Route, Routes } from 'react-router'
import { useMe } from './api/hooks'
import { AppShell } from './components/AppShell'
import { LoginPage } from './pages/LoginPage'
import { FeedPage } from './pages/FeedPage'
import { MapPage } from './pages/MapPage'
import { ListingPage } from './pages/ListingPage'
import { SettingsPage } from './pages/SettingsPage'

function Protected({ children }: { children: React.ReactNode }) {
  const me = useMe()
  if (me.isLoading) return <div className="p-6 text-slate-500">جارٍ التحميل…</div>
  if (me.isError) return <Navigate to="/login" replace />
  return <AppShell>{children}</AppShell>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Protected><FeedPage /></Protected>} />
      <Route path="/map" element={<Protected><MapPage /></Protected>} />
      <Route path="/listing/:id" element={<Protected><ListingPage /></Protected>} />
      <Route path="/settings" element={<Protected><SettingsPage /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
