import { useEffect, useRef, useState, type FormEvent } from 'react';
import { MessageCircle, Send } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import {
  getConversations,
  getConversation,
  sendConversationReply,
  type ConversationSummary,
  type Message,
} from '../api/messages';

function formatWhen(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  return sameDay
    ? d.toLocaleTimeString('en-KE', { hour: 'numeric', minute: '2-digit' })
    : d.toLocaleDateString('en-KE', { day: 'numeric', month: 'short' });
}

export function MessagesPage() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [thread, setThread] = useState<Message[]>([]);
  const [loadingThread, setLoadingThread] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  async function loadConversations() {
    setLoadingList(true);
    try {
      setConversations(await getConversations());
    } catch {
      setError('Could not load conversations.');
    } finally {
      setLoadingList(false);
    }
  }

  useEffect(() => {
    loadConversations();
  }, []);

  async function openConversation(parentUserId: string) {
    setSelected(parentUserId);
    setLoadingThread(true);
    setError(null);
    try {
      setThread(await getConversation(parentUserId));
      // Clear the unread badge locally without a full refetch.
      setConversations((prev) => prev.map((c) => (c.parent_user_id === parentUserId ? { ...c, unread_count: 0 } : c)));
    } catch {
      setError('Could not load this conversation.');
    } finally {
      setLoadingThread(false);
    }
  }

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [thread]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || !selected || sending) return;

    setSending(true);
    setError(null);
    try {
      const sent = await sendConversationReply(selected, trimmed);
      setThread((prev) => [...prev, sent]);
      setInput('');
      loadConversations();
    } catch {
      setError('Could not send that reply. Try again.');
    } finally {
      setSending(false);
    }
  }

  return (
    <AppShell>
      <div className="px-8 py-8 h-screen flex flex-col">
        <div className="mb-6">
          <h1 className="font-display text-2xl text-ink-900 font-medium">Messages</h1>
          <p className="text-sm text-ink-600 mt-1">Questions from parents about fees, invoices, and payments.</p>
        </div>

        <div className="flex-1 min-h-0 flex border border-ink-200 rounded-lg overflow-hidden bg-white">
          <div className="w-72 shrink-0 border-r border-ink-200 overflow-y-auto">
            {loadingList ? (
              <p className="text-sm text-ink-600 px-4 py-4">Loading…</p>
            ) : conversations.length === 0 ? (
              <p className="text-sm text-ink-600 px-4 py-4">No messages yet.</p>
            ) : (
              conversations.map((c) => (
                <button
                  key={c.parent_user_id}
                  onClick={() => openConversation(c.parent_user_id)}
                  className={`w-full text-left px-4 py-3 border-b border-ink-100 hover:bg-ink-100/60 transition-colors ${
                    selected === c.parent_user_id ? 'bg-ink-100' : ''
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium text-ink-900 truncate">{c.parent_name}</p>
                    <span className="text-xs text-ink-500 shrink-0">{formatWhen(c.last_message_at)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2 mt-0.5">
                    <p className="text-xs text-ink-600 truncate">
                      {c.last_message_sender_role === 'STAFF' ? 'You: ' : ''}
                      {c.last_message_body}
                    </p>
                    {c.unread_count > 0 && (
                      <span className="text-xs bg-clay-700 text-white rounded-full w-5 h-5 flex items-center justify-center shrink-0">
                        {c.unread_count}
                      </span>
                    )}
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="flex-1 min-w-0 flex flex-col">
            {!selected ? (
              <div className="flex-1 flex items-center justify-center text-ink-500 text-sm flex-col gap-2">
                <MessageCircle className="w-6 h-6" />
                Select a conversation
              </div>
            ) : (
              <>
                <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-3">
                  {loadingThread ? (
                    <p className="text-sm text-ink-600">Loading…</p>
                  ) : (
                    thread.map((m) => (
                      <div key={m.id} className={`flex ${m.sender_role === 'STAFF' ? 'justify-end' : 'justify-start'}`}>
                        <div
                          className={`max-w-[70%] rounded-lg px-3.5 py-2 text-sm whitespace-pre-wrap ${
                            m.sender_role === 'STAFF' ? 'bg-ink-900 text-paper' : 'bg-ink-100 text-ink-900'
                          }`}
                        >
                          {m.sender_role === 'PARENT' && (
                            <p className="text-xs font-medium text-ink-600 mb-0.5">{m.sender_name}</p>
                          )}
                          {m.student_name && <p className="text-xs opacity-70 mb-0.5">Re: {m.student_name}</p>}
                          {m.body}
                        </div>
                      </div>
                    ))
                  )}
                  {error && <p className="text-xs text-clay-700">{error}</p>}
                  <div ref={scrollRef} />
                </div>

                <form onSubmit={handleSubmit} className="flex items-center gap-2 px-6 py-4 border-t border-ink-200">
                  <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Type a reply…"
                    className="flex-1 px-3.5 py-2 rounded-md border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-ink-900/20"
                    disabled={sending}
                  />
                  <button
                    type="submit"
                    disabled={sending || !input.trim()}
                    className="p-2 rounded-md bg-ink-900 text-paper hover:bg-ink-800 disabled:opacity-40 disabled:cursor-not-allowed"
                    aria-label="Send"
                  >
                    <Send className="w-4 h-4" strokeWidth={2} />
                  </button>
                </form>
              </>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
