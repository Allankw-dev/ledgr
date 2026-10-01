import { useEffect, useState } from 'react';
import { Phone, Mail } from 'lucide-react';
import { getStudentDetails } from '../api/school';
import type { StudentDetails, GuardianDetail } from '../types';

const STATUS_LABEL: Record<GuardianDetail['status'], { text: string; cls: string }> = {
  APPROVED: { text: 'Linked', cls: 'bg-emerald-100 text-emerald-700' },
  PENDING: { text: 'Awaiting approval', cls: 'bg-amber-100 text-amber-700' },
  INVITED: { text: 'Not signed up yet', cls: 'bg-ink-100 text-ink-600' },
};

function kes(value: string) {
  return `KES ${Number(value).toLocaleString()}`;
}

function formatDate(iso: string | null) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs text-ink-600">{label}</p>
      <p className="text-sm text-ink-900 mt-0.5">{children}</p>
    </div>
  );
}

/** Everything the bursar needs about one student, loaded when the row is opened. */
export function StudentDetailsPanel({ studentId }: { studentId: string }) {
  const [details, setDetails] = useState<StudentDetails | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setDetails(null);
    setError(null);
    getStudentDetails(studentId)
      .then((d) => !cancelled && setDetails(d))
      .catch(() => !cancelled && setError('Could not load details. Try again.'));
    return () => {
      cancelled = true;
    };
  }, [studentId]);

  if (error) return <p className="px-5 py-4 text-sm text-clay-700">{error}</p>;
  if (!details) return <p className="px-5 py-4 text-sm text-ink-600">Loading details…</p>;

  const owing = Number(details.balance_due) > 0;

  return (
    <div className="px-5 py-4 grid gap-6 md:grid-cols-2">
      <div className="flex flex-col gap-5">
        <div className="grid grid-cols-2 gap-x-6 gap-y-3">
          <Field label="Admission no.">{details.admission_number}</Field>
          <Field label="Grade">{details.class_name ?? 'Unassigned'}</Field>
          <Field label="Date of birth">{formatDate(details.date_of_birth)}</Field>
          <Field label="Enrolled">{formatDate(details.created_at)}</Field>
        </div>
        <div>
          <p className="text-xs text-ink-600 mb-1.5">Fees</p>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Billed">
              <span className="figure">{kes(details.total_billed)}</span>
            </Field>
            <Field label="Paid">
              <span className="figure">{kes(details.total_paid)}</span>
            </Field>
            <Field label="Balance">
              <span className={`figure font-medium ${owing ? 'text-clay-700' : 'text-emerald-700'}`}>
                {kes(details.balance_due)}
              </span>
            </Field>
          </div>
        </div>
      </div>

      <div>
        <p className="text-xs text-ink-600 mb-1.5">Parents / guardians</p>
        {details.guardians.length === 0 ? (
          <p className="text-sm text-ink-600">No parent recorded yet. Use “Link parent” to add one.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {details.guardians.map((g, i) => (
              <li key={`${g.name}-${i}`} className="rounded-md border border-ink-200 px-3 py-2.5">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <p className="text-sm font-medium text-ink-900">
                    {g.name}
                    <span className="ml-2 text-xs font-normal text-ink-600 capitalize">
                      {g.relationship_type}
                      {g.is_primary ? ' · primary' : ''}
                    </span>
                  </p>
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_LABEL[g.status].cls}`}>
                    {STATUS_LABEL[g.status].text}
                  </span>
                </div>
                <div className="mt-1.5 flex flex-col gap-1 text-sm">
                  {g.phone ? (
                    <a href={`tel:${g.phone}`} className="flex items-center gap-2 text-ink-900 hover:underline underline-offset-2 figure">
                      <Phone className="w-3.5 h-3.5 text-ink-600" /> {g.phone}
                    </a>
                  ) : (
                    <span className="flex items-center gap-2 text-ink-400">
                      <Phone className="w-3.5 h-3.5" /> No phone number
                    </span>
                  )}
                  {g.email ? (
                    <a href={`mailto:${g.email}`} className="flex items-center gap-2 text-ink-900 hover:underline underline-offset-2 break-all">
                      <Mail className="w-3.5 h-3.5 text-ink-600" /> {g.email}
                    </a>
                  ) : (
                    <span className="flex items-center gap-2 text-ink-400">
                      <Mail className="w-3.5 h-3.5" /> No email
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
