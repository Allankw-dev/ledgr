import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Send, Users } from 'lucide-react';
import { listClassGroups, listClassGroupMessages, sendClassGroupMessage } from '../api/classGroups';
import { useAuthStore } from '../store/authStore';
import type { ClassGroupSummary, ClassGroupMessage } from '../types';

const roleLabel: Record<string, string> = {
  SCHOOL_ADMIN: 'School office',
  BURSAR: "Bursar's office",
  TEACHER: 'Teacher',
  PARENT: 'Parent',
};

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en-KE', { hour: 'numeric', minute: '2-digit' });
}

function formatPreviewTime(iso: string) {
  const d = new Date(iso);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  return sameDay
    ? d.toLocaleTimeString('en-KE', { hour: 'numeric', minute: '2-digit' })
    : d.toLocaleDateString('en-KE', { day: 'numeric', month: 'short' });
}

export function ClassGroupChat() {
  const user = useAuthStore((s) => s.user);
  const [groups, setGroups] = useState<ClassGroupSummary[]>([]);
  const [groupsLoaded, setGroupsLoaded] = useState(false);
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ClassGroupMessage[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listClassGroups()
      .then((data) => {
        setGroups(data);
        if (data.length > 0) setSelectedClassId(data[0].class_id);
      })
      .catch(() => setError('Could not load your class groups.'))
      .finally(() => setGroupsLoaded(true));
  }, []);

  useEffect(() => {
    if (!selectedClassId) return;
    setLoadingMessages(true);
    listClassGroupMessages(selectedClassId)
      .then(setMessages)
      .catch(() => setError('Could not load this conversation.'))
      .finally(() => setLoadingMessages(false));
  }, [selectedClassId]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || sending || !selectedClassId) return;

    setSending(true);
    setError(null);
    try {
      const sent = await sendClassGroupMessage(selectedClassId, trimmed);
      setMessages((prev) => [...prev, sent]);
      setInput('');
      setGroups((prev) =>
        prev.map((g) =>
          g.class_id === selectedClassId
            ? { ...g, last_message_preview: sent.body.slice(0, 120), last_message_at: sent.created_at }
            : g
        )
      );
    } catch {
      setError('Could not send that message. Try again in a moment.');
    } finally {
      setSending(false);
    }
  }

  const selectedGroup = groups.find((g) => g.class_id === selectedClassId);

  if (groupsLoaded && groups.length === 0) {
    return (
      <div className="bg-panel border border-ink-200 rounded-lg px-6 py-16 text-center">
        <Users className="w-8 h-8 text-ink-400 mx-auto mb-3" strokeWidth={1.5} />
        <p className="text-sm text-ink-900 font-medium">No class groups yet</p>
        <p className="text-xs text-ink-600 mt-1">
          You'll see a group here once you're linked to a grade — as a child's parent, a teacher assigned to it, or
          a member of the school office.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-panel border border-ink-200 rounded-lg overflow-hidden grid grid-cols-1 md:grid-cols-[260px_1fr]" style={{ height: '640px' }}>
      {/* Group list */}
      <div className="border-b md:border-b-0 md:border-r border-ink-200 overflow-y-auto">
        {groups.map((g) => (
          <button
            key={g.class_id}
            onClick={() => setSelectedClassId(g.class_id)}
            className={`w-full text-left px-4 py-3 border-b border-ink-100 transition-colors ${
              g.class_id === selectedClassId ? 'bg-ink-100' : 'hover:bg-ink-100/50'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium text-ink-900 truncate">{g.class_name}</p>
              {g.last_message_at && (
                <span className="text-[11px] text-ink-400 shrink-0">{formatPreviewTime(g.last_message_at)}</span>
              )}
            </div>
            <p className="text-xs text-ink-600 truncate mt-0.5">
              {g.last_message_preview || 'No messages yet'}
            </p>
          </button>
        ))}
      </div>

      {/* Thread */}
      <div className="flex flex-col min-h-0">
        <div className="px-5 py-3.5 border-b border-ink-200 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center shrink-0">
            <Users className="w-4 h-4 text-[#06110B]" strokeWidth={2} />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-ink-900 truncate">
              {selectedGroup ? `${selectedGroup.class_name} Group` : 'Select a group'}
            </p>
            <p className="text-xs text-ink-400">Parents, teachers, and the school office</p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3">
          {loadingMessages ? (
            <p className="text-sm text-ink-600">Loading…</p>
          ) : messages.length === 0 ? (
            <p className="text-sm text-ink-600">
              No messages yet. Say hello to start the conversation for this class.
            </p>
          ) : (
            messages.map((m) => {
              const isMine = m.sender_user_id === user?.id;
              return (
                <div key={m.id} className={`flex ${isMine ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[75%] rounded-lg px-3.5 py-2 text-sm whitespace-pre-wrap ${
                      isMine ? 'bg-ink-800 text-ink-900' : 'bg-ink-100 text-ink-900'
                    }`}
                  >
                    {!isMine && (
                      <p className="text-xs font-medium text-emerald-700 mb-0.5">
                        {m.sender_name} <span className="text-ink-400 font-normal">· {roleLabel[m.sender_role] || m.sender_role}</span>
                      </p>
                    )}
                    {m.body}
                    <p className={`text-[10px] mt-1 ${isMine ? 'text-ink-400' : 'text-ink-400'}`}>{formatTime(m.created_at)}</p>
                  </div>
                </div>
              );
            })
          )}
          {error && <p className="text-xs text-clay-700">{error}</p>}
          <div ref={scrollRef} />
        </div>

        <form onSubmit={handleSubmit} className="flex items-center gap-2 px-5 py-3 border-t border-ink-200">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={selectedClassId ? 'Type a message…' : 'Select a group first'}
            disabled={!selectedClassId || sending}
            className="flex-1 px-3.5 py-2 rounded-md border border-ink-200 text-sm bg-panel focus:outline-none focus:ring-2 focus:ring-emerald-700/30"
          />
          <button
            type="submit"
            disabled={sending || !input.trim() || !selectedClassId}
            className="p-2.5 rounded-md bg-gradient-to-br from-emerald-700 to-cyan text-[#06110B] hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="Send"
          >
            <Send className="w-4 h-4" strokeWidth={2} />
          </button>
        </form>
      </div>
    </div>
  );
}
