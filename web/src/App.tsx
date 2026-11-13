import { Navigate, Route, Routes } from 'react-router'
import { useMe } from './api/hooks'
import { ChatProvider } from './components/chat/ChatProvider'
import { AppShell } from './components/AppShell'
import { LoginPage } from './pages/LoginPage'
import { FeedPage } from './pages/FeedPage'
import { MapPage } from './pages/MapPage'
import { ComparePage } from './pages/ComparePage'
import { ListingPage } from './pages/ListingPage'
import { AssistantPage } from './pages/AssistantPage'
import { VisitsPage } from './pages/VisitsPage'
import { TripPage } from './pages/TripPage'
import { SettingsPage } from './pages/SettingsPage'

function Protected({ children }: { children: React.ReactNode }) {
  const me = useMe()
  if (me.isLoading) return <div className="p-6 text-slate-500">جارٍ التحميل…</div>
  if (me.isError) return <Navigate to="/login" replace />
  return <AppShell>{children}</AppShell>
}

export default function App() {
  return (
    <ChatProvider>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Protected><FeedPage /></Protected>} />
      <Route path="/map" element={<Protected><MapPage /></Protected>} />
      <Route path="/listing/:id" element={<Protected><ListingPage /></Protected>} />
      <Route path="/compare" element={<Protected><ComparePage /></Protected>} />
      <Route path="/assistant" element={<Protected><AssistantPage /></Protected>} />
      <Route path="/visits" element={<Protected><VisitsPage /></Protected>} />
      <Route path="/visits/:id" element={<Protected><TripPage /></Protected>} />
      <Route path="/settings" element={<Protected><SettingsPage /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </ChatProvider>
  )
}
