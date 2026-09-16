/**
 * WhatsApp-style read receipt: a single grey check for "sent", doubled and
 * turned blue once the other side has read it. There's no separate
 * "delivered" (double grey) state here — this app doesn't track delivery
 * as a distinct event from read, so it's an honest two states, not three.
 */
export function MessageTicks({ read }: { read: boolean }) {
  return (
    <svg
      viewBox="0 0 18 12"
      width="16"
      height="11"
      aria-label={read ? 'Read' : 'Sent'}
      className="inline-block shrink-0 align-middle"
    >
      <path
        d="M1 6.5L4.5 10L10.5 2"
        fill="none"
        stroke={read ? '#53bdeb' : 'currentColor'}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {read && (
        <path
          d="M6.5 6.5L10 10L17 2"
          fill="none"
          stroke="#53bdeb"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
    </svg>
  );
}
