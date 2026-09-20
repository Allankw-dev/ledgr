import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AtSign, ChevronDown, Download, FileText, Image as ImageIcon, Paperclip, Send, Users, X } from 'lucide-react';
import {
  listClassGroups,
  listClassGroupMessages,
  listClassGroupMembers,
  sendClassGroupMessage,
  sendClassGroupFile,
  getAttachmentUrl,
  getMessageReceipts,
} from '../api/classGroups';
import { useAuthStore } from '../store/authStore';
import { usePolling } from '../hooks/usePolling';
import { MessageTicks } from './MessageTicks';
import type {
  AttachmentUrl,
  ChatAttachment,
  ClassGroupMessage,
  ClassGroupSummary,
  GroupMember,
  MessageReceipt,
} from '../types';

const MAX_FILE_MB = 10;
const POLL_THREAD_MS = 4000;
const POLL_GROUPS_MS = 15000;

const roleLabel: Record<string, string> = {
  SCHOOL_ADMIN: 'School office',
  BURSAR: "Bursar's office",
  TEACHER: 'Teacher',
  PARENT: 'Parent',
};

// Each sender gets a stable colour, like WhatsApp groups, so a long thread is easy to scan.
const NAME_COLORS = ['#39FF88', '#3FD9FF', '#B39DFF', '#FFC24B', '#FF8A5C', '#FF7AB6', '#7CE8C0', '#6FB1FF'];
function nameColor(id: string) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return NAME_COLORS[h % NAME_COLORS.length];
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('');
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en-KE', { hour: 'numeric', minute: '2-digit' });
}

function formatPreviewTime(iso: string) {
  const d = new Date(iso);
  return d.toDateString() === new Date().toDateString()
    ? formatTime(iso)
    : d.toLocaleDateString('en-KE', { day: 'numeric', month: 'short' });
}

