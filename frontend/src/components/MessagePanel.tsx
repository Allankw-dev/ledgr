import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useLocation } from 'react-router-dom';
import { MessageCircle, Send, ChevronDown } from 'lucide-react';
import { getMyMessages, sendMyMessage, pingMyTyping, getStaffTypingStatus, type Message } from '../api/messages';
import { MessageTicks } from './MessageTicks';
import { TypingDots } from './TypingDots';
import { usePolling } from '../hooks/usePolling';

const POLL_MESSAGES_MS = 3000;
const POLL_TYPING_MS = 1500;
const TYPING_PING_THROTTLE_MS = 2000;

export function MessagePanel() {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Links like /parent/dashboard#messages (the "School office" shortcut) open this panel and bring it into
  // view. Keyed on location.key as well, so using the link again while already here still works.
  const location = useLocation();
  useEffect(() => {
    if (location.hash !== '#messages') return;
    setOpen(true);
    const t = window.setTimeout(() => panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 150);
    return () => window.clearTimeout(t);
  }, [location.key, location.hash]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [staffTyping, setStaffTyping] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  // True while the person is reading at the bottom; false once they scroll
  // up to read older messages, so new activity never drags them back down.
  const stickRef = useRef(true);
  const lastTypingPingRef = useRef(0);

  useEffect(() => {
    if (open && !loaded) {
      getMyMessages()
        .then(setMessages)
        .catch(() => setError('Could not load your messages.'))
        .finally(() => setLoaded(true));
    }
  }, [open, loaded]);

  // Poll for new messages (and updated read receipts on ours) while the
  // panel is open. usePolling waits for each request to finish and pauses
  // while the tab is hidden, so an open-but-forgotten chat costs nothing.
  usePolling(() => getMyMessages().then(setMessages), POLL_MESSAGES_MS, open);

  // Poll whether staff is currently typing.
  usePolling(() => getStaffTypingStatus().then(setStaffTyping), POLL_TYPING_MS, open);

  // Scroll only the message list itself (never the page), and only when
  // something actually new arrived while the person is at the bottom. The
  // 3-second poll hands back a fresh array every time, so depend on the
  // count / last id rather than the array.
  const count = messages.length;
  const lastId = messages[messages.length - 1]?.id;
  useEffect(() => {
    const el = listRef.current;
    if (!open || !el || !stickRef.current) return;
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [count, lastId, staffTyping, open]);

  // Opening the panel starts at the latest message.
  useEffect(() => {
    if (!open) return;
    stickRef.current = true;
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [open, loaded]);

  function onListScroll() {
    const el = listRef.current;
    if (!el) return;
    stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }

  function handleInputChange(value: string) {
    setInput(value);
    const now = Date.now();
    if (value.trim() && now - lastTypingPingRef.current > TYPING_PING_THROTTLE_MS) {
      lastTypingPingRef.current = now;
      pingMyTyping().catch(() => {});
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    setSending(true);
    setError(null);
    stickRef.current = true;
    try {
      const sent = await sendMyMessage(trimmed);
      setMessages((prev) => [...prev, sent]);
      setInput('');
    } catch {
      setError('Could not send that message. Try again in a moment.');
    } finally {
      setSending(false);
    }
  }

  return (
    <div ref={panelRef} id="messages" className="bg-panel border border-ink-200 rounded-lg overflow-hidden mt-6">
      <button onClick={() => setOpen(!open)} className="w-full px-5 py-4 flex items-center justify-between text-left">
        <span className="flex items-center gap-2 font-display text-base text-ink-900 font-medium">
          <MessageCircle className="w-4 h-4" strokeWidth={2} />
          Message the school
        </span>
        <ChevronDown className={`w-4 h-4 text-ink-600 transition-transform duration-300 ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="expand-in border-t border-ink-100 flex flex-col">
          <div ref={listRef} onScroll={onListScroll} className="max-h-80 overflow-y-auto overscroll-contain px-5 py-4 flex flex-col gap-3">
            {loaded && messages.length === 0 && (
              <p className="text-sm text-ink-600">
                Have a question about fees, an invoice, or a payment? Send a message and the school's office will get
                back to you here.
              </p>
            )}

            {messages.map((m) => (
              <div key={m.id} className={`flex ${m.sender_role === 'PARENT' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[85%] rounded-lg px-3.5 py-2 text-sm whitespace-pre-wrap ${
                    m.sender_role === 'PARENT' ? 'bg-ink-800 text-ink-900' : 'bg-ink-100 text-ink-900'
                  }`}
                >
                  {m.sender_role === 'STAFF' && <p className="text-xs font-medium text-ink-600 mb-0.5">{m.sender_name}</p>}
                  {m.body}
                  {m.sender_role === 'PARENT' && (
                    <span className="flex justify-end mt-1 text-ink-500">
                      <MessageTicks read={!!m.read_at} />
                    </span>
                  )}
                </div>
              </div>
            ))}

            {staffTyping && <TypingDots />}

            {error && <p className="text-xs text-clay-700">{error}</p>}
          </div>

          <form onSubmit={handleSubmit} className="flex items-center gap-2 px-5 py-3 border-t border-ink-100">
            <input
              value={input}
              onChange={(e) => handleInputChange(e.target.value)}
              placeholder="Type a message…"
              className="flex-1 px-3.5 py-2 rounded-md border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-ink-900/20"
              disabled={sending}
            />
            <button
              type="submit"
              disabled={sending || !input.trim()}
              className="p-2 rounded-md bg-gradient-to-br from-emerald-700 to-cyan text-[#06110B] hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="Send"
            >
              <Send className="w-4 h-4" strokeWidth={2} />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
