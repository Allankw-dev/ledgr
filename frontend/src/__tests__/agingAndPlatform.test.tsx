import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AxiosError } from 'axios';
import type { AgingReport } from '../api/aging';
import type { CreatedSchool, PlatformSchool } from '../api/subscription';

vi.mock('../components/AppShell', () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock('../api/aging', () => ({ getAgingReport: vi.fn(), downloadAgingCsv: vi.fn() }));
vi.mock('../api/subscription', () => ({ listPlatformSchools: vi.fn(), updateSchoolSubscription: vi.fn(), getMySubscription: vi.fn(), createSchool: vi.fn() }));
vi.mock('../store/authStore', () => ({
  useAuthStore: (sel: (s: unknown) => unknown) => sel({ logout: vi.fn(), user: { full_name: 'Allan', email: 'a@x.test' } }),
}));

import { downloadAgingCsv, getAgingReport } from '../api/aging';
import { createSchool, listPlatformSchools, updateSchoolSubscription } from '../api/subscription';
import { AgingPage } from '../pages/AgingPage';
import { PlatformPage } from '../pages/PlatformPage';

const report = (over: Partial<AgingReport> = {}): AgingReport => ({
  buckets: [
    { key: 'current', label: 'Not yet due', count: 1, amount: '500' },
    { key: '1-30', label: '1 to 30 days late', count: 2, amount: '1600' },
    { key: '31-60', label: '31 to 60 days late', count: 0, amount: '0' },
    { key: '61-90', label: '61 to 90 days late', count: 0, amount: '0' },
    { key: '90+', label: 'Over 90 days late', count: 1, amount: '3000' },
  ],
  total_count: 4,
  total_outstanding: '5100',
  rows: [
    { invoice_id: 'i1', student_id: 's1', student_name: 'Danny Otieno', admission_number: 'A1', class_name: 'Grade 5', term_name: 'Term 1', due_date: '2026-01-10T00:00:00Z', days_overdue: 120, balance: '3000', bucket: '90+' },
  ],
  truncated: false,
  ...over,
});

describe('AgingPage', () => {
  beforeEach(() => {
    vi.mocked(getAgingReport).mockReset();
    vi.mocked(downloadAgingCsv).mockReset();
  });

  it('shows the five groups, the worst invoice first, and the total owed', async () => {
    vi.mocked(getAgingReport).mockResolvedValue(report());
    render(<MemoryRouter><AgingPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('Danny Otieno')).toBeTruthy());
    for (const label of ['Not yet due', '1 to 30 days late', 'Over 90 days late']) expect(screen.getByText(label)).toBeTruthy();
    expect(screen.getByText('120 days late')).toBeTruthy();
    expect(document.body.textContent).toMatch(/5,100 owed across 4 invoices/);
  });

  it('tapping a group asks for just that group, and tapping it again goes back to all', async () => {
    vi.mocked(getAgingReport).mockResolvedValue(report());
    render(<MemoryRouter><AgingPage /></MemoryRouter>);
    await waitFor(() => screen.getByText('Danny Otieno'));
    expect(getAgingReport).toHaveBeenLastCalledWith(null);

    // After selecting, the group's name also appears as the list heading, so find the card by its role.
    const card = () => screen.getByRole('button', { name: /Over 90 days late/ });
    fireEvent.click(card());
    await waitFor(() => expect(getAgingReport).toHaveBeenLastCalledWith('90+'));
    expect(card().getAttribute('aria-pressed')).toBe('true');

    fireEvent.click(card());
    await waitFor(() => expect(getAgingReport).toHaveBeenLastCalledWith(null));
  });

  it('says so when nothing is owed, and offers no export then', async () => {
    vi.mocked(getAgingReport).mockResolvedValue(report({ total_count: 0, total_outstanding: '0', rows: [], buckets: report().buckets.map((b) => ({ ...b, count: 0, amount: '0' })) }));
    render(<MemoryRouter><AgingPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('Nothing is owed. Every invoice is paid.')).toBeTruthy());
    expect((screen.getByText('Export CSV').closest('button') as HTMLButtonElement).disabled).toBe(true);
  });

  it('tells the person when the list was cut short, and fails clearly', async () => {
    vi.mocked(getAgingReport).mockResolvedValue(report({ truncated: true }));
    const { unmount } = render(<MemoryRouter><AgingPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/Export the CSV for the full list/)).toBeTruthy());
    unmount();
    vi.mocked(getAgingReport).mockRejectedValue(new Error('boom'));
    render(<MemoryRouter><AgingPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/Couldn't load the aging report/));
  });
});

const school = (over: Partial<PlatformSchool> = {}): PlatformSchool => ({
  id: 'sc1', name: 'Greenfield Academy', contact_email: 'bursar@greenfield.test', created_at: '2026-01-01T00:00:00Z', plan: 'STANDARD',
  subscription_status: 'ACTIVE', status: 'ACTIVE', read_only: false, days_left: 40, trial_ends_at: null, paid_until: '2026-11-20T00:00:00Z',
  learner_count: 412, learner_limit: 500, ...over,
});

