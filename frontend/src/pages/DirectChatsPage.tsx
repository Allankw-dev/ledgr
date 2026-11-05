import { AppShell } from '../components/AppShell';
import { DirectChat } from '../components/DirectChat';

export function DirectChatsPage() {
  return (
    <AppShell>
      <div className="max-w-6xl mx-auto px-4 sm:px-8 py-6 sm:py-8">
        <div className="mb-6">
          <h1 className="font-display text-2xl text-ink-900 font-medium reveal">Private chats</h1>
          <p className="text-sm text-ink-600 mt-1">
            Message a parent one-to-one. It's private to the two of you and stored encrypted, unless a chat is reported, in which case the school administrator can review the reported messages.
          </p>
        </div>
        <DirectChat />
      </div>
    </AppShell>
  );
}
