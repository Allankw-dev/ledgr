import { useCallback, useEffect, useState } from 'react';
import {
  listSubscriptionPayments,
  recordSubscriptionPayment,
  voidSubscriptionPayment,
  type PaymentMethodName,
  type PlatformSchool,
  type SubscriptionPaymentList,
} from '../api/subscription';
import { getErrorMessage } from '../api/client';
import { money } from '../lib/money';

const FIELD = 'mt-1 w-full rounded-lg bg-white/[0.05] border border-white/[0.08] px-3 py-2 text-sm text-ink-900';
const BTN = 'rounded-full border border-white/[0.1] px-3 py-1.5 text-xs text-ink-900 hover:border-lime/50 disabled:opacity-40 transition-colors';

const METHODS: { value: PaymentMethodName; label: string; needsReference: boolean }[] = [
  { value: 'MPESA', label: 'M-Pesa', needsReference: true },
  { value: 'BANK_TRANSFER', label: 'Bank transfer', needsReference: true },
  { value: 'CASH', label: 'Cash', needsReference: false },
  { value: 'CHEQUE', label: 'Cheque', needsReference: false },
  { value: 'OTHER', label: 'Other', needsReference: false },
];

const today = () => new Date().toISOString().slice(0, 10);
const day = (iso: string) => new Date(iso).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' });

/**
 * The operator's book of what ONE school paid for using Ledgr. Booking a payment and extending the school's
 * paid-until date happen in one step on the server, so the money and the date can't drift apart. A mistake is
 * voided (kept, struck through, with a reason), never deleted.
 */