function dayLabel(iso: string) {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString('en-KE', { weekday: 'long', day: 'numeric', month: 'long' });
}

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Renders message text with @mentions highlighted. */
function renderBody(body: string, names: string[]) {
  const tokens = [...names.map((n) => '@' + n), '@everyone'].sort((a, b) => b.length - a.length);
  if (!body) return null;
  const re = new RegExp(`(${tokens.map(escapeRegExp).join('|')})`, 'gi');
  return body.split(re).map((part, i) =>
    tokens.some((t) => t.toLowerCase() === part.toLowerCase()) ? (
      <span key={i} className="text-cyan font-medium bg-cyan/10 rounded px-0.5">
        {part}
      </span>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

// Short-lived signed links, cached so a 4-second poll doesn't re-request (and re-flash) every image.
const urlCache = new Map<string, { exp: number; data: AttachmentUrl }>();

function AttachmentView({ classId, messageId, attachment }: { classId: string; messageId: string; attachment: ChatAttachment }) {
  const [data, setData] = useState<AttachmentUrl | null>(() => {
    const hit = urlCache.get(messageId);
    return hit && hit.exp > Date.now() ? hit.data : null;
  });
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await getAttachmentUrl(classId, messageId);
      urlCache.set(messageId, { exp: Date.now() + (d.expires_in - 60) * 1000, data: d });
      setData(d);
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, [classId, messageId]);

  useEffect(() => {
    if (!data) void load();
  }, [data, load]);

  if (attachment.is_image) {
    return (
      <div className="mb-1.5">
        {data ? (
          <a href={data.url} target="_blank" rel="noopener noreferrer">
            <img
              src={data.url}
              alt={attachment.name}
              loading="lazy"
              onError={() => {
                urlCache.delete(messageId);
                setData(null);
              }}
              className="rounded-md max-h-64 max-w-full object-cover"
            />
          </a>
        ) : (
          <div className="w-52 h-36 rounded-md bg-ink-800 animate-pulse flex items-center justify-center text-ink-400">
            <ImageIcon className="w-6 h-6" strokeWidth={1.5} />
          </div>
        )}
      </div>
    );
  }

  return (
    <a
      href={data?.url}
      target="_blank"
      rel="noopener noreferrer"
      download={attachment.name}
      onClick={(e) => {
        if (!data) {
          e.preventDefault();
          void load();
        }
      }}
      className="flex items-center gap-3 rounded-md bg-black/25 border border-ink-200 px-3 py-2.5 mb-1.5 hover:bg-black/40 transition-colors"
    >
      <div className="w-9 h-9 rounded-md bg-violet/20 text-violet flex items-center justify-center shrink-0">
        <FileText className="w-5 h-5" strokeWidth={1.75} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-ink-900 truncate">{attachment.name}</p>
        <p className="text-[11px] text-ink-400">{failed ? 'Could not load — tap to retry' : formatBytes(attachment.size)}</p>
      </div>
      <Download className="w-4 h-4 text-ink-600 shrink-0" strokeWidth={2} />
    </a>
  );
}

function detectMention(text: string, caret: number) {
  const before = text.slice(0, caret);
  const m = /(^|\s)@([^\s@]*(?: [^\s@]*){0,2})$/.exec(before);
  if (!m) return null;
  return { start: before.length - m[2].length - 1, query: m[2] };
}

export function ClassGroupChat() {
  const user = useAuthStore((s) => s.user);
  const [searchParams] = useSearchParams();
  const [groups, setGroups] = useState<ClassGroupSummary[]>([]);
  const [groupsLoaded, setGroupsLoaded] = useState(false);
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ClassGroupMessage[]>([]);
  const [members, setMembers] = useState<GroupMember[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [input, setInput] = useState('');
  const [caret, setCaret] = useState(0);
  const [pickerIndex, setPickerIndex] = useState(0);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingPreview, setPendingPreview] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showJump, setShowJump] = useState(false);
  const [infoFor, setInfoFor] = useState<ClassGroupMessage | null>(null);
  const [receipts, setReceipts] = useState<MessageReceipt[] | null>(null);

  const mentionMap = useRef<Map<string, string>>(new Map()); // "Name" -> user id
  const listRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const photoInputRef = useRef<HTMLInputElement>(null);
  const stickToBottom = useRef(true);
  const lastSig = useRef('');
  const canMentionAll = user?.role !== 'PARENT';

  // ---------- groups ----------
  const loadGroups = useCallback(async () => {
    try {
      const data = await listClassGroups();
      setGroups(data);
      setSelectedClassId((cur) => {
        if (cur) return cur;
        const wanted = searchParams.get('class');
        if (wanted && data.some((g) => g.class_id === wanted)) return wanted;
        return data[0]?.class_id ?? null;
      });
    } catch {
      setError('Could not load your class groups.');
    } finally {
      setGroupsLoaded(true);
    }
  }, [searchParams]);

  useEffect(() => {
    void loadGroups();
  }, [loadGroups]);
  usePolling(loadGroups, POLL_GROUPS_MS);

  // ---------- thread ----------
  const signature = (list: ClassGroupMessage[]) =>
    list.map((m) => `${m.id}:${m.status ?? ''}:${m.delivered_count ?? ''}:${m.read_count ?? ''}`).join('|');

  const refreshThread = useCallback(async () => {
    if (!selectedClassId) return;
    const data = await listClassGroupMessages(selectedClassId);
    const sig = signature(data);
    if (sig !== lastSig.current) {
      lastSig.current = sig;
      setMessages(data);
      if (!stickToBottom.current) setShowJump(true);
    }
  }, [selectedClassId]);

  useEffect(() => {
    if (!selectedClassId) return;
    setLoadingMessages(true);
    setMessages([]);
    lastSig.current = '';
    stickToBottom.current = true;
    setShowJump(false);
    mentionMap.current = new Map();
    setInput('');
    setPendingFile(null);
    Promise.all([listClassGroupMessages(selectedClassId), listClassGroupMembers(selectedClassId).catch(() => [])])
      .then(([msgs, mems]) => {
        lastSig.current = signature(msgs);
        setMessages(msgs);
        setMembers(mems);
        // Opening the thread marked it read — clear the unread badge right away.
        setGroups((prev) => prev.map((g) => (g.class_id === selectedClassId ? { ...g, unread_count: 0, unread_mentions: 0 } : g)));
      })
      .catch(() => setError('Could not load this conversation.'))
      .finally(() => setLoadingMessages(false));
  }, [selectedClassId]);

  // While the chat is open, refresh it every few seconds (paused in hidden tabs) — this is
  // also what turns senders' ticks blue when you're looking at their message.
  usePolling(refreshThread, POLL_THREAD_MS, !!selectedClassId);

  useEffect(() => {
    if (stickToBottom.current) endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  function onScroll() {
    const el = listRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    stickToBottom.current = nearBottom;
    if (nearBottom) setShowJump(false);
  }

  function jumpToBottom() {
    stickToBottom.current = true;
    setShowJump(false);
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }

  // ---------- attachments ----------
  useEffect(() => {
    if (pendingFile && pendingFile.type.startsWith('image/')) {
      const url = URL.createObjectURL(pendingFile);
      setPendingPreview(url);
      return () => URL.revokeObjectURL(url);
    }
    setPendingPreview(null);
  }, [pendingFile]);

  function pickFile(file: File | undefined) {
    if (!file) return;
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      setError(`That file is too large. The limit is ${MAX_FILE_MB} MB.`);
      return;
    }
    setError(null);
    setPendingFile(file);
    inputRef.current?.focus();
  }

  // ---------- @mentions ----------
  const mention = useMemo(() => detectMention(input, caret), [input, caret]);
  const pickerOptions = useMemo(() => {
    if (!mention) return [];
    const q = mention.query.toLowerCase();
    const opts: { id: string; name: string; subtitle: string; all?: boolean }[] = [];
    if (canMentionAll && 'everyone'.startsWith(q)) {
      opts.push({ id: '__all__', name: 'everyone', subtitle: 'Notify everyone in this group', all: true });
    }
    members
      .filter((m) => m.name.toLowerCase().includes(q))
      .slice(0, 6)
      .forEach((m) => opts.push({ id: m.user_id, name: m.name, subtitle: m.subtitle || roleLabel[m.role] || '' }));
    return opts;
  }, [mention, members, canMentionAll]);

  useEffect(() => setPickerIndex(0), [mention?.query]);

  function chooseMention(opt: { id: string; name: string; all?: boolean }) {
    if (!mention) return;
    const before = input.slice(0, mention.start);
    const after = input.slice(caret);
    const inserted = `@${opt.name} `;
    const next = before + inserted + after;
    if (!opt.all) mentionMap.current.set(opt.name, opt.id);
    setInput(next);
    const pos = (before + inserted).length;
    setCaret(pos);
    requestAnimationFrame(() => {
      inputRef.current?.focus();
      inputRef.current?.setSelectionRange(pos, pos);
    });
  }

  function startMention() {
    const el = inputRef.current;
    const pos = el?.selectionStart ?? input.length;
    const needsSpace = pos > 0 && !/\s/.test(input[pos - 1]);
    const next = input.slice(0, pos) + (needsSpace ? ' @' : '@') + input.slice(pos);
    setInput(next);
    const newPos = pos + (needsSpace ? 2 : 1);
    setCaret(newPos);
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(newPos, newPos);
    });
  }

  // ---------- send ----------
  async function handleSend() {
    const text = input.trim();
    if ((!text && !pendingFile) || sending || !selectedClassId) return;

    const mentionUserIds = [...mentionMap.current.entries()].filter(([name]) => text.includes('@' + name)).map(([, id]) => id);
    const mentionAll = canMentionAll && /(^|\s)@everyone\b/i.test(text);

    setSending(true);
    setError(null);
    try {
      const sent = pendingFile
        ? await sendClassGroupFile(selectedClassId, pendingFile, text, { mentionUserIds, mentionAll })
        : await sendClassGroupMessage(selectedClassId, text, { mentionUserIds, mentionAll });
      stickToBottom.current = true;
      setMessages((prev) => {
        const next = [...prev, sent];
        lastSig.current = signature(next);
        return next;
      });
      setInput('');
      setPendingFile(null);
      mentionMap.current = new Map();
      setGroups((prev) =>
        prev.map((g) =>
          g.class_id === selectedClassId
            ? {
                ...g,
                last_message_preview: (text || (sent.attachment?.is_image ? '📷 Photo' : `📎 ${sent.attachment?.name ?? 'File'}`)).slice(0, 120),
                last_message_at: sent.created_at,
              }
            : g
        )
      );
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Could not send that message. Try again in a moment.');
    } finally {
      setSending(false);
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (mention && pickerOptions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setPickerIndex((i) => (i + 1) % pickerOptions.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setPickerIndex((i) => (i - 1 + pickerOptions.length) % pickerOptions.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        chooseMention(pickerOptions[pickerIndex]);
        return;
      }
      if (e.key === 'Escape') {
        setCaret(0);
        return;
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }

  // ---------- message info ----------
  async function openInfo(m: ClassGroupMessage) {
    if (!selectedClassId) return;
    setInfoFor(m);
    setReceipts(null);
    try {
      setReceipts(await getMessageReceipts(selectedClassId, m.id));
    } catch {
      setReceipts([]);
    }
  }

  const selectedGroup = groups.find((g) => g.class_id === selectedClassId);
  const canSeeInfo = (m: ClassGroupMessage) => m.sender_user_id === user?.id || (user?.role !== 'PARENT' && user?.role !== 'TEACHER');

  if (groupsLoaded && groups.length === 0) {
    return (
      <div className="bg-panel border border-ink-200 rounded-lg px-6 py-16 text-center">
        <Users className="w-8 h-8 text-ink-400 mx-auto mb-3" strokeWidth={1.5} />
        <p className="text-sm text-ink-900 font-medium">No class groups yet</p>
        <p className="text-xs text-ink-600 mt-1">
          {user?.role === 'TEACHER'
            ? "You'll see a group for each grade you're assigned to. Ask the school admin to assign you to your grade(s) under Teachers."
            : user?.role === 'PARENT'
              ? "You'll see your child's grade group here once the school has approved your link to them."
              : 'Groups appear once grades exist and students are added to them.'}
        </p>
      </div>
    );
  }

  let lastDay = '';

  return (
    <div className="bg-panel border border-ink-200 rounded-xl overflow-hidden grid grid-cols-1 md:grid-cols-[280px_1fr] h-[calc(100vh-12rem)] min-h-[480px] max-h-[760px] shadow-xl shadow-black/20">
      {/* Group list */}
      <div className="border-b md:border-b-0 md:border-r border-ink-200 overflow-y-auto max-h-32 md:max-h-none shrink-0 md:shrink bg-ink-950/40">
        {groups.map((g) => {
          const active = g.class_id === selectedClassId;
          return (
            <button
              key={g.class_id}
              onClick={() => setSelectedClassId(g.class_id)}
              className={`w-full text-left px-4 py-3.5 border-b border-ink-100 transition-colors ${
                active ? 'bg-gradient-to-r from-emerald-100 to-transparent border-l-2 border-l-emerald-700' : 'hover:bg-ink-100/60'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium text-ink-900 truncate">{g.class_name}</p>
                {g.last_message_at && (
                  <span className={`text-[11px] shrink-0 ${g.unread_count ? 'text-emerald-700' : 'text-ink-400'}`}>
                    {formatPreviewTime(g.last_message_at)}
                  </span>
                )}
              </div>
              <div className="flex items-center justify-between gap-2 mt-0.5">
                <p className="text-xs text-ink-600 truncate">{g.last_message_preview || 'No messages yet'}</p>
                <span className="flex items-center gap-1 shrink-0">
                  {!!g.unread_mentions && (
                    <span className="w-5 h-5 rounded-full bg-amber text-[#06110B] flex items-center justify-center" title="You were mentioned">
                      <AtSign className="w-3 h-3" strokeWidth={3} />
                    </span>
                  )}
                  {!!g.unread_count && !active && (
                    <span className="min-w-[20px] h-5 px-1.5 rounded-full bg-green text-[#06110B] text-[11px] font-bold flex items-center justify-center">
                      {g.unread_count > 99 ? '99+' : g.unread_count}
                    </span>
                  )}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Thread */}
      <div className="flex flex-col min-h-0 min-w-0">
        <div className="px-5 py-3.5 border-b border-ink-200 flex items-center gap-3 bg-gradient-to-r from-ink-100 to-panel">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center shrink-0 shadow-lg shadow-emerald-700/20">
            <Users className="w-5 h-5 text-[#06110B]" strokeWidth={2} />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink-900 truncate">
              {selectedGroup ? `${selectedGroup.class_name} Group` : 'Select a group'}
            </p>
            <p className="text-xs text-ink-400 truncate">
              {members.length > 0 ? `${members.length + 1} members · ` : ''}Parents, teachers and the school office
            </p>
          </div>
        </div>

        <div className="relative flex-1 min-h-0">
          <div ref={listRef} onScroll={onScroll} className="chat-wallpaper absolute inset-0 overflow-y-auto px-4 sm:px-6 py-4 flex flex-col gap-1.5">
            {loadingMessages ? (
              <p className="text-sm text-ink-600 m-auto">Loading…</p>
            ) : messages.length === 0 ? (
              <div className="m-auto text-center max-w-xs bg-panel/80 border border-ink-200 rounded-lg px-5 py-6">
                <p className="text-sm text-ink-900 font-medium">No messages yet</p>
                <p className="text-xs text-ink-600 mt-1">Say hello to start the conversation for this class.</p>
              </div>
            ) : (
              messages.map((m) => {
                const isMine = m.sender_user_id === user?.id;
                const day = dayLabel(m.created_at);
                const showDay = day !== lastDay;
                lastDay = day;
                const color = nameColor(m.sender_user_id);
                const names = (m.mentions ?? []).map((x) => x.name);
                return (
                  <div key={m.id} className="msg-in">
                    {showDay && (
                      <div className="flex justify-center my-3">
                        <span className="text-[11px] text-ink-600 bg-panel/90 border border-ink-200 rounded-full px-3 py-1">{day}</span>
                      </div>
                    )}
                    <div className={`flex ${isMine ? 'justify-end' : 'justify-start'} gap-2`}>
                      {!isMine && (
                        <div
                          className="w-8 h-8 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0 mt-0.5 text-[#06110B]"
                          style={{ background: color }}
                          aria-hidden="true"
                        >
                          {initials(m.sender_name)}
                        </div>
                      )}
                      <div
                        className={`max-w-[80%] sm:max-w-[70%] rounded-2xl px-3.5 py-2 text-sm shadow-md shadow-black/20 ${
                          isMine
                            ? 'bg-green-100 border border-green-200 rounded-tr-md text-ink-900'
                            : 'bg-ink-100 border border-ink-200 rounded-tl-md text-ink-900'
                        } ${m.mentions_me ? 'ring-1 ring-amber/60' : ''}`}
                      >
                        {!isMine && (
                          <p className="text-xs font-semibold mb-0.5 flex flex-wrap items-baseline gap-x-1.5" style={{ color }}>
                            {m.sender_name}
                            <span className="text-ink-400 font-normal text-[11px]">
                              {m.sender_subtitle || roleLabel[m.sender_role] || m.sender_role}
                            </span>
                          </p>
                        )}
                        {m.mentions_me && (
                          <p className="text-[10px] uppercase tracking-wide text-amber font-semibold mb-1 flex items-center gap-1">
                            <AtSign className="w-3 h-3" strokeWidth={3} /> Mentioned you
                          </p>
                        )}
                        {m.attachment && selectedClassId && (
                          <AttachmentView classId={selectedClassId} messageId={m.id} attachment={m.attachment} />
                        )}
                        {m.body && <p className="whitespace-pre-wrap break-words">{renderBody(m.body, names)}</p>}
                        <div className="flex items-center justify-end gap-1.5 mt-1 text-ink-400">
                          <span className="text-[10px]">{formatTime(m.created_at)}</span>
                          {isMine && m.status && (
                            canSeeInfo(m) ? (
                              <button
                                type="button"
                                onClick={() => openInfo(m)}
                                title={
                                  m.recipient_count
                                    ? `Read by ${m.read_count ?? 0} of ${m.recipient_count} · tap for details`
                                    : 'Tap for details'
                                }
                                className="hover:opacity-80"
                              >
                                <MessageTicks status={m.status} />
                              </button>
                            ) : (
                              <MessageTicks status={m.status} />
                            )
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
            <div ref={endRef} />
          </div>

          {showJump && (
            <button
              onClick={jumpToBottom}
              className="absolute bottom-3 right-4 flex items-center gap-1.5 rounded-full bg-green text-[#06110B] text-xs font-semibold px-3 py-1.5 shadow-lg"
            >
              <ChevronDown className="w-3.5 h-3.5" strokeWidth={3} /> New messages
            </button>
          )}
        </div>

        {/* Composer */}
        <div className="relative border-t border-ink-200 bg-panel px-3 sm:px-4 py-3">
          {mention && pickerOptions.length > 0 && (
            <div className="absolute bottom-full left-3 right-3 sm:left-4 sm:right-auto sm:w-80 mb-2 rounded-lg border border-ink-200 bg-panel shadow-2xl overflow-hidden z-20">
              <p className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-wide text-ink-400">Mention someone</p>
              {pickerOptions.map((opt, i) => (
                <button
                  key={opt.id}
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    chooseMention(opt);
                  }}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 text-left ${i === pickerIndex ? 'bg-ink-100' : 'hover:bg-ink-100/60'}`}
                >
                  <span
                    className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold text-[#06110B] shrink-0"
                    style={{ background: opt.all ? '#FFC24B' : nameColor(opt.id) }}
                  >
                    {opt.all ? '@' : initials(opt.name)}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm text-ink-900 truncate">{opt.all ? '@everyone' : opt.name}</span>
                    <span className="block text-[11px] text-ink-400 truncate">{opt.subtitle}</span>
                  </span>
                </button>
              ))}
            </div>
          )}

          {pendingFile && (
            <div className="flex items-center gap-3 mb-2 rounded-lg border border-ink-200 bg-ink-100 px-3 py-2">
              {pendingPreview ? (
                <img src={pendingPreview} alt="" className="w-12 h-12 rounded-md object-cover" />
              ) : (
                <div className="w-12 h-12 rounded-md bg-violet/20 text-violet flex items-center justify-center">
                  <FileText className="w-6 h-6" strokeWidth={1.75} />
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="text-sm text-ink-900 truncate">{pendingFile.name}</p>
                <p className="text-[11px] text-ink-400">{formatBytes(pendingFile.size)} · add a caption below if you like</p>
              </div>
              <button type="button" onClick={() => setPendingFile(null)} aria-label="Remove attachment" className="text-ink-400 hover:text-ink-900">
                <X className="w-4 h-4" strokeWidth={2} />
              </button>
            </div>
          )}

          {error && <p className="text-xs text-clay-700 mb-2">{error}</p>}

          <div className="flex items-end gap-1.5">
            <input
              ref={photoInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              className="hidden"
              onChange={(e) => {
                pickFile(e.target.files?.[0]);
                e.target.value = '';
              }}
            />
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv"
              className="hidden"
              onChange={(e) => {
                pickFile(e.target.files?.[0]);
                e.target.value = '';
              }}
            />
            <button type="button" onClick={() => photoInputRef.current?.click()} disabled={!selectedClassId} aria-label="Attach a photo" title="Photo" className="p-2.5 rounded-full text-ink-600 hover:text-ink-900 hover:bg-ink-100 disabled:opacity-40">
              <ImageIcon className="w-5 h-5" strokeWidth={1.75} />
            </button>
            <button type="button" onClick={() => fileInputRef.current?.click()} disabled={!selectedClassId} aria-label="Attach a file" title="File" className="p-2.5 rounded-full text-ink-600 hover:text-ink-900 hover:bg-ink-100 disabled:opacity-40">
              <Paperclip className="w-5 h-5" strokeWidth={1.75} />
            </button>
            <button type="button" onClick={startMention} disabled={!selectedClassId} aria-label="Mention someone" title="Mention (@)" className="p-2.5 rounded-full text-ink-600 hover:text-ink-900 hover:bg-ink-100 disabled:opacity-40">
              <AtSign className="w-5 h-5" strokeWidth={1.75} />
            </button>

            <textarea
              ref={inputRef}
              rows={1}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                setCaret(e.target.selectionStart);
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
              }}
              onKeyUp={(e) => setCaret((e.target as HTMLTextAreaElement).selectionStart)}
              onClick={(e) => setCaret((e.target as HTMLTextAreaElement).selectionStart)}
              onKeyDown={onKeyDown}
              placeholder={selectedClassId ? 'Type a message… use @ to mention someone' : 'Select a group first'}
              disabled={!selectedClassId || sending}
              className="flex-1 resize-none px-4 py-2.5 rounded-2xl border border-ink-200 text-sm bg-ink-100 text-ink-900 placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-emerald-700/30 max-h-[120px]"
            />
            <button
              type="button"
              onClick={() => void handleSend()}
              disabled={sending || (!input.trim() && !pendingFile) || !selectedClassId}
              className="p-3 rounded-full bg-gradient-to-br from-emerald-700 to-cyan text-[#06110B] hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-emerald-700/20"
              aria-label="Send"
            >
              <Send className="w-4.5 h-4.5" strokeWidth={2.25} />
            </button>
          </div>
        </div>
      </div>

      {/* Message info */}
      {infoFor && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-ink-950/60" onClick={() => setInfoFor(null)}>
          <div className="w-full max-w-sm rounded-xl border border-ink-200 bg-panel shadow-2xl max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-ink-200">
              <p className="text-sm font-medium text-ink-900">Message info</p>
              <button onClick={() => setInfoFor(null)} aria-label="Close" className="text-ink-400 hover:text-ink-900">
                <X className="w-4 h-4" strokeWidth={2} />
              </button>
            </div>
            <div className="overflow-y-auto p-2">
              {receipts === null ? (
                <p className="text-xs text-ink-600 p-4">Loading…</p>
              ) : receipts.length === 0 ? (
                <p className="text-xs text-ink-600 p-4">Nobody else is in this group yet.</p>
              ) : (
                (['read', 'delivered', 'pending'] as const).map((bucket) => {
                  const people = receipts.filter((r) => (bucket === 'read' ? r.read : bucket === 'delivered' ? !r.read && r.delivered : !r.delivered));
                  if (people.length === 0) return null;
                  return (
                    <div key={bucket} className="mb-2">
                      <p className="px-3 py-1.5 text-[11px] uppercase tracking-wide text-ink-400 flex items-center gap-1.5">
                        {bucket === 'read' && <MessageTicks status="read" />}
                        {bucket === 'delivered' && <MessageTicks status="delivered" />}
                        {bucket === 'pending' && <MessageTicks status="sent" />}
                        {bucket === 'read' ? 'Read by' : bucket === 'delivered' ? 'Delivered to' : 'Not delivered yet'} ({people.length})
                      </p>
                      {people.map((r) => (
                        <div key={r.user_id} className="flex items-center gap-2.5 px-3 py-1.5">
                          <span className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold text-[#06110B]" style={{ background: nameColor(r.user_id) }}>
                            {initials(r.name)}
                          </span>
                          <span className="min-w-0">
                            <span className="block text-sm text-ink-900 truncate">{r.name}</span>
                            <span className="block text-[11px] text-ink-400 truncate">{r.subtitle || roleLabel[r.role]}</span>
                          </span>
                        </div>
                      ))}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
