import { useState } from 'react';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { SelectField } from './ui/SelectField';
import { bulkGenerateInvoices } from '../api/school';
import type { SchoolClass } from '../types';

interface BulkGenerateFormProps {
  termId: string;
  classes: SchoolClass[];
  onSuccess: (result: { created: number; skipped: number; errors: unknown[] }) => void;
  onCancel: () => void;
}

export function BulkGenerateForm({ termId, classes, onSuccess, onCancel }: BulkGenerateFormProps) {
  const [classId, setClassId] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!dueDate) {
      setError('Pick a due date for these invoices.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await bulkGenerateInvoices({
        term_id: termId,
        class_id: classId || undefined,
        due_date: new Date(dueDate).toISOString(),
      });
      onSuccess(result);
    } catch {
      setError('Could not generate invoices. Make sure fee structures exist for this term.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
      <SelectField
        label="Class"
        placeholder="All classes (every student in the school)"
        options={classes.map((c) => ({ value: c.id, label: c.name }))}
        value={classId}
        onChange={(e) => setClassId(e.target.value)}
      />
      <TextField label="Due date" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />

      {error && (
        <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">
          {error}
        </p>
      )}

      <p className="text-xs text-ink-600">
        This creates one invoice per active student, totaling every fee structure set up for this term. Students who
        already have an invoice for this term are skipped automatically.
      </p>

      <div className="flex justify-end gap-2 mt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Generating…' : 'Generate invoices'}
        </Button>
      </div>
    </form>
  );
}
