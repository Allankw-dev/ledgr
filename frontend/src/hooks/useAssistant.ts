import { useState } from 'react';
import { sendAssistantMessage, type AssistantMessage, type AssistantAction } from '../api/assistant';
import { getErrorMessage } from '../api/client';

export interface DisplayMessage {
  role: 'user' | 'assistant';
  content: string;
  actions?: AssistantAction[];
}

export function useAssistant() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    // Server holds no session state — resend the transcript so far as history.
    const history: AssistantMessage[] = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: 'user', content: trimmed }]);
    setSending(true);
    setError(null);

    try {
      const result = await sendAssistantMessage(trimmed, history);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: result.reply, actions: result.actions_taken },
      ]);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSending(false);
    }
  }

  return { messages, sending, error, sendMessage };
}
