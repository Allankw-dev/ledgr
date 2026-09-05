import { useEffect, useRef, useState } from 'react';
import { Sparkles, Send, CheckCircle2 } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { useAssistant } from '../hooks/useAssistant';

const SUGGESTED_PROMPTS = [
  'How much have we collected this term?',
  'Which invoices are highest risk right now?',
  'What should we expect to collect next term?',
];

export function AssistantPage() {
  const { messages, sending, error, sendMessage } = useAssistant();
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, sending]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || sending) return;
    sendMessage(input);
    setInput('');
  }

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-8 py-8 h-screen flex flex-col">
        <div className="mb-6 shrink-0">
          <h1 className="font-display text-2xl text-ink-900 font-medium flex items-center gap-2.5">
            <Sparkles className="w-5.5 h-5.5" strokeWidth={1.75} />
            Bursar assistant
          </h1>
          <p className="text-sm text-ink-600 mt-1">
            Ask about collections, risk, or ask it to remind a guardian about a balance.
          </p>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto min-h-0 -mx-2 px-2">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center gap-4 text-center">
              <div className="w-11 h-11 rounded-full bg-ink-100 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-ink-600" strokeWidth={1.75} />
              </div>
              <p className="text-sm text-ink-600 max-w-xs">
                It can look up collection numbers, flag risky invoices, and send fee reminders when you ask.
              </p>
              <div className="flex flex-col gap-2 w-full max-w-sm">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => sendMessage(prompt)}
                    className="text-left text-sm px-4 py-2.5 rounded-md border border-ink-200 text-ink-700 hover:bg-ink-100 transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-4 pb-4">
              {messages.map((m, i) => (
                <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[85%] rounded-lg px-4 py-2.5 text-sm whitespace-pre-wrap ${
                      m.role === 'user'
                        ? 'bg-ink-900 text-paper'
                        : 'bg-white border border-ink-200 text-ink-900'
                    }`}
                  >
                    {m.content}
                    {m.actions && m.actions.length > 0 && (
                      <div className="mt-2.5 pt-2.5 border-t border-ink-100 flex flex-col gap-1.5">
                        {m.actions.map((a, j) => (
                          <div key={j} className="flex items-start gap-1.5 text-xs text-emerald-700">
                            <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 shrink-0" strokeWidth={2} />
                            <span>{a.result_summary}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {sending && (
                <div className="flex justify-start">
                  <div className="bg-white border border-ink-200 rounded-lg px-4 py-2.5 text-sm text-ink-400">
                    Thinking…
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {error && (
          <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm mb-3 shrink-0">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="shrink-0 flex items-center gap-2 pt-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about collections, risk, or reminders…"
            disabled={sending}
            className="flex-1 px-4 py-2.5 rounded-md border border-ink-200 text-sm text-ink-900 placeholder:text-ink-400 focus:outline-none focus:border-ink-600 disabled:bg-ink-100"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="px-4 py-2.5 rounded-md bg-ink-900 text-paper disabled:bg-ink-400 disabled:cursor-not-allowed hover:bg-ink-800 transition-colors"
            aria-label="Send message"
          >
            <Send className="w-4 h-4" strokeWidth={2} />
          </button>
        </form>
      </div>
    </AppShell>
  );
}
