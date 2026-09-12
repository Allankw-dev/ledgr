import { useRef, useState, useEffect, type FormEvent } from 'react';
import { Sparkles, Send } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { queryAssistant, type AssistantMessage } from '../api/assistant';

const SUGGESTIONS = [
  'Which students are overdue right now?',
  'How does this term compare to last term?',
  'Who are the highest-risk unpaid accounts?',
];

export function AssistantPage() {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const nextMessages: AssistantMessage[] = [...messages, { role: 'user', content: trimmed }];
    setMessages(nextMessages);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const answer = await queryAssistant(nextMessages);
      setMessages([...nextMessages, { role: 'assistant', content: answer }]);
    } catch {
      setError('Could not reach the assistant. Try again in a moment.');
      setMessages(messages); // roll back — don't leave an unanswered question in history
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    send(input);
  }

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-4 sm:px-8 py-6 sm:py-8 flex flex-col h-screen">
        <div className="mb-6 shrink-0">
          <h1 className="font-display text-2xl text-ink-900 font-medium flex items-center gap-2">
            <Sparkles className="w-5 h-5" strokeWidth={1.75} />
            Ask Ledgr
          </h1>
          <p className="text-sm text-ink-600 mt-1">
            Ask about students, invoices, or collection — it looks up real data, it doesn't guess.
          </p>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-4 pb-4">
          {messages.length === 0 && (
            <div className="flex flex-col gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left text-sm px-4 py-3 rounded-lg border border-ink-200 bg-panel hover:bg-ink-100 text-ink-700"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] rounded-lg px-4 py-2.5 text-sm whitespace-pre-wrap ${
                  m.role === 'user' ? 'bg-ink-800 text-ink-900' : 'bg-panel border border-ink-200 text-ink-900'
                }`}
              >
                {m.content}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-panel border border-ink-200 rounded-lg px-4 py-2.5 text-sm text-ink-600">
                Looking that up…
              </div>
            </div>
          )}

          {error && (
            <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm">
              {error}
            </div>
          )}

          <div ref={scrollRef} />
        </div>

        <form onSubmit={handleSubmit} className="shrink-0 flex items-center gap-2 pt-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about students, invoices, or collection…"
            className="flex-1 px-4 py-2.5 rounded-md border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-ink-900/20"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="p-2.5 rounded-md bg-gradient-to-br from-emerald-700 to-cyan text-[#06110B] hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="Send"
          >
            <Send className="w-4 h-4" strokeWidth={2} />
          </button>
        </form>
      </div>
    </AppShell>
  );
}
