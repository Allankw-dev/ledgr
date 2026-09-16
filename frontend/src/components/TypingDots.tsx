/** Three dots bouncing in sequence inside an incoming-message-shaped
 * bubble — the WhatsApp "typing…" indicator. Pure CSS animation (see the
 * .typing-dot keyframes in index.css), no JS timers. */
export function TypingDots() {
  return (
    <div className="flex justify-start">
      <div className="bg-ink-100 rounded-lg px-4 py-3 flex items-center gap-1" aria-label="Typing…">
        <span className="typing-dot" style={{ animationDelay: '0ms' }} />
        <span className="typing-dot" style={{ animationDelay: '160ms' }} />
        <span className="typing-dot" style={{ animationDelay: '320ms' }} />
      </div>
    </div>
  );
}
