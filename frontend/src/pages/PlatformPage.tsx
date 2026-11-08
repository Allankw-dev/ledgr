import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { BookOpen, LogOut, Plus } from 'lucide-react';
import { DxCard } from '../components/dx/DxCard';
import {
  createSchool,
  getPaymentsHealth,
  listPlatformSchools,
  updateSchoolSubscription,
  type CreatedSchool,
  type PlatformSchool,
  type SchoolPaymentsHealth,
  type SubscriptionStatus,
  type SubscriptionUpdate,
} from '../api/subscription';
import { getErrorMessage } from '../api/client';
import { MpesaSetupPanel } from '../components/MpesaSetupPanel';
import { PaymentsHealthPanel } from '../components/PaymentsHealthPanel';
import { SchoolBillingPanel } from '../components/SchoolBillingPanel';
import { OperatorTwoFactor } from '../components/OperatorTwoFactor';
import { useAuthStore } from '../store/authStore';

const PILL: Record<SubscriptionStatus, string> = {
  ACTIVE: 'bg-green-100 text-green',
  TRIAL: 'bg-lime/15 text-lime',
  GRACE: 'bg-amber-100 text-amber',
  EXPIRED: 'bg-coral-100 text-coral',
  SUSPENDED: 'bg-coral-100 text-coral',
};

function when(s: PlatformSchool): string {
  const date = s.subscription_status === 'TRIAL' ? s.trial_ends_at : s.paid_until;
  if (s.status === 'SUSPENDED') return 'Switched off';
  if (!date) return s.subscription_status === 'TRIAL' ? 'Trial with no end date' : 'No end date';
  const d = new Date(date).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' });
  if (s.status === 'EXPIRED') return `Ended ${d}`;
  if (s.status === 'GRACE') return `Ended ${d} · read-only in ${s.days_left ?? 0}d`;
  return `${s.subscription_status === 'TRIAL' ? 'Trial ends' : 'Paid until'} ${d}${s.days_left !== null ? ` · ${s.days_left}d left` : ''}`;
}

const toInputDate = (iso: string | null) => (iso ? iso.slice(0, 10) : '');

