import { useState, type FormEvent } from 'react';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { updateInvoice } from '../api/school';

interface EditInvoiceDueDateFormProps {
  invoiceId: string;
  currentDueDate: string;
  onSuccess: () => void;
  onCancel: () => void;
}

export function EditInvoiceDueDateForm({ invoiceId, currentDueDate, onSuccess, onCancel }: EditInvoiceDueDateFormProps) {
  const [dueDate, setDueDate] = useState(currentDueDate.slice(0, 10));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await updateInvoice(invoiceId, new Date(dueDate).toISOString());
      onSuccess();
    } catch {
      setError('Could not save this change. Try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
      <TextField label="Due date" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} required />

      {error && (
        <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">
          {error}
        </p>
      )}

      <div className="flex justify-end gap-2 mt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : 'Save due date'}
        </Button>
      </div>
    </form>
  );
}
