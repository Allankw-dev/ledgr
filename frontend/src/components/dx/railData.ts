import { AlertTriangle, AtSign, Flag, MessageCircle, MessagesSquare, Users2, type LucideIcon } from 'lucide-react';
import type { MentionNotification } from '../../types';
import { pluralize, timeAgo } from './format';

export interface RailNotice {
  key: string;
  title: string;
  hint: string;
  /** Omitted when there is nowhere better to send the person than where they already are. */
  to?: string;
  icon: LucideIcon;
  tone: 'green' | 'amber' | 'coral';
}

type MentionLite = Pick<MentionNotification, 'id' | 'seen' | 'sender_name' | 'class_name' | 'class_id' | 'created_at'>;

interface Common {
  unreadMessages: number;
  unreadClassGroups: number;
  mentions: MentionLite[];
}

const MAX_NOTICES = 5;

function mentionNotices(mentions: MentionLite[], chatPath: string, now?: number): RailNotice[] {
  return mentions
    .filter((m) => !m.seen)
    .slice(0, 2)
    .map((m) => ({
      key: `mention-${m.id}`,
      title: `${m.sender_name} mentioned you in ${m.class_name}`,
      hint: timeAgo(m.created_at, now),
      to: `${chatPath}?class=${m.class_id}`,
      icon: AtSign,
      tone: 'amber' as const,
    }));
}

/** What the admin/bursar rail lists. Counts only appear when they are above zero, so the list is honest about being empty. */
export function buildAdminNotices(i: Common & { flagged: number; overdue: number }, now?: number): RailNotice[] {
  const out: RailNotice[] = [...mentionNotices(i.mentions, '/class-groups', now)];
  if (i.unreadMessages > 0)
    out.push({ key: 'messages', title: `${pluralize(i.unreadMessages, 'new message')} from parents`, hint: 'Messages', to: '/messages', icon: MessageCircle, tone: 'green' });
  if (i.unreadClassGroups > 0)
    out.push({ key: 'class', title: `${pluralize(i.unreadClassGroups, 'unread class group message')}`, hint: 'Class groups', to: '/class-groups', icon: Users2, tone: 'green' });
  if (i.flagged > 0)
    out.push({ key: 'flagged', title: `${pluralize(i.flagged, 'payment')} flagged for review`, hint: 'See flagged payments below', icon: Flag, tone: 'coral' });
  if (i.overdue > 0)
    out.push({ key: 'overdue', title: `${pluralize(i.overdue, 'invoice')} overdue`, hint: 'Needs follow-up', to: '/invoices', icon: AlertTriangle, tone: 'coral' });
  return out.slice(0, MAX_NOTICES);
}

/** Same idea for a parent: school office, class group, teacher chats and mentions. */
export function buildParentNotices(i: Common & { unreadDirect: number }, now?: number): RailNotice[] {
  const out: RailNotice[] = [...mentionNotices(i.mentions, '/parent/class-group', now)];
  if (i.unreadMessages > 0)
    out.push({ key: 'messages', title: `${pluralize(i.unreadMessages, 'new message')} from the school office`, hint: 'Messages', to: '/parent/dashboard#messages', icon: MessageCircle, tone: 'green' });
  if (i.unreadClassGroups > 0)
    out.push({ key: 'class', title: `${pluralize(i.unreadClassGroups, 'unread class group message')}`, hint: 'Class group', to: '/parent/class-group', icon: Users2, tone: 'green' });
  if (i.unreadDirect > 0)
    out.push({ key: 'direct', title: `${pluralize(i.unreadDirect, 'unread teacher message')}`, hint: 'Teacher chats', to: '/parent/chats', icon: MessagesSquare, tone: 'green' });
  return out.slice(0, MAX_NOTICES);
}
