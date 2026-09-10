import { useState } from 'react';
import { Phone, Check } from 'lucide-react';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { updateMyProfile } from '../api/user';

interface UpdatePhoneFormProps {
  currentPhone: string | null;
  onUpdated: (newPhone: string) => void;
}

export function UpdatePhoneForm({ currentPhone, onUpdated }: UpdatePhoneFormProps) {
  const [editing, setEditing] = useState(false);
  const [phone, setPhone] = useState(currentPhone || '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const updated = await updateMyProfile({ phone });
      onUpdated(updated.phone || '');
      setEditing(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      setError('Could not update your phone number. Try again.');
    } finally {
      setSubmitting(false);
    }
  }

  if (!editing) {
    return (
      <div className="flex items-center justify-between bg-panel border border-ink-200 rounded-lg px-5 py-3.5">
        <div className="flex items-center gap-2.5 text-sm">
          <Phone className="w-4 h-4 text-ink-400" strokeWidth={1.75} />
          <span className="text-ink-900">{currentPhone || 'No phone number on file'}</span>
          {saved && (
            <span className="flex items-center gap-1 text-emerald-700 text-xs font-medium">
              <Check className="w-3.5 h-3.5" /> Updated
            </span>
          )}
        </div>
        <button
          onClick={() => setEditing(true)}
          className="text-xs font-medium text-ink-900 hover:underline underline-offset-2"
        >
          {currentPhone ? 'Change number' : 'Add number'}
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="bg-panel border border-ink-200 rounded-lg p-5 flex flex-col gap-3">
      <TextField
        label="Phone number"
        type="tel"
        placeholder="e.g. +254712345678"
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
        autoFocus
      />
      {error && <p className="text-sm text-clay-700">{error}</p>}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={() => setEditing(false)} className="text-xs px-3 py-1.5">
          Cancel
        </Button>
        <Button type="submit" disabled={submitting} className="text-xs px-3 py-1.5">
          {submitting ? 'Saving…' : 'Save'}
        </Button>
      </div>
    </form>
  );
}
