import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ArrowLeft, Lock, MessageSquarePlus, Search, Send, X } from 'lucide-react';
import {
  listDirectContacts,
  listDirectConversations,
  listDirectMessages,
  sendDirectMessage,
  startDirectConversation,
} from '../api/direct';
import { getErrorMessage } from '../api/client';
import { useAuthStore } from '../store/authStore';
import { usePolling } from '../hooks/usePolling';
import { MessageTicks } from './MessageTicks';
import type { DirectContact, DirectConversation, DirectMessage } from '../types';

const POLL_THREAD_MS = 4000;
const POLL_LIST_MS = 15000;

const NAME_COLORS = ['#39FF88', '#3FD9FF', '#B39DFF', '#FFC24B', '#FF8A5C', '#FF7AB6', '#7CE8C0', '#6FB1FF'];
function colorFor(id: string) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return NAME_COLORS[h % NAME_COLORS.length];
}
function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join('');
}
function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en-KE', { hour: 'numeric', minute: '2-digit' });
}
function formatListTime(iso: string) {
  const d = new Date(iso);
  return d.toDateString() === new Date().toDateString()
    ? formatTime(iso)
    : d.toLocaleDateString('en-KE', { day: 'numeric', month: 'short' });
}
function dayLabel(iso: string) {
  const d = new Date(iso);
  const y = new Date();
  y.setDate(y.getDate() - 1);
  if (d.toDateString() === new Date().toDateString()) return 'Today';
  if (d.toDateString() === y.toDateString()) return 'Yesterday';
  return d.toLocaleDateString('en-KE', { weekday: 'long', day: 'numeric', month: 'long' });
}