function SchoolCard({ school, onChange, onSchoolChanged }: { school: PlatformSchool; onChange: (s: PlatformSchool) => void; onSchoolChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(false);
  const [paymentsOpen, setPaymentsOpen] = useState(false);
  const [billingOpen, setBillingOpen] = useState(false);
  const [paidUntil, setPaidUntil] = useState(toInputDate(school.paid_until));
  const [limit, setLimit] = useState(school.learner_limit?.toString() ?? '');

  async function apply(body: SubscriptionUpdate) {
    setBusy(true);
    setError('');
    try {
      onChange(await updateSchoolSubscription(school.id, body));
      setEditing(false);
    } catch {
      setError("That didn't save. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const btn = 'rounded-full border border-white/[0.1] px-3 py-1.5 text-xs text-ink-900 hover:border-lime/50 disabled:opacity-40 transition-colors';
  const suspended = school.subscription_status === 'SUSPENDED';

  return (
    <DxCard className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-display text-lg text-ink-900 truncate">{school.name}</h2>
          <p className="text-xs text-ink-400 truncate">{school.contact_email}</p>
        </div>
        <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${PILL[school.status]}`}>{school.status}</span>
      </div>

      <dl className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
        <div>
          <dt className="text-xs text-ink-400">Standing</dt>
          <dd className="text-ink-900 mt-0.5">{when(school)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-400">Learners</dt>
          <dd className="figure text-ink-900 mt-0.5">
            {school.learner_count}
            {school.learner_limit !== null ? ` / ${school.learner_limit}` : ''}
            {school.learner_limit !== null && school.learner_count > school.learner_limit && <span className="ml-2 text-xs text-amber">over</span>}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-400">Plan</dt>
          <dd className="text-ink-900 mt-0.5">{school.plan}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-400">Last paid you</dt>
          <dd className="text-ink-900 mt-0.5">
            {school.last_payment_on ? new Date(school.last_payment_on).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Nothing recorded'}
          </dd>
        </div>
      </dl>

      <div className="mt-4 flex flex-wrap gap-2">
        <button className={`${btn} !border-lime/40`} aria-expanded={billingOpen} onClick={() => setBillingOpen((o) => !o)}>{billingOpen ? 'Hide billing' : 'Record payment'}</button>
        <button className={btn} disabled={busy} onClick={() => apply({ trial_days: 30 })}>30-day trial</button>
        <button className={btn} disabled={busy} onClick={() => setEditing((e) => !e)}>{editing ? 'Cancel' : 'Edit'}</button>
        <button className={btn} aria-expanded={paymentsOpen} onClick={() => setPaymentsOpen((o) => !o)}>{paymentsOpen ? 'Hide M-Pesa' : 'M-Pesa setup'}</button>
        {suspended ? (
          <button className={`${btn} !border-lime/50 text-lime`} disabled={busy} onClick={() => apply({ status: 'ACTIVE' })}>Reactivate</button>
        ) : (
          <button
            className={`${btn} hover:!border-coral/60 text-coral`}
            disabled={busy}
            onClick={() => window.confirm(`Switch off ${school.name}? Their staff become read-only (it can take up to a minute to reach every server) and automatic reminders stop. Parents can still pay.`) && apply({ status: 'SUSPENDED' })}
          >
            Suspend
          </button>
        )}
      </div>

      {editing && (
        <form
          className="mt-4 grid sm:grid-cols-[1fr_1fr_auto] gap-3 items-end"
          onSubmit={(e) => {
            e.preventDefault();
            void apply({
              paid_until: paidUntil ? `${paidUntil}T23:59:59Z` : null,
              learner_limit: limit.trim() === '' ? null : Number(limit),
            });
          }}
        >
          <label className="text-xs text-ink-400">
            Paid until
            <input type="date" value={paidUntil} onChange={(e) => setPaidUntil(e.target.value)} className="mt-1 w-full rounded-lg bg-white/[0.05] border border-white/[0.08] px-3 py-2 text-sm text-ink-900" />
          </label>
          <label className="text-xs text-ink-400">
            Learner limit (blank = none)
            <input type="number" min={1} value={limit} onChange={(e) => setLimit(e.target.value)} className="mt-1 w-full rounded-lg bg-white/[0.05] border border-white/[0.08] px-3 py-2 text-sm text-ink-900" />
          </label>
          <button disabled={busy} className="rounded-full bg-lime text-[#0B1203] font-semibold text-sm px-5 py-2 disabled:opacity-50">Save</button>
          <div className="sm:col-span-3 flex flex-wrap items-center gap-2 border-t border-white/[0.06] pt-3">
            <span className="text-xs text-ink-400">Free extension, no payment (goodwill or a correction). When they paid, use Record payment instead:</span>
            <button type="button" className={btn} disabled={busy} onClick={() => apply({ extend_months: 1 })}>+1 month</button>
            <button type="button" className={btn} disabled={busy} onClick={() => apply({ extend_months: 4 })}>+4 months</button>
            <button type="button" className={btn} disabled={busy} onClick={() => apply({ extend_months: 12 })}>+12 months</button>
          </div>
        </form>
      )}
      {billingOpen && <SchoolBillingPanel school={school} onSchoolChanged={onSchoolChanged} />}
      {paymentsOpen && <MpesaSetupPanel schoolId={school.id} schoolName={school.name} />}
      {error && <p role="alert" className="mt-3 text-xs text-coral">{error}</p>}
    </DxCard>
  );
}

const FIELD = 'mt-1 w-full rounded-lg bg-white/[0.05] border border-white/[0.08] px-3 py-2 text-sm text-ink-900';

function AddSchoolForm({ onCreated, onCancel }: { onCreated: (s: CreatedSchool) => void; onCancel: () => void }) {
  const [schoolName, setSchoolName] = useState('');
  const [adminName, setAdminName] = useState('');
  const [adminEmail, setAdminEmail] = useState('');
  const [trialDays, setTrialDays] = useState('30');
  const [limit, setLimit] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      onCreated(
        await createSchool({
          school_name: schoolName.trim(),
          admin_full_name: adminName.trim(),
          admin_email: adminEmail.trim(),
          trial_days: trialDays.trim() === '' ? undefined : Number(trialDays),
          learner_limit: limit.trim() === '' ? undefined : Number(limit),
        }),
      );
    } catch (err) {
      setError(getErrorMessage(err, "That school couldn't be created. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <DxCard className="p-5">
      <h2 className="font-display text-lg text-ink-900">Add a school</h2>
      <p className="text-xs text-ink-400 mt-1">The school's administrator gets an email with a link to set their own password.</p>
      <form className="mt-4 grid sm:grid-cols-2 gap-3" onSubmit={submit}>
        <label className="text-xs text-ink-400">
          School name
          <input required minLength={2} value={schoolName} onChange={(e) => setSchoolName(e.target.value)} className={FIELD} />
        </label>
        <label className="text-xs text-ink-400">
          Administrator's full name
          <input required minLength={2} value={adminName} onChange={(e) => setAdminName(e.target.value)} className={FIELD} />
        </label>
        <label className="text-xs text-ink-400">
          Administrator's email
          <input required type="email" value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} className={FIELD} />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs text-ink-400">
            Trial days (blank = none)
            <input type="number" min={1} max={120} value={trialDays} onChange={(e) => setTrialDays(e.target.value)} className={FIELD} />
          </label>
          <label className="text-xs text-ink-400">
            Learner limit (blank = none)
            <input type="number" min={1} value={limit} onChange={(e) => setLimit(e.target.value)} className={FIELD} />
          </label>
        </div>
        <div className="sm:col-span-2 flex items-center gap-3">
          <button disabled={busy} className="rounded-full bg-lime text-[#0B1203] font-semibold text-sm px-5 py-2 disabled:opacity-50">
            {busy ? 'Creating…' : 'Create school'}
          </button>
          <button type="button" onClick={onCancel} className="text-sm text-ink-600 hover:text-ink-900">Cancel</button>
        </div>
      </form>
      {error && <p role="alert" className="mt-3 text-xs text-coral">{error}</p>}
    </DxCard>
  );
}

const PAGE_SIZE = 20;

type Filter = 'ALL' | 'RENEW' | 'SUSPENDED' | 'PAYMENTS';
const FILTERS: { value: Filter; label: string }[] = [
  { value: 'ALL', label: 'All' },
  { value: 'RENEW', label: 'Needs renewing' },
  { value: 'SUSPENDED', label: 'Suspended' },
  { value: 'PAYMENTS', label: 'Payment problems' },
];

export function PlatformPage() {
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);
  const user = useAuthStore((s) => s.user);
  const [schools, setSchools] = useState<PlatformSchool[] | null>(null);
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);
  const [notice, setNotice] = useState('');
  // The server answers 403 until the operator has two-factor sign-in on; then only the set-up card is shown.
  const [needsTwoFactor, setNeedsTwoFactor] = useState(false);
  const [health, setHealth] = useState<SchoolPaymentsHealth[] | null>(null);
  const [healthError, setHealthError] = useState('');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('ALL');
  const [visible, setVisible] = useState(PAGE_SIZE);

  const loadHealth = useCallback(() => {
    setHealthError('');
    getPaymentsHealth()
      .then(setHealth)
      .catch(() => setHealthError("Couldn't check the schools' payments."));
  }, []);

  const load = useCallback(() => {
    setError('');
    listPlatformSchools()
      .then((rows) => {
        setNeedsTwoFactor(false);
        setSchools(rows);
        loadHealth();
      })
      .catch((err) => {
        if (axios.isAxiosError(err) && err.response?.status === 403) setNeedsTwoFactor(true);
        else setError("Couldn't load the schools.");
      });
  }, [loadHealth]);
  useEffect(load, [load]);

  const healthById = new Map((health ?? []).map((h) => [h.school_id, h]));
  const q = query.trim().toLowerCase();
  const filtered = (schools ?? []).filter((s) => {
    if (q && !s.name.toLowerCase().includes(q) && !s.contact_email.toLowerCase().includes(q)) return false;
    if (filter === 'RENEW') return s.status === 'GRACE' || s.status === 'EXPIRED';
    if (filter === 'SUSPENDED') return s.status === 'SUSPENDED';
    if (filter === 'PAYMENTS') {
      const h = healthById.get(s.id);
      return !!h && (h.severity === 'bad' || h.severity === 'warn');
    }
    return true;
  });

  const counts = (schools ?? []).reduce<Record<string, number>>((acc, s) => ({ ...acc, [s.status]: (acc[s.status] ?? 0) + 1 }), {});

  return (
    <div className="min-h-dvh">
      <header className="flex items-center justify-between px-4 sm:px-8 py-4 border-b border-white/[0.07]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-700 to-cyan flex items-center justify-center">
            <BookOpen className="w-4 h-4 text-[#06110B]" strokeWidth={2.25} />
          </div>
          <span className="font-display text-lg font-semibold text-ink-900">Ledgr</span>
          <span className="text-xs text-ink-400 border border-white/10 rounded-full px-2 py-0.5 ml-1">Platform</span>
        </div>
        <button
          onClick={() => {
            void logout();
            navigate('/');
          }}
          className="flex items-center gap-2 text-sm text-ink-600 hover:text-ink-900 transition-colors"
          aria-label="Sign out"
        >
          <span className="hidden sm:inline">{user?.full_name ?? user?.email}</span>
          <LogOut className="w-4 h-4" strokeWidth={2} />
        </button>
      </header>

      <main className="px-4 sm:px-8 py-6 max-w-[1000px] mx-auto flex flex-col gap-5">
        {needsTwoFactor ? (
          <OperatorTwoFactor onEnabled={load} />
        ) : (
        <>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="font-display text-3xl text-ink-900">Schools and billing</h1>
            <p className="text-sm text-ink-600 mt-1">Renew, start a trial, or switch a school off. Parents can always pay, whatever the status.</p>
          </div>
          {!adding && (
            <button
              onClick={() => {
                setNotice('');
                setAdding(true);
              }}
              className="flex items-center gap-1.5 rounded-full bg-lime text-[#0B1203] font-semibold text-sm px-4 py-2"
            >
              <Plus className="w-4 h-4" strokeWidth={2.5} />
              Add school
            </button>
          )}
        </div>

        {notice && <div role="status" className="bg-green-100 text-green rounded-md px-4 py-3 text-sm">{notice}</div>}
        {adding && (
          <AddSchoolForm
            onCancel={() => setAdding(false)}
            onCreated={(created) => {
              setSchools((cur) => [...(cur ?? []), created]);
              setAdding(false);
              setNotice(
                created.invite_sent
                  ? `${created.name} was created. ${created.contact_email} has an email with a link to set their password.`
                  : `${created.name} was created, but the invite email could not be sent. Ask ${created.contact_email} to use "Forgot password" on the sign-in page.`,
              );
            }}
          />
        )}

        {schools && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              ['Schools', schools.length],
              ['In date', (counts.ACTIVE ?? 0) + (counts.TRIAL ?? 0)],
              ['Needs renewing', (counts.GRACE ?? 0) + (counts.EXPIRED ?? 0)],
              ['Suspended', counts.SUSPENDED ?? 0],
            ].map(([label, n]) => (
              <DxCard key={label as string} className="p-4">
                <p className="text-xs text-ink-600">{label}</p>
                <p className="figure text-2xl text-ink-900 mt-1">{n}</p>
              </DxCard>
            ))}
          </div>
        )}

        {error && (
          <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm flex items-center justify-between">
            {error}
            <button onClick={load} className="underline">Try again</button>
          </div>
        )}
        {!schools && !error && <p className="text-sm text-ink-600">Loading…</p>}
        {schools?.length === 0 && <p className="text-sm text-ink-600">No schools yet.</p>}
        {schools && schools.length > 0 && (
          <PaymentsHealthPanel
            rows={health}
            error={healthError}
            onRefresh={loadHealth}
            onOpenSchool={(name) => {
              setQuery(name);
              setFilter('ALL');
              setVisible(PAGE_SIZE);
            }}
          />
        )}
        {schools && schools.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="search"
              aria-label="Search schools"
              placeholder="Search by school or admin email"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setVisible(PAGE_SIZE);
              }}
              className="flex-1 min-w-[14rem] rounded-full bg-white/[0.05] border border-white/[0.08] px-4 py-2 text-sm text-ink-900"
            />
            <div role="group" aria-label="Filter schools" className="flex flex-wrap gap-2">
              {FILTERS.map((f) => (
                <button
                  key={f.value}
                  aria-pressed={filter === f.value}
                  onClick={() => {
                    setFilter(f.value);
                    setVisible(PAGE_SIZE);
                  }}
                  className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${filter === f.value ? 'border-lime/60 text-lime' : 'border-white/[0.1] text-ink-900 hover:border-lime/50'}`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
        )}
        {schools && schools.length > 0 && filtered.length === 0 && <p className="text-sm text-ink-600">No schools match.</p>}
        {filtered.slice(0, visible).map((s) => (
          <SchoolCard
            key={s.id}
            school={s}
            onChange={(updated) => setSchools((cur) => cur?.map((x) => (x.id === updated.id ? updated : x)) ?? null)}
            onSchoolChanged={load}
          />
        ))}
        {filtered.length > visible && (
          <button onClick={() => setVisible((v) => v + PAGE_SIZE)} className="self-center rounded-full border border-white/[0.1] px-4 py-2 text-sm text-ink-900 hover:border-lime/50 transition-colors">
            Show {Math.min(PAGE_SIZE, filtered.length - visible)} more ({filtered.length - visible} not shown)
          </button>
        )}
        </>
        )}
      </main>
    </div>
  );
}