describe('PlatformPage', () => {
  beforeEach(() => {
    vi.mocked(listPlatformSchools).mockReset();
    vi.mocked(updateSchoolSubscription).mockReset();
    vi.mocked(createSchool).mockReset();
  });

  it('lists each school with its standing and learner usage', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([school(), school({ id: 'sc2', name: 'Hillside', status: 'EXPIRED', subscription_status: 'ACTIVE', days_left: 0, learner_limit: null, learner_count: 90 })]);
    render(<MemoryRouter><PlatformPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('Greenfield Academy')).toBeTruthy());
    expect(screen.getByText('Hillside')).toBeTruthy();
    expect(document.body.textContent).toMatch(/412 \/ 500/);
    expect(document.body.textContent).toMatch(/40d left/);
    expect(screen.getByText('EXPIRED')).toBeTruthy();
  });

  it('renewing sends the months and shows the result straight away', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([school({ status: 'EXPIRED', days_left: 0 })]);
    vi.mocked(updateSchoolSubscription).mockResolvedValue(school({ days_left: 120 }));
    render(<MemoryRouter><PlatformPage /></MemoryRouter>);
    await waitFor(() => screen.getByText('Greenfield Academy'));
    fireEvent.click(screen.getByText('+4 months'));
    await waitFor(() => expect(updateSchoolSubscription).toHaveBeenCalledWith('sc1', { extend_months: 4 }));
    await waitFor(() => expect(screen.getByText('ACTIVE')).toBeTruthy());
  });

  it('suspending asks first, and does nothing if you say no', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([school()]);
    vi.mocked(updateSchoolSubscription).mockResolvedValue(school({ status: 'SUSPENDED', subscription_status: 'SUSPENDED' }));
    render(<MemoryRouter><PlatformPage /></MemoryRouter>);
    await waitFor(() => screen.getByText('Greenfield Academy'));

    vi.spyOn(window, 'confirm').mockReturnValueOnce(false);
    fireEvent.click(screen.getByText('Suspend'));
    expect(updateSchoolSubscription).not.toHaveBeenCalled();

    vi.spyOn(window, 'confirm').mockReturnValueOnce(true);
    fireEvent.click(screen.getByText('Suspend'));
    await waitFor(() => expect(updateSchoolSubscription).toHaveBeenCalledWith('sc1', { status: 'SUSPENDED' }));
    await waitFor(() => expect(screen.getByText('Reactivate')).toBeTruthy());
  });

  it('editing can clear the learner limit and sets paid-until to the end of that day', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([school()]);
    vi.mocked(updateSchoolSubscription).mockResolvedValue(school({ learner_limit: null }));
    render(<MemoryRouter><PlatformPage /></MemoryRouter>);
    await waitFor(() => screen.getByText('Greenfield Academy'));
    fireEvent.click(screen.getByText('Edit'));
    fireEvent.change(screen.getByLabelText(/Learner limit/), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText(/Paid until/), { target: { value: '2027-03-31' } });
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => expect(updateSchoolSubscription).toHaveBeenCalledWith('sc1', { paid_until: '2027-03-31T23:59:59Z', learner_limit: null }));
  });

  const fillAddSchool = () => {
    fireEvent.click(screen.getByText('Add school'));
    fireEvent.change(screen.getByLabelText(/School name/), { target: { value: '  Brand New Academy ' } });
    fireEvent.change(screen.getByLabelText(/Administrator's full name/), { target: { value: 'Ada Admin' } });
    fireEvent.change(screen.getByLabelText(/Administrator's email/), { target: { value: 'ada@newschool.test' } });
    fireEvent.change(screen.getByLabelText(/Learner limit/), { target: { value: '150' } });
  };
  const created = (over: Partial<CreatedSchool> = {}): CreatedSchool => ({
    ...school({ id: 'sc9', name: 'Brand New Academy', contact_email: 'ada@newschool.test', status: 'TRIAL', subscription_status: 'TRIAL', learner_count: 0, learner_limit: 150 }),
    invite_sent: true,
    ...over,
  });

  it('adds a school, shows it straight away and says the admin was emailed', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([school()]);
    vi.mocked(createSchool).mockResolvedValue(created());
    render(<MemoryRouter><PlatformPage /></MemoryRouter>);
    await waitFor(() => screen.getByText('Greenfield Academy'));
    fillAddSchool();
    fireEvent.click(screen.getByText('Create school'));
    await waitFor(() =>
      expect(createSchool).toHaveBeenCalledWith({
        school_name: 'Brand New Academy',
        admin_full_name: 'Ada Admin',
        admin_email: 'ada@newschool.test',
        trial_days: 30,
        learner_limit: 150,
      }),
    );
    await waitFor(() => expect(screen.getByText('Brand New Academy')).toBeTruthy());
    expect(screen.getByRole('status').textContent).toMatch(/ada@newschool\.test has an email/);
    expect(screen.queryByText('Create school')).toBeNull(); // the form closed
  });

  it('tells the operator what to do when the invite email could not be sent', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([]);
    vi.mocked(createSchool).mockResolvedValue(created({ invite_sent: false }));
    render(<MemoryRouter><PlatformPage /></MemoryRouter>);
    await waitFor(() => screen.getByText('Add school'));
    fillAddSchool();
    fireEvent.click(screen.getByText('Create school'));
    await waitFor(() => expect(screen.getByRole('status').textContent).toMatch(/Forgot password/));
  });

  it('keeps the form open and shows the reason when the school cannot be created', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([]);
    const err = new AxiosError('Request failed', '409', undefined, undefined, { status: 409, data: { detail: 'An account with that email already exists' } } as never);
    vi.mocked(createSchool).mockRejectedValue(err);
    render(<MemoryRouter><PlatformPage /></MemoryRouter>);
    await waitFor(() => screen.getByText('Add school'));
    fillAddSchool();
    fireEvent.click(screen.getByText('Create school'));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/already exists/));
    expect(screen.getByText('Create school')).toBeTruthy();
  });

  it('shows a retry when the list will not load', async () => {
    vi.mocked(listPlatformSchools).mockRejectedValue(new Error('403'));
    render(<MemoryRouter><PlatformPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/Couldn't load the schools/));
    expect(screen.getByText('Try again')).toBeTruthy();
  });
});