function Avatar({ id, name, size = 40 }: { id: string; name: string; size?: number }) {
  return (
    <span
      className="rounded-full flex items-center justify-center font-bold text-[#06110B] shrink-0"
      style={{ background: colorFor(id), width: size, height: size, fontSize: size * 0.34 }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  );
}

/**
 * Private one-to-one chat between a teacher and a parent. Pick someone from
 * "New chat" (a teacher sees the parents of their grades; a parent sees their
 * child's teachers). Only the two participants can read a conversation; the
 * messages are encrypted in transit and stored encrypted.
 */
export function DirectChat() {
  const user = useAuthStore((s) => s.user);
  const [searchParams] = useSearchParams();
  const [conversations, setConversations] = useState<DirectConversation[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DirectMessage[]>([]);
  const [loadingThread, setLoadingThread] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [contacts, setContacts] = useState<DirectContact[] | null>(null);
  const [query, setQuery] = useState('');
  const [starting, setStarting] = useState<string | null>(null);

  const endRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const lastSig = useRef('');
  const isTeacher = user?.role === 'TEACHER';
  const selected = conversations.find((c) => c.id === selectedId) ?? null;

  const loadConversations = useCallback(async () => {
    try {
      const data = await listDirectConversations();
      setConversations(data);
      setSelectedId((cur) => cur ?? null);
    } catch {
      setError('Could not load your chats.');
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void loadConversations();
  }, [loadConversations]);
  usePolling(loadConversations, POLL_LIST_MS);

  // Deep link: /chats?with=<userId> opens (or starts) the chat with that person.
  useEffect(() => {
    const withId = searchParams.get('with');
    if (!withId) return;
    startDirectConversation(withId)
      .then((c) => {
        setSelectedId(c.id);
        void loadConversations();
      })
      .catch((e) => setError(getErrorMessage(e, 'Could not open that chat.')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const signature = (list: DirectMessage[]) => list.map((m) => `${m.id}:${m.status ?? ''}`).join('|');

  const refreshThread = useCallback(async () => {
    if (!selectedId) return;
    const data = await listDirectMessages(selectedId);
    const sig = signature(data);
    if (sig !== lastSig.current) {
      lastSig.current = sig;
      setMessages(data);
    }
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    setLoadingThread(true);
    setMessages([]);
    setInput('');
    lastSig.current = '';
    stick.current = true;
    listDirectMessages(selectedId)
      .then((data) => {
        lastSig.current = signature(data);
        setMessages(data);
        // Opening it marked it read — clear the badge straight away.
        setConversations((prev) => prev.map((c) => (c.id === selectedId ? { ...c, unread_count: 0 } : c)));
      })
      .catch(() => setError('Could not load this chat.'))
      .finally(() => setLoadingThread(false));
  }, [selectedId]);

  // While a chat is open it refreshes every few seconds (paused in hidden tabs) — that is also
  // what turns the other person's ticks blue.
  usePolling(refreshThread, POLL_THREAD_MS, !!selectedId);

  useEffect(() => {
    if (stick.current) endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  function onScroll() {
    const el = listRef.current;
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  }

  async function openPicker() {
    setPickerOpen(true);
    setQuery('');
    setContacts(null);
    try {
      setContacts(await listDirectContacts());
    } catch {
      setContacts([]);
    }
  }

  const filteredContacts = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (contacts ?? []).filter((c) => !q || c.name.toLowerCase().includes(q) || c.subtitle.toLowerCase().includes(q));
  }, [contacts, query]);

  async function pick(contact: DirectContact) {
    setStarting(contact.user_id);
    setError(null);
    try {
      const conv = await startDirectConversation(contact.user_id);
      await loadConversations();
      setSelectedId(conv.id);
      setPickerOpen(false);
    } catch (e) {
      setError(getErrorMessage(e, 'Could not start that chat.'));
    } finally {
      setStarting(null);
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || sending || !selectedId) return;
    setSending(true);
    setError(null);
    try {
      const sent = await sendDirectMessage(selectedId, text);
      stick.current = true;
      setMessages((prev) => {
        const next = [...prev, sent];
        lastSig.current = signature(next);
        return next;
      });
      setInput('');
      setConversations((prev) =>
        prev
          .map((c) => (c.id === selectedId ? { ...c, last_message_preview: text.slice(0, 80), last_message_at: sent.created_at } : c))
          .sort((a, b) => (b.last_message_at ?? '').localeCompare(a.last_message_at ?? ''))
      );
    } catch (e) {
      setError(getErrorMessage(e, 'Could not send that message. Try again in a moment.'));
    } finally {
      setSending(false);
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }

  let lastDay = '';

  return (
    <div className="bg-panel border border-ink-200 rounded-xl overflow-hidden grid grid-cols-1 md:grid-cols-[300px_1fr] h-[calc(100vh-12rem)] min-h-[480px] max-h-[760px] shadow-xl shadow-black/20 relative">
      {/* Conversation list (hidden on phones while a chat is open) */}
      <div className={`${selected ? 'hidden md:flex' : 'flex'} flex-col min-h-0 border-b md:border-b-0 md:border-r border-ink-200 bg-ink-950/40`}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-ink-200">
          <p className="text-sm font-semibold text-ink-900">Private chats</p>
          <button
            onClick={openPicker}
            className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-br from-emerald-700 to-cyan text-[#06110B] text-xs font-semibold px-3 py-1.5 hover:brightness-110"
          >
            <MessageSquarePlus className="w-3.5 h-3.5" strokeWidth={2.25} />
            New chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loaded && conversations.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <Lock className="w-7 h-7 text-ink-400 mx-auto mb-3" strokeWidth={1.5} />
              <p className="text-sm text-ink-900 font-medium">No private chats yet</p>
              <p className="text-xs text-ink-600 mt-1">
                {isTeacher
                  ? "Tap New chat and pick a parent from your grades to start a private conversation."
                  : "Tap New chat to message your child's teacher privately."}
              </p>
            </div>
          ) : (
            conversations.map((c) => {
              const active = c.id === selectedId;
              return (
                <button
                  key={c.id}
                  onClick={() => setSelectedId(c.id)}
                  className={`w-full flex items-center gap-3 text-left px-4 py-3 border-b border-ink-100 transition-colors ${
                    active ? 'bg-gradient-to-r from-emerald-100 to-transparent border-l-2 border-l-emerald-700' : 'hover:bg-ink-100/60'
                  }`}
                >
                  <Avatar id={c.other_user_id} name={c.other_name} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium text-ink-900 truncate">{c.other_name}</p>
                      {c.last_message_at && (
                        <span className={`text-[11px] shrink-0 ${c.unread_count ? 'text-emerald-700' : 'text-ink-400'}`}>
                          {formatListTime(c.last_message_at)}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs text-ink-600 truncate">{c.last_message_preview || c.other_subtitle}</p>
                      {!!c.unread_count && !active && (
                        <span className="min-w-[20px] h-5 px-1.5 rounded-full bg-green text-[#06110B] text-[11px] font-bold flex items-center justify-center shrink-0">
                          {c.unread_count > 99 ? '99+' : c.unread_count}
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* Thread */}
      <div className={`${selected ? 'flex' : 'hidden md:flex'} flex-col min-h-0 min-w-0`}>
        {!selected ? (
          <div className="chat-wallpaper flex-1 flex items-center justify-center p-6">
            <div className="text-center max-w-xs bg-panel/80 border border-ink-200 rounded-lg px-6 py-8">
              <Lock className="w-8 h-8 text-emerald-700 mx-auto mb-3" strokeWidth={1.5} />
              <p className="text-sm font-medium text-ink-900">Private, one-to-one</p>
              <p className="text-xs text-ink-600 mt-1">
                Choose a chat, or start a new one. Only you and the other person can see these conversations.
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="px-4 py-3 border-b border-ink-200 flex items-center gap-3 bg-gradient-to-r from-ink-100 to-panel">
              <button onClick={() => setSelectedId(null)} className="md:hidden text-ink-600 hover:text-ink-900" aria-label="Back to chats">
                <ArrowLeft className="w-5 h-5" strokeWidth={2} />
              </button>
              <Avatar id={selected.other_user_id} name={selected.other_name} />
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink-900 truncate">{selected.other_name}</p>
                <p className="text-xs text-ink-400 truncate">{selected.other_subtitle}</p>
              </div>
              <span
                className="ml-auto inline-flex items-center gap-1 text-[11px] text-emerald-700 border border-emerald-700/30 bg-emerald-100 rounded-full px-2.5 py-1 shrink-0"
                title="Messages are encrypted in transit and stored encrypted. Only you and this person can see this chat in Ledgr."
              >
                <Lock className="w-3 h-3" strokeWidth={2.5} />
                Encrypted
              </span>
            </div>

            <div ref={listRef} onScroll={onScroll} className="chat-wallpaper flex-1 min-h-0 overflow-y-auto px-4 sm:px-6 py-4 flex flex-col gap-1.5">
              <div className="self-center max-w-sm text-center text-[11px] text-ink-600 bg-panel/90 border border-ink-200 rounded-lg px-3 py-2 mb-2">
                <Lock className="w-3 h-3 inline -mt-0.5 mr-1" strokeWidth={2.5} />
                Encrypted in transit and stored encrypted. Only you and {selected.other_name.split(' ')[0]} can see this chat in Ledgr.
              </div>

              {loadingThread ? (
                <p className="text-sm text-ink-600 m-auto">Loading…</p>
              ) : messages.length === 0 ? (
                <p className="text-xs text-ink-600 m-auto">No messages yet — say hello.</p>
              ) : (
                messages.map((m) => {
                  const mine = m.sender_user_id === user?.id;
                  const day = dayLabel(m.created_at);
                  const showDay = day !== lastDay;
                  lastDay = day;
                  return (
                    <div key={m.id} className="msg-in">
                      {showDay && (
                        <div className="flex justify-center my-3">
                          <span className="text-[11px] text-ink-600 bg-panel/90 border border-ink-200 rounded-full px-3 py-1">{day}</span>
                        </div>
                      )}
                      <div className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
                        <div
                          className={`max-w-[80%] sm:max-w-[70%] rounded-2xl px-3.5 py-2 text-sm shadow-md shadow-black/20 ${
                            mine ? 'bg-green-100 border border-green-200 rounded-tr-md' : 'bg-ink-100 border border-ink-200 rounded-tl-md'
                          } text-ink-900`}
                        >
                          <p className="whitespace-pre-wrap break-words">{m.body}</p>
                          <div className="flex items-center justify-end gap-1.5 mt-1 text-ink-400">
                            <span className="text-[10px]">{formatTime(m.created_at)}</span>
                            {mine && m.status && <MessageTicks status={m.status} />}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={endRef} />
            </div>

            <div className="border-t border-ink-200 bg-panel px-3 sm:px-4 py-3">
              {error && <p className="text-xs text-clay-700 mb-2">{error}</p>}
              {selected.can_send ? (
                <div className="flex items-end gap-2">
                  <textarea
                    rows={1}
                    value={input}
                    onChange={(e) => {
                      setInput(e.target.value);
                      e.target.style.height = 'auto';
                      e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
                    }}
                    onKeyDown={onKeyDown}
                    placeholder={`Message ${selected.other_name.split(' ')[0]}…`}
                    disabled={sending}
                    className="flex-1 resize-none px-4 py-2.5 rounded-2xl border border-ink-200 text-sm bg-ink-100 text-ink-900 placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-emerald-700/30 max-h-[120px]"
                  />
                  <button
                    onClick={() => void handleSend()}
                    disabled={sending || !input.trim()}
                    aria-label="Send"
                    className="p-3 rounded-full bg-gradient-to-br from-emerald-700 to-cyan text-[#06110B] hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-emerald-700/20"
                  >
                    <Send className="w-4.5 h-4.5" strokeWidth={2.25} />
                  </button>
                </div>
              ) : (
                <p className="text-xs text-ink-600 text-center py-2">
                  You can't send messages here any more — you're no longer linked through a grade. You can still read the history.
                </p>
              )}
            </div>
          </>
        )}
      </div>

      {/* New chat picker */}
      {pickerOpen && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-ink-950/60" onClick={() => setPickerOpen(false)}>
          <div className="w-full max-w-md rounded-xl border border-ink-200 bg-panel shadow-2xl max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-ink-200">
              <p className="text-sm font-medium text-ink-900">{isTeacher ? 'Message a parent' : 'Message a teacher'}</p>
              <button onClick={() => setPickerOpen(false)} aria-label="Close" className="text-ink-400 hover:text-ink-900">
                <X className="w-4 h-4" strokeWidth={2} />
              </button>
            </div>
            <div className="px-4 py-3 border-b border-ink-200">
              <div className="relative">
                <Search className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2" strokeWidth={2} />
                <input
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={isTeacher ? 'Search parents or children…' : 'Search teachers…'}
                  className="w-full pl-9 pr-3 py-2 rounded-lg border border-ink-200 bg-ink-100 text-sm text-ink-900 placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-emerald-700/30"
                />
              </div>
            </div>
            <div className="overflow-y-auto p-1.5">
              {contacts === null ? (
                <p className="text-xs text-ink-600 p-4">Loading…</p>
              ) : filteredContacts.length === 0 ? (
                <p className="text-xs text-ink-600 p-4">
                  {contacts.length === 0
                    ? isTeacher
                      ? "No parents to show yet. You'll see parents of the grades you're assigned to, once their link to their child is approved."
                      : "No teachers to show yet. You'll see your child's teacher(s) once the school has approved your link to them."
                    : 'No matches.'}
                </p>
              ) : (
                filteredContacts.map((c) => (
                  <button
                    key={c.user_id}
                    onClick={() => void pick(c)}
                    disabled={starting === c.user_id}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left hover:bg-ink-100 disabled:opacity-60"
                  >
                    <Avatar id={c.user_id} name={c.name} size={36} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm text-ink-900 truncate">{c.name}</span>
                      <span className="block text-[11px] text-ink-400 truncate">{c.subtitle}</span>
                    </span>
                    {c.conversation_id && <span className="text-[10px] text-ink-400 shrink-0">Open chat</span>}
                    {!!c.unread_count && (
                      <span className="min-w-[20px] h-5 px-1.5 rounded-full bg-green text-[#06110B] text-[11px] font-bold flex items-center justify-center shrink-0">
                        {c.unread_count}
                      </span>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
