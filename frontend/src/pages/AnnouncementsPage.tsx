import { useState, type FormEvent } from 'react';
import { Megaphone, Send } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Button } from '../components/ui/Button';
import { TextField } from '../components/ui/TextField';
import { SelectField } from '../components/ui/SelectField';
import { useClasses } from '../hooks/useSchoolSetup';
import { sendAnnouncement, type SendAnnouncementResult } from '../api/announcements';

export function AnnouncementsPage() {
  const { classes } = useClasses();
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [classId, setClassId] = useState('');
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<SendAnnouncementResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const audienceLabel = classId ? classes.find((c) => c.id === classId)?.name || 'this class' : 'the whole school';

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!subject.trim() || !message.trim()) return;

    const confirmed = window.confirm(
      `Send this to every parent/guardian linked to ${audienceLabel}? This can't be undone.`
    );
    if (!confirmed) return;

    setSending(true);
    setError(null);
    setResult(null);
    try {
      const res = await sendAnnouncement({ subject: subject.trim(), message: message.trim(), classId: classId || undefined });
      setResult(res);
      setSubject('');
      setMessage('');
    } catch {
      setError('Could not send the announcement. Check your connection and try again.');
    } finally {
      setSending(false);
    }
  }

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto px-4 sm:px-8 py-6 sm:py-8">
        <div className="mb-6">
          <h1 className="font-display text-2xl text-ink-900 font-medium flex items-center gap-2">
            <Megaphone className="w-5 h-5" strokeWidth={1.75} />
            Announcements
          </h1>
          <p className="text-sm text-ink-600 mt-1">
            Send a notice to parents by email and SMS — term dates, events, anything that isn't a fee reminder.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="bg-panel border border-ink-200 rounded-lg p-6 flex flex-col gap-4">
          <SelectField
            label="Send to"
            value={classId}
            onChange={(e) => setClassId(e.target.value)}
            options={classes.map((c) => ({ value: c.id, label: c.name }))}
            placeholder="Whole school"
          />
          <TextField
            label="Subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            maxLength={150}
            placeholder="e.g. Sports Day — Friday 14th"
            required
          />
          <div className="flex flex-col gap-1.5">
            <label htmlFor="announcement-message" className="text-sm font-medium text-ink-700">
              Message
            </label>
            <textarea
              id="announcement-message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              maxLength={2000}
              rows={6}
              placeholder="Write the notice as you'd like a parent to read it — a greeting and sign-off are added automatically for email."
              className="px-3.5 py-2.5 rounded-md border border-ink-200 bg-panel text-ink-900 text-sm placeholder:text-ink-400 focus-visible:outline-2 focus-visible:outline-ink-600 resize-y"
              required
            />
            <p className="text-xs text-ink-400 text-right">{message.length}/2000</p>
          </div>

          {error && (
            <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm">
              {error}
            </div>
          )}

          {result && (
            <div className="bg-emerald-50 text-emerald-800 rounded-md px-4 py-3 text-sm">
              Sent to {result.recipient_count} guardian{result.recipient_count === 1 ? '' : 's'} —{' '}
              {result.emails_sent} email{result.emails_sent === 1 ? '' : 's'}, {result.sms_sent} text
              {result.sms_sent === 1 ? '' : 's'} delivered.
              {result.errors.length > 0 && (
                <ul className="mt-2 list-disc list-inside text-xs">
                  {result.errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <Button type="submit" disabled={sending || !subject.trim() || !message.trim()} className="self-start flex items-center gap-2">
            <Send className="w-4 h-4" strokeWidth={2} />
            {sending ? 'Sending…' : `Send to ${audienceLabel}`}
          </Button>
        </form>
      </div>
    </AppShell>
  );
}