export function SchoolBillingPanel({ school, onSchoolChanged }: { school: PlatformSchool; onSchoolChanged: () => void }) {
  const [book, setBook] = useState<SubscriptionPaymentList | null>(null);
  const [loadError, setLoadError] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);

  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState<PaymentMethodName>('MPESA');
  const [reference, setReference] = useState('');
  const [months, setMonths] = useState('1');
  const [paidOn, setPaidOn] = useState(today());
  const [note, setNote] = useState('');

  const [voiding, setVoiding] = useState<string | null>(null);
  const [voidReason, setVoidReason] = useState('');

  const refresh = useCallback(() => {
    listSubscriptionPayments(school.id)
      .then(setBook)
      .catch(() => setLoadError("Couldn't load this school's payment book."));
  }, [school.id]);
  useEffect(refresh, [refresh]);

  const needsReference = METHODS.find((m) => m.value === method)?.needsReference ?? false;

  async function record(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      const row = await recordSubscriptionPayment(school.id, {
        amount: amount.trim(),
        method,
        ...(reference.trim() ? { reference: reference.trim() } : {}),
        paid_on: `${paidOn}T12:00:00Z`,
        months: Number(months),
        ...(note.trim() ? { note: note.trim() } : {}),
      });
      setNotice({
        ok: true,
        text: `Recorded ${money(row.amount, row.currency)}${row.months_added ? ` and added ${row.months_added} month${row.months_added === 1 ? '' : 's'}` : ' (the paid-until date was not changed)'}.`,
      });
      setAmount('');
      setReference('');
      setNote('');
      refresh();
      onSchoolChanged();
    } catch (err) {
      setNotice({ ok: false, text: getErrorMessage(err, "That payment wasn't recorded. Please try again.") });
    } finally {
      setBusy(false);
    }
  }

  async function confirmVoid(id: string) {
    setBusy(true);
    setNotice(null);
    try {
      await voidSubscriptionPayment(id, voidReason.trim());
      setVoiding(null);
      setVoidReason('');
      setNotice({ ok: true, text: "Marked as a mistake. The paid-until date was not changed. Edit it yourself if it should move." });
      refresh();
      onSchoolChanged();
    } catch (err) {
      setNotice({ ok: false, text: getErrorMessage(err, "Couldn't void that payment.") });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label={`Billing for ${school.name}`} className="mt-4 rounded-xl border border-white/[0.08] p-4 space-y-5">
      <div>
        <h3 className="font-display text-base text-ink-900">What {school.name} has paid you</h3>
        <p className="mt-1 text-xs text-ink-400">
          Record each payment here, and say how many months it covers. That keeps the money and the paid-until date together.
        </p>
      </div>

      <form onSubmit={record} className="grid sm:grid-cols-3 gap-3" aria-label="Record a payment">
        <label className="text-xs text-ink-400">
          Amount ({book?.currency ?? 'KES'})
          <input required inputMode="decimal" pattern="\d+(\.\d{1,2})?" value={amount} onChange={(e) => setAmount(e.target.value)} className={FIELD} />
        </label>
        <label className="text-xs text-ink-400">
          How they paid
          <select value={method} onChange={(e) => setMethod(e.target.value as PaymentMethodName)} className={FIELD}>
            {METHODS.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </label>
        <label className="text-xs text-ink-400">
          {method === 'MPESA' ? 'M-Pesa code' : method === 'BANK_TRANSFER' ? 'Bank reference' : 'Reference (optional)'}
          <input required={needsReference} value={reference} onChange={(e) => setReference(e.target.value)} className={FIELD} />
        </label>
        <label className="text-xs text-ink-400">
          Months this covers
          <input type="number" min={0} max={36} required value={months} onChange={(e) => setMonths(e.target.value)} className={FIELD} />
        </label>
        <label className="text-xs text-ink-400">
          Date paid
          <input type="date" required value={paidOn} max={today()} onChange={(e) => setPaidOn(e.target.value)} className={FIELD} />
        </label>
        <label className="text-xs text-ink-400">
          Note (optional)
          <input maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} className={FIELD} />
        </label>
        <div className="sm:col-span-3 flex flex-wrap items-center gap-3">
          <button disabled={busy} className="rounded-full bg-lime text-[#0B1203] font-semibold text-sm px-5 py-2 disabled:opacity-50">
            {busy ? 'Saving…' : 'Record payment'}
          </button>
          <span className="text-xs text-ink-400">0 months books the money without moving the date (a deposit, say).</span>
        </div>
      </form>

      {notice && (
        <p role={notice.ok ? 'status' : 'alert'} className={`text-xs ${notice.ok ? 'text-green' : 'text-coral'}`}>
          {notice.text}
        </p>
      )}

      <div>
        <div className="flex items-baseline justify-between gap-3">
          <h4 className="text-sm text-ink-900">Payment book</h4>
          {book && <span className="text-xs text-ink-400">Total paid: <strong className="text-ink-900">{money(book.total_paid, book.currency)}</strong></span>}
        </div>
        {loadError && <p role="alert" className="mt-2 text-xs text-coral">{loadError}</p>}
        {!book && !loadError && <p className="mt-2 text-xs text-ink-400">Loading…</p>}
        {book && book.payments.length === 0 && <p className="mt-2 text-xs text-ink-400">Nothing recorded yet.</p>}
        {book && book.payments.length > 0 && (
          <ul className="mt-2 divide-y divide-white/[0.06]">
            {book.payments.map((p) => {
              const voided = p.voided_at !== null;
              return (
                <li key={p.id} className="py-2.5 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className={voided ? 'line-through text-ink-400' : 'text-ink-900'}>
                      <span className="figure">{money(p.amount, p.currency)}</span>
                      <span className="text-ink-400"> · {METHODS.find((m) => m.value === p.method)?.label ?? p.method}</span>
                      {p.reference && <span className="text-ink-400"> · {p.reference}</span>}
                      <span className="text-ink-400"> · {day(p.paid_on)}</span>
                      {p.months_added > 0 && <span className="text-ink-400"> · {p.months_added} month{p.months_added === 1 ? '' : 's'}</span>}
                    </div>
                    {!voided && voiding !== p.id && (
                      <button className={BTN} disabled={busy} onClick={() => { setVoiding(p.id); setVoidReason(''); }}>
                        Entered by mistake
                      </button>
                    )}
                    {voided && <span className="text-coral">Voided: {p.void_reason}</span>}
                  </div>
                  {p.note && <p className="mt-0.5 text-ink-400">{p.note}</p>}
                  {voiding === p.id && (
                    <form
                      className="mt-2 flex flex-wrap items-end gap-2"
                      onSubmit={(e) => {
                        e.preventDefault();
                        void confirmVoid(p.id);
                      }}
                    >
                      <label className="text-xs text-ink-400 flex-1 min-w-[12rem]">
                        Why is this a mistake?
                        <input required minLength={3} maxLength={300} value={voidReason} onChange={(e) => setVoidReason(e.target.value)} className={FIELD} />
                      </label>
                      <button disabled={busy || voidReason.trim().length < 3} className={`${BTN} hover:!border-coral/60 text-coral`}>Void it</button>
                      <button type="button" className={BTN} onClick={() => setVoiding(null)}>Cancel</button>
                    </form>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
