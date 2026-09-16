import { useEffect, useRef, useState, type FormEvent } from 'react';
import { MessageCircle, Send, ChevronUp, ChevronDown } from 'lucide-react';
import { getMyMessages, sendMyMessage, pingMyTyping, getStaffTypingStatus, type Message } from '../api/messages';
import { MessageTicks } from './MessageTicks';
import { TypingDots } from './TypingDots';

const POLL_MESSAGES_MS = 3000;
const POLL_TYPING_MS = 1500;
const TYPING_PING_THROTTLE_MS = 2000;

export function MessagePanel() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [staffTyping, setStaffTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
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
  // panel is open. Merges by id rather than replacing wholesale so a
  // message mid-send locally isn't ever momentarily duplicated or dropped.
  useEffect(() => {
    if (!open) return;
    const id = setInterval(() => {
      getMyMessages()
        .then(setMessages)
        .catch(() => {
          /* a missed poll isn't worth surfacing as an error */
        });
    }, POLL_MESSAGES_MS);
    return () => clearInterval(id);
  }, [open]);

  // Poll whether staff is currently typing.
  useEffect(() => {
    if (!open) return;
    const id = setInterval(() => {
      getStaffTypingStatus()
        .then(setStaffTyping)
        .catch(() => {});
    }, POLL_TYPING_MS);
    return () => clearInterval(id);
  }, [open]);

  useEffect(() => {
    if (open) scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, staffTyping, open]);

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
    <div className="bg-panel border border-ink-200 rounded-lg overflow-hidden mt-6">
      <button onClick={() => setOpen(!open)} className="w-full px-5 py-4 flex items-center justify-between text-left">
        <span className="flex items-center gap-2 font-display text-base text-ink-900 font-medium">
          <MessageCircle className="w-4 h-4" strokeWidth={2} />
          Message the school
        </span>
        {open ? <ChevronUp className="w-4 h-4 text-ink-600" /> : <ChevronDown className="w-4 h-4 text-ink-600" />}
      </button>

      {open && (
        <div className="border-t border-ink-100 flex flex-col">
          <div className="max-h-80 overflow-y-auto px-5 py-4 flex flex-col gap-3">
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
            <div ref={scrollRef} />
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
