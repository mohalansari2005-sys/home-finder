import { ChatPanel } from '../components/chat/ChatPanel'

/** Full-page chat: the phone tab, and the المساعد entry in the tablet/desktop sidebar. */
export function AssistantPage() {
  return (
    <div className="h-[calc(100dvh-4.5rem-env(safe-area-inset-bottom))] md:h-full">
      <ChatPanel variant="page" />
    </div>
  )
}
