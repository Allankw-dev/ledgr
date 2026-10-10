import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Bell, ChevronRight, Mail, MessageCircle, MessagesSquare, Phone, Sparkles, Users2, type LucideIcon } from 'lucide-react';
import { listAuditLogs, type AuditLogEntry } from '../../api/auditLogs';
import { listTeachers } from '../../api/teachers';
import type { Teacher } from '../../types';
import { useShellNotifications } from '../NotificationsContext';
import { ListSkeleton } from '../ui/Skeleton';
import { Avatar } from './Avatar';
import { buildAdminNotices, buildParentNotices, type RailNotice } from './railData';
import { humanizeAction, timeAgo } from './format';

const TONE: Record<RailNotice['tone'], string> = {
  green: 'bg-green-100 text-green',
  amber: 'bg-amber-100 text-amber',
  coral: 'bg-coral-100 text-coral',
};

export function RailSection({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section>
      <div className="flex items-center justify-between gap-3 mb-3">
        <h2 className="font-display text-lg text-ink-900">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function NoticeList({ notices, emptyText }: { notices: RailNotice[]; emptyText: string }) {
  if (notices.length === 0) {
    return (
      <div className="flex items-center gap-3 rounded-xl bg-dx border border-white/[0.06] px-4 py-3.5">
        <span className="w-9 h-9 rounded-full bg-white/[0.06] text-ink-600 flex items-center justify-center shrink-0">
          <Bell className="w-4 h-4" strokeWidth={1.75} />
        </span>
        <p className="text-sm text-ink-600">{emptyText}</p>
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-1">
      {notices.map((n) => {
        const Icon = n.icon;
        const body = (
          <>
            <span className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${TONE[n.tone]}`}>
              <Icon className="w-4 h-4" strokeWidth={2} />
            </span>
            <span className="min-w-0">
              <span className="block text-sm text-ink-900 leading-snug">{n.title}</span>
              <span className="block text-xs text-ink-400 mt-0.5">{n.hint}</span>
            </span>
          </>
        );
        return (
          <li key={n.key}>
            {n.to ? (
              <Link to={n.to} className="flex items-center gap-3 rounded-xl px-2 py-2 hover:bg-white/[0.05] transition-colors">
                {body}
              </Link>
            ) : (
              <div className="flex items-center gap-3 px-2 py-2">{body}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** One person (or shortcut) as a row; the active row turns lime with its quick actions, like a selected contact. */
function ContactRow({
  name,
  sub,
  active,
  onSelect,
  actions,
  avatar,
}: {
  name: string;
  sub: string;
  active: boolean;
  onSelect: () => void;
  actions?: ReactNode;
  avatar?: ReactNode;
}) {
  return (
    <li
      className={`flex items-center gap-1 rounded-full pr-2 transition-colors ${
        active ? 'bg-lime text-[#0B1203]' : 'hover:bg-white/[0.05] text-ink-900'
      }`}
    >
      <button onClick={onSelect} aria-pressed={active} className="flex flex-1 min-w-0 items-center gap-3 p-2 text-left rounded-full">
        {avatar}
        <span className="min-w-0">
          <span className="block text-sm font-medium truncate">{name}</span>
          <span className={`block text-[11px] truncate ${active ? 'text-[#0B1203]/65' : 'text-ink-400'}`}>{sub}</span>
        </span>
      </button>
      {active && actions}
    </li>
  );
}

function ActionLink({ href, label, children }: { href: string; label: string; children: ReactNode }) {
  return (
    <a
      href={href}
      aria-label={label}
      className="w-8 h-8 rounded-full bg-[#0B1203] text-lime flex items-center justify-center hover:brightness-125 transition"
    >
      {children}
    </a>
  );
}

function AdminActivities() {
  const [rows, setRows] = useState<AuditLogEntry[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listAuditLogs(1, 5)
      .then((p) => !cancelled && setRows(p.items))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) return <p className="text-sm text-ink-600">Couldn't load recent activity.</p>;
  if (!rows) return <ListSkeleton rows={3} />;
  if (rows.length === 0) return <p className="text-sm text-ink-600">Nothing has happened yet.</p>;

  return (
    <ol className="relative flex flex-col gap-4">
      <span className="absolute left-[17px] top-3 bottom-3 w-px bg-white/10" aria-hidden="true" />
      {rows.map((e) => (
        <li key={e.id} className="relative flex items-center gap-3">
          <Avatar name={e.actor_name || '?'} size={36} className="ring-4 ring-bg" />
          <div className="min-w-0">
            <p className="text-sm text-ink-900 truncate">{humanizeAction(e.action)}</p>
            <p className="text-xs text-ink-400 truncate">
              {e.actor_name} · {timeAgo(e.created_at)}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function TeacherContacts() {
  const [teachers, setTeachers] = useState<Teacher[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listTeachers()
      .then((t) => !cancelled && setTeachers(t.filter((x) => x.is_active)))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) return <p className="text-sm text-ink-600">Couldn't load contacts.</p>;
  if (!teachers) return <ListSkeleton rows={3} />;
  if (teachers.length === 0) {
    return (
      <p className="text-sm text-ink-600">
        No teachers yet.{' '}
        <Link to="/teachers" className="text-lime hover:underline">
          Add one
        </Link>
      </p>
    );
  }

  const shown = teachers.slice(0, 5);
  const fallback = shown.find((t) => t.email || t.phone)?.id ?? null;
  const activeId = selected ?? fallback;

  return (
    <ul className="flex flex-col gap-1">
      {shown.map((t) => (
        <ContactRow
          key={t.id}
          name={t.full_name}
          sub={t.class_names.length > 0 ? t.class_names.join(', ') : 'Teacher'}
          avatar={<Avatar name={t.full_name} size={36} />}
          active={t.id === activeId}
          onSelect={() => setSelected(t.id === selected ? null : t.id)}
          actions={
            <span className="flex items-center gap-1.5">
              {t.email && (
                <ActionLink href={`mailto:${t.email}`} label={`Email ${t.full_name}`}>
                  <Mail className="w-3.5 h-3.5" strokeWidth={2} />
                </ActionLink>
              )}
              {t.phone && (
                <ActionLink href={`tel:${t.phone}`} label={`Call ${t.full_name}`}>
                  <Phone className="w-3.5 h-3.5" strokeWidth={2} />
                </ActionLink>
              )}
            </span>
          }
        />
      ))}
    </ul>
  );
}

/** Right-hand column of the admin/bursar dashboard: what needs attention, what just happened, who to reach. */
export function AdminRail({ overdueCount, flaggedCount }: { overdueCount: number; flaggedCount: number }) {
  const notif = useShellNotifications();
  const notices = buildAdminNotices({
    unreadMessages: notif?.unreadMessages ?? 0,
    unreadClassGroups: notif?.unreadClassGroups ?? 0,
    mentions: notif?.mentions ?? [],
    flagged: flaggedCount,
    overdue: overdueCount,
  });

  return (
    <div className="flex flex-col gap-8">
      <RailSection title="Notifications">
        <NoticeList notices={notices} emptyText="You're all caught up." />
      </RailSection>
      <RailSection title="Activities">
        <AdminActivities />
      </RailSection>
      <RailSection
        title="School contacts"
        action={
          <Link to="/teachers" className="text-xs text-ink-600 hover:text-lime transition-colors">
            All teachers
          </Link>
        }
      >
        <TeacherContacts />
      </RailSection>
    </div>
  );
}

const PARENT_SHORTCUTS: { to: string; name: string; sub: string; icon: LucideIcon }[] = [
  { to: '/parent/dashboard#messages', name: 'School office', sub: 'Message the bursar', icon: MessageCircle },
  { to: '/parent/chats', name: 'Teacher chats', sub: 'Talk to your child’s teacher', icon: MessagesSquare },
  { to: '/parent/class-group', name: 'Class group', sub: 'Updates from the class', icon: Users2 },
  { to: '/parent/assistant', name: 'Ask Ledgr', sub: 'Questions about fees', icon: Sparkles },
];

/** One shortcut: the whole row is a link, so a single tap goes there. The lime highlight just follows hover/focus. */
function ShortcutRow({ to, name, sub, icon: Icon, hot, onHot }: { to: string; name: string; sub: string; icon: LucideIcon; hot: boolean; onHot: () => void }) {
  return (
    <li>
      <Link
        to={to}
        onMouseEnter={onHot}
        onFocus={onHot}
        className={`flex items-center gap-3 rounded-full p-2 pr-4 transition-colors ${hot ? 'bg-lime text-[#0B1203]' : 'text-ink-900 hover:bg-white/[0.05]'}`}
      >
        <span className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${hot ? 'bg-[#0B1203] text-lime' : 'bg-white/[0.06] text-ink-600'}`}>
          <Icon className="w-4 h-4" strokeWidth={2} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium truncate">{name}</span>
          <span className={`block text-[11px] truncate ${hot ? 'text-[#0B1203]/65' : 'text-ink-400'}`}>{sub}</span>
        </span>
        <ChevronRight className={`w-4 h-4 shrink-0 ${hot ? 'opacity-80' : 'opacity-40'}`} strokeWidth={2} />
      </Link>
    </li>
  );
}

/** The parent's version: unread things, then quick ways to reach the school. Recent payments are passed in as `activity`. */
export function ParentRail({ activity }: { activity?: ReactNode }) {
  const notif = useShellNotifications();
  const [hot, setHot] = useState(PARENT_SHORTCUTS[0].to);
  const notices = buildParentNotices({
    unreadMessages: notif?.unreadMessages ?? 0,
    unreadClassGroups: notif?.unreadClassGroups ?? 0,
    unreadDirect: notif?.unreadDirect ?? 0,
    mentions: notif?.mentions ?? [],
  });

  return (
    <div className="flex flex-col gap-8">
      <RailSection title="Notifications">
        <NoticeList notices={notices} emptyText="Nothing new right now." />
      </RailSection>
      {activity}
      <RailSection title="Get in touch">
        <ul className="flex flex-col gap-1">
          {PARENT_SHORTCUTS.map((s) => (
            <ShortcutRow key={s.to} {...s} hot={s.to === hot} onHot={() => setHot(s.to)} />
          ))}
        </ul>
      </RailSection>
    </div>
  );
}
