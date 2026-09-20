import type { MessageStatus } from '../types';

/**
 * WhatsApp-style receipt.
 *   sent      -> one grey tick   (saved on the server)
 *   delivered -> two grey ticks  (reached everyone's device)
 *   read      -> two BLUE ticks  (everyone has read it)
 *
 * The 1:1 chats only track sent/read, so they keep passing `read`; the class
 * group chat passes the three-state `status`.
 */
export function MessageTicks({ read, status }: { read?: boolean; status?: MessageStatus | null }) {
  const state: MessageStatus = status ?? (read ? 'read' : 'sent');
  const double = state !== 'sent';
  const color = state === 'read' ? '#53bdeb' : 'currentColor';
  const label = state === 'read' ? 'Read' : state === 'delivered' ? 'Delivered' : 'Sent';
  return (
    <svg viewBox="0 0 18 12" width="16" height="11" aria-label={label} role="img" className="inline-block shrink-0 align-middle">
      <path d="M1 6.5L4.5 10L10.5 2" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      {double && (
        <path d="M6.5 6.5L10 10L17 2" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      )}
    </svg>
  );
}
