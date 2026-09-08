import { ParentShell } from '../components/ParentShell';
import { ChatWidget } from '../components/ChatWidget';

export function ParentAssistantPage() {
  return (
    <ParentShell>
      <h1 className="font-display text-2xl text-ink-900 font-medium mb-1">Assistant</h1>
      <p className="text-sm text-ink-600 mb-6">
        Ask about balances, payments, or invoices for any of your children.
      </p>
      <ChatWidget />
    </ParentShell>
  );
}
