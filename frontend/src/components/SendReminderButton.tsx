import { useState } from 'react';
import { Bell } from 'lucide-react';
import { sendInvoiceReminder } from '../api/school';
import { getErrorMessage } from '../api/client';

export function SendReminderButton({ invoiceId }: { invoiceId: string }) {
  const [sending, setSending] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  async function handleClick() {
    setSending(true);
    setFeedback(null);
    try {
      const result = await sendInvoiceReminder(invoiceId);
      const emailCount = result.results.filter((r) => r.email_sent).length;
      const smsCount = result.results.filter((r) => r.sms_sent).length;

      if (emailCount === 0 && smsCount === 0) {
        setIsError(true);
        setFeedback('No reminder was sent — email/SMS may not be set up yet, or the guardian has no contact info on file.');
      } else {
        setIsError(false);
        const parts = [];
        if (emailCount > 0) parts.push(`${emailCount} email${emailCount === 1 ? '' : 's'}`);
        if (smsCount > 0) parts.push(`${smsCount} SMS`);
        setFeedback(`Reminder sent: ${parts.join(', ')}.`);
      }
    } catch (err: unknown) {
      setIsError(true);
      setFeedback(getErrorMessage(err, 'Could not send the reminder.'));
    } finally {
      setSending(false);
      setTimeout(() => setFeedback(null), 6000);
    }
  }

  return (
    <div className="relative inline-block">
      <button
        onClick={handleClick}
        disabled={sending}
        className="text-xs font-medium text-ink-900 hover:underline underline-offset-2 flex items-center gap-1 disabled:opacity-50"
      >
        <Bell className="w-3.5 h-3.5" /> {sending ? 'Sending…' : 'Remind'}
      </button>
      {feedback && (
        <div
          role="status"
          className={`absolute z-10 top-full right-0 mt-1.5 w-56 text-xs rounded-md px-3 py-2 shadow-lg ${
            isError ? 'bg-clay-100 text-clay-700' : 'bg-emerald-100 text-emerald-700'
          }`}
        >
          {feedback}
        </div>
      )}
    </div>
  );
}
