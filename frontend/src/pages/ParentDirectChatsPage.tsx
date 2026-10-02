import { ParentShell } from '../components/ParentShell';
import { ChatTabs } from '../components/ChatTabs';
import { DirectChat } from '../components/DirectChat';

export function ParentDirectChatsPage() {
  return (
    <ParentShell>
      <div className="md:hidden">
        <ChatTabs />
      </div>
      <div className="hidden md:block mb-6">
        <h1 className="font-display text-xl sm:text-2xl text-ink-900 font-medium reveal">Teacher chats</h1>
        <p className="hidden sm:block text-sm text-ink-600 mt-1">
          Message your child's teacher privately. Only the two of you can see the conversation, and it's stored encrypted.
        </p>
      </div>
      <DirectChat />
    </ParentShell>
  );
}
