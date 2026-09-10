import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Sparkles, Send, ChevronUp, ChevronDown } from 'lucide-react';
import { queryParentAssistant, type AssistantMessage } from '../api/parentAssistant';

const SUGGESTIONS = ['Has my payment gone through?', "What's still owed this term?", 'When is the next payment due?'];

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading, open]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const nextMessages: AssistantMessage[] = [...messages, { role: 'user', content: trimmed }];
    setMessages(nextMessages);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const answer = await queryParentAssistant(nextMessages);
      setMessages([...nextMessages, { role: 'assistant', content: answer }]);
    } catch {
      setError('Could not reach the assistant. Try again in a moment.');
      setMessages(messages);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    send(input);
  }

  return (
    <div className="bg-panel border border-ink-200 rounded-lg overflow-hidden mt-6">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-5 py-4 flex items-center justify-between text-left"
      >
        <span className="flex items-center gap-2 font-display text-base text-ink-900 font-medium">
          <Sparkles className="w-4 h-4" strokeWidth={2} />
          Ask about your fees
        </span>
        {open ? <ChevronUp className="w-4 h-4 text-ink-600" /> : <ChevronDown className="w-4 h-4 text-ink-600" />}
      </button>

      {open && (
        <div className="border-t border-ink-100 flex flex-col">
          <div className="max-h-80 overflow-y-auto px-5 py-4 flex flex-col gap-3">
            {messages.length === 0 && (
              <div className="flex flex-col gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="text-left text-sm px-3.5 py-2.5 rounded-md border border-ink-200 hover:bg-ink-100 text-ink-700"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[85%] rounded-lg px-3.5 py-2 text-sm whitespace-pre-wrap ${
                    m.role === 'user' ? 'bg-ink-800 text-ink-900' : 'bg-ink-100 text-ink-900'
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}

            {loading && <p className="text-xs text-ink-400">Looking that up…</p>}
            {error && <p className="text-xs text-clay-700">{error}</p>}
            <div ref={scrollRef} />
          </div>

          <form onSubmit={handleSubmit} className="flex items-center gap-2 px-5 py-3 border-t border-ink-100">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question…"
              className="flex-1 px-3.5 py-2 rounded-md border border-ink-200 text-sm focus:outline-none focus:ring-2 focus:ring-ink-900/20"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
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
