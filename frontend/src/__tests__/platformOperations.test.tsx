import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { PlatformSchool, SchoolPaymentsHealth, SubscriptionPaymentList } from '../api/subscription';
import type { MpesaAccountStatus } from '../api/platformMpesa';

vi.mock('../components/AppShell', () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock('../api/subscription', () => ({
  listPlatformSchools: vi.fn(),
  updateSchoolSubscription: vi.fn(),
  createSchool: vi.fn(),
  getMySubscription: vi.fn(),
  getPaymentsHealth: vi.fn(),
  listSubscriptionPayments: vi.fn(),
  recordSubscriptionPayment: vi.fn(),
  voidSubscriptionPayment: vi.fn(),
}));
vi.mock('../api/platformMpesa', () => ({
  getSchoolMpesa: vi.fn(), saveSchoolMpesa: vi.fn(), testSchoolMpesa: vi.fn(), registerSchoolMpesaUrls: vi.fn(),
  setSchoolMpesaMode: vi.fn(), removeSchoolMpesa: vi.fn(), rotateSchoolMpesaAddress: vi.fn(),
}));
vi.mock('../store/authStore', () => ({
  useAuthStore: (sel: (s: unknown) => unknown) => sel({ logout: vi.fn(), user: { full_name: 'Allan', email: 'a@x.test' } }),
}));

import { getPaymentsHealth, listPlatformSchools, listSubscriptionPayments, recordSubscriptionPayment, voidSubscriptionPayment } from '../api/subscription';
import { getSchoolMpesa, rotateSchoolMpesaAddress, setSchoolMpesaMode } from '../api/platformMpesa';
import { PlatformPage } from '../pages/PlatformPage';

const school = (over: Partial<PlatformSchool> = {}): PlatformSchool => ({
  id: 'sc1', name: 'Greenfield Academy', contact_email: 'bursar@greenfield.test', created_at: '2026-01-01T00:00:00Z', plan: 'STANDARD',
  subscription_status: 'ACTIVE', status: 'ACTIVE', read_only: false, days_left: 40, trial_ends_at: null, paid_until: '2026-12-15T00:00:00Z',
  learner_count: 412, learner_limit: 500, last_payment_on: null, ...over,
});

const health = (over: Partial<SchoolPaymentsHealth> = {}): SchoolPaymentsHealth => ({
  school_id: 'sc1', school_name: 'Greenfield Academy', currency: 'KES', subscription_status: 'ACTIVE', read_only: false, mpesa_mode: 'OWN',
  environment: 'PRODUCTION', shortcode: '111111', tested_at: '2026-11-01T00:00:00Z', c2b_registered_at: '2026-11-01T00:00:00Z', last_error: null,
  confirmed_30d_count: 12, confirmed_30d_amount: '84000.00', last_confirmed_at: '2026-11-05T09:00:00Z', stuck_pending: 0, failed_7d: 0,
  mismatches: 0, unallocated: 0, unmatched_c2b: 0, shared_paybill: false, severity: 'ok', attention: [], ...over,
});

const emptyBook = (over: Partial<SubscriptionPaymentList> = {}): SubscriptionPaymentList => ({ payments: [], total_paid: '0', currency: 'KES', ...over });

const bookRow = (over = {}) => ({
  id: 'p1', school_id: 'sc1', amount: '15000.00', currency: 'KES', method: 'MPESA' as const, reference: 'SJK4X2L9QP', paid_on: '2026-11-04T12:00:00Z',
  months_added: 3, note: null, created_at: '2026-11-04T12:00:00Z', voided_at: null, void_reason: null, ...over,
});

const renderPage = () => render(<MemoryRouter><PlatformPage /></MemoryRouter>);

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getPaymentsHealth).mockResolvedValue([]);
  vi.mocked(listSubscriptionPayments).mockResolvedValue(emptyBook());
});

describe('recording what a school paid', () => {
  it('books the payment with its months, says what happened, and refreshes the school', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([school()]);
    vi.mocked(recordSubscriptionPayment).mockResolvedValue(bookRow());
    renderPage();
    await waitFor(() => screen.getByText('Greenfield Academy'));
    expect(screen.getByText('Nothing recorded')).toBeTruthy();
    fireEvent.click(screen.getByText('Record payment'));

    await waitFor(() => screen.getByLabelText(/^Amount/));
    fireEvent.change(screen.getByLabelText(/^Amount/), { target: { value: '15000' } });
    fireEvent.change(screen.getByLabelText(/M-Pesa code/), { target: { value: ' SJK4X2L9QP ' } });
    fireEvent.change(screen.getByLabelText(/Months this covers/), { target: { value: '3' } });
    fireEvent.click(screen.getByText('Record payment')); // the form's button (the card's toggle now reads "Hide billing")

    await waitFor(() =>
      expect(recordSubscriptionPayment).toHaveBeenCalledWith('sc1', expect.objectContaining({ amount: '15000', method: 'MPESA', reference: 'SJK4X2L9QP', months: 3 })),
    );
    await waitFor(() => expect(screen.getByRole('status').textContent).toMatch(/Recorded KES 15,000\.00 and added 3 months/));
    expect(listPlatformSchools).toHaveBeenCalledTimes(2); // the card's paid-until is re-read
  });

  it('asks for a reference for M-Pesa and bank, but not for cash', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([school()]);
    renderPage();
    await waitFor(() => screen.getByText('Greenfield Academy'));
    fireEvent.click(screen.getByText('Record payment'));
    await waitFor(() => screen.getByLabelText(/How they paid/));
    expect((screen.getByLabelText(/M-Pesa code/) as HTMLInputElement).required).toBe(true);
    fireEvent.change(screen.getByLabelText(/How they paid/), { target: { value: 'CASH' } });
    expect((screen.getByLabelText(/Reference/) as HTMLInputElement).required).toBe(false);
    fireEvent.change(screen.getByLabelText(/How they paid/), { target: { value: 'BANK_TRANSFER' } });
    expect((screen.getByLabelText(/Bank reference/) as HTMLInputElement).required).toBe(true);
  });

  it("shows the server's reason when a payment is refused, for example a reference booked twice", async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([school()]);
    const { AxiosError } = await import('axios');
    vi.mocked(recordSubscriptionPayment).mockRejectedValue(
      new AxiosError('x', '409', undefined, undefined, { status: 409, data: { detail: 'That reference is already booked for this school.' } } as never),
    );
    renderPage();
    await waitFor(() => screen.getByText('Greenfield Academy'));
    fireEvent.click(screen.getByText('Record payment'));
    await waitFor(() => screen.getByLabelText(/^Amount/));
    fireEvent.change(screen.getByLabelText(/^Amount/), { target: { value: '100' } });
    fireEvent.change(screen.getByLabelText(/M-Pesa code/), { target: { value: 'DUP' } });
    fireEvent.click(screen.getByText('Record payment'));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/already booked/));
  });

  it('lists the book with a total, and voiding asks why and keeps the row struck through', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([school({ last_payment_on: '2026-11-04T12:00:00Z' })]);
    vi.mocked(listSubscriptionPayments).mockResolvedValue(emptyBook({ payments: [bookRow()], total_paid: '15000.00' }));
    vi.mocked(voidSubscriptionPayment).mockResolvedValue(bookRow({ voided_at: '2026-11-05T00:00:00Z', void_reason: 'entered twice' }));
    renderPage();
    await waitFor(() => screen.getByText('Greenfield Academy'));
    fireEvent.click(screen.getByText('Record payment'));
    await waitFor(() => screen.getByText('SJK4X2L9QP', { exact: false }));
    expect(screen.getByText(/Total paid:/).textContent).toMatch(/KES 15,000\.00/);

    fireEvent.click(screen.getByText('Entered by mistake'));
    const voidBtn = screen.getByText('Void it') as HTMLButtonElement;
    expect(voidBtn.disabled).toBe(true); // a reason is needed first
    fireEvent.change(screen.getByLabelText(/Why is this a mistake/), { target: { value: 'entered twice' } });
    vi.mocked(listSubscriptionPayments).mockResolvedValue(emptyBook({ payments: [bookRow({ voided_at: '2026-11-05T00:00:00Z', void_reason: 'entered twice' })] }));
    fireEvent.click(screen.getByText('Void it'));
    await waitFor(() => expect(voidSubscriptionPayment).toHaveBeenCalledWith('p1', 'entered twice'));
    await waitFor(() => expect(screen.getByText(/Voided: entered twice/)).toBeTruthy());
    expect(screen.getByRole('status').textContent).toMatch(/paid-until date was not changed/);
  });
});

describe('payments health', () => {
  const rows = [
    health({ school_id: 'sc2', school_name: 'Hillside', severity: 'bad', last_error: 'x', attention: ['Last Safaricom problem: rejected'] }),
    health({ school_id: 'sc3', school_name: 'Lakeview', severity: 'warn', attention: ['2 payment prompt(s) have been waiting more than 15 minutes'] }),
    health({ school_id: 'sc1', school_name: 'Greenfield Academy', severity: 'ok' }),
    health({ school_id: 'sc4', school_name: 'Quiet School', severity: 'info', mpesa_mode: 'OFF', attention: ['Online M-Pesa is off for this school'] }),
  ];
  const four = [school(), school({ id: 'sc2', name: 'Hillside' }), school({ id: 'sc3', name: 'Lakeview' }), school({ id: 'sc4', name: 'Quiet School' })];

  it('shows only the problems at first, worst first, and can show every school', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue(four);
    vi.mocked(getPaymentsHealth).mockResolvedValue(rows);
    renderPage();
    const panel = await waitFor(() => screen.getByRole('heading', { name: 'Payments health' }).closest('div')!.parentElement!.parentElement!);
    expect(within(panel).getByText(/1 broken, 1 needs a look/)).toBeTruthy();
    const items = within(panel).getAllByRole('listitem').filter((li) => li.querySelector('button'));
    expect(items.map((li) => li.querySelector('button')!.textContent)).toEqual(['Hillside', 'Lakeview']);
    expect(within(panel).queryByText('Quiet School')).toBeNull();
    fireEvent.click(within(panel).getByText('Show every school'));
    expect(within(panel).getByText('Quiet School')).toBeTruthy();
  });

  it('says so when nothing needs attention', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([school()]);
    vi.mocked(getPaymentsHealth).mockResolvedValue([health()]);
    renderPage();
    await waitFor(() => expect(screen.getByText(/Nothing needs your attention/)).toBeTruthy());
  });

  it('tapping a school narrows the list to it', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue(four);
    vi.mocked(getPaymentsHealth).mockResolvedValue(rows);
    renderPage();
    await waitFor(() => screen.getByRole('heading', { name: 'Payments health' }));
    const panelButtons = screen.getAllByRole('button', { name: 'Hillside' });
    fireEvent.click(panelButtons[0]);
    expect((screen.getByLabelText('Search schools') as HTMLInputElement).value).toBe('Hillside');
    expect(screen.getByRole('heading', { name: 'Hillside' })).toBeTruthy(); // its card is shown
    expect(screen.queryByRole('heading', { name: 'Lakeview' })).toBeNull(); // the other cards are not
  });

  it('a failed health check shows a retry and does not hide the schools', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([school()]);
    vi.mocked(getPaymentsHealth).mockRejectedValue(new Error('boom'));
    renderPage();
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/Couldn't check the schools' payments/));
    expect(screen.getByText('Greenfield Academy')).toBeTruthy();
  });
});

describe('finding a school among many', () => {
  const many = Array.from({ length: 25 }, (_, i) => school({ id: `s${i}`, name: `School ${String(i).padStart(2, '0')}`, contact_email: `admin${i}@x.test` }));

  it('shows 20 at a time and offers the rest', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue(many);
    renderPage();
    await waitFor(() => screen.getByText('School 00'));
    expect(screen.getByText('School 19')).toBeTruthy();
    expect(screen.queryByText('School 20')).toBeNull();
    fireEvent.click(screen.getByText(/Show 5 more/));
    expect(screen.getByText('School 24')).toBeTruthy();
  });

  it('searches by name or admin email', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue(many);
    renderPage();
    await waitFor(() => screen.getByText('School 00'));
    fireEvent.change(screen.getByLabelText('Search schools'), { target: { value: 'school 07' } });
    expect(screen.getByText('School 07')).toBeTruthy();
    expect(screen.queryByText('School 08')).toBeNull();
    fireEvent.change(screen.getByLabelText('Search schools'), { target: { value: 'admin12@' } });
    expect(screen.getByText('School 12')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Search schools'), { target: { value: 'nothing like this' } });
    expect(screen.getByText('No schools match.')).toBeTruthy();
  });

  it('filters to the schools that need renewing, are suspended, or have payment problems', async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([
      school({ id: 'a', name: 'Fine School' }),
      school({ id: 'b', name: 'Lapsed School', status: 'EXPIRED' }),
      school({ id: 'c', name: 'Off School', status: 'SUSPENDED', subscription_status: 'SUSPENDED' }),
      school({ id: 'd', name: 'Broken Pay School' }),
    ]);
    vi.mocked(getPaymentsHealth).mockResolvedValue([health({ school_id: 'd', school_name: 'Broken Pay School', severity: 'bad', attention: ['x'] })]);
    renderPage();
    await waitFor(() => screen.getByText('Fine School'));
    const pick = (name: string) => fireEvent.click(screen.getByRole('button', { name, pressed: false }));
    await waitFor(() => screen.getByRole('button', { name: 'Payment problems' }));
    pick('Needs renewing');
    expect(screen.getByText('Lapsed School')).toBeTruthy();
    expect(screen.queryByText('Fine School')).toBeNull();
    pick('Suspended');
    expect(screen.getByText('Off School')).toBeTruthy();
    expect(screen.queryByText('Lapsed School')).toBeNull();
    pick('Payment problems');
    expect(screen.getAllByText('Broken Pay School').length).toBeGreaterThan(0);
    expect(screen.queryByText('Off School')).toBeNull();
  });
});

describe('the M-Pesa panel safeguards', () => {
  const status = (over: Partial<MpesaAccountStatus> = {}): MpesaAccountStatus => ({
    school_id: 'sc1', mode: 'OFF', has_account: true, environment: 'PRODUCTION', shortcode: '111111', tested_at: '2026-11-01T00:00:00Z',
    c2b_registered_at: '2026-11-01T00:00:00Z', last_error: null, global_configured: true, addresses_ready: true, other_schools_on_global: 0, ...over,
  });
  const open = async () => {
    vi.mocked(listPlatformSchools).mockResolvedValue([school()]);
    renderPage();
    await waitFor(() => screen.getByText('Greenfield Academy'));
    fireEvent.click(screen.getByText('M-Pesa setup'));
    await waitFor(() => screen.getByText(/Online M-Pesa for Greenfield Academy/));
  };

  it('sharing the server-wide paybill with other schools needs an explicit yes', async () => {
    vi.mocked(getSchoolMpesa).mockResolvedValue(status({ other_schools_on_global: 2 }));
    vi.mocked(setSchoolMpesaMode).mockResolvedValue({ ok: true, message: 'ok', status: status({ mode: 'GLOBAL', other_schools_on_global: 2 }) });
    await open();
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false);
    fireEvent.click(screen.getByText('Use the server-wide paybill'));
    expect(setSchoolMpesaMode).not.toHaveBeenCalled();
    vi.spyOn(window, 'confirm').mockReturnValueOnce(true);
    fireEvent.click(screen.getByText('Use the server-wide paybill'));
    await waitFor(() => expect(setSchoolMpesaMode).toHaveBeenCalledWith('sc1', 'GLOBAL', true));
  });

  it('the first school on the server-wide paybill is not asked to confirm', async () => {
    vi.mocked(getSchoolMpesa).mockResolvedValue(status({ other_schools_on_global: 0 }));
    vi.mocked(setSchoolMpesaMode).mockResolvedValue({ ok: true, message: 'ok', status: status({ mode: 'GLOBAL' }) });
    const confirm = vi.spyOn(window, 'confirm');
    await open();
    fireEvent.click(screen.getByText('Use the server-wide paybill'));
    await waitFor(() => expect(setSchoolMpesaMode).toHaveBeenCalledWith('sc1', 'GLOBAL', false));
    expect(confirm).not.toHaveBeenCalled();
  });

  it('a school already sharing the paybill is warned about it', async () => {
    vi.mocked(getSchoolMpesa).mockResolvedValue(status({ mode: 'GLOBAL', other_schools_on_global: 1 }));
    await open();
    expect(screen.getByText(/shares the server-wide paybill with 1 other school/)).toBeTruthy();
  });

  it('rotating the webhook address asks first and only touches this school', async () => {
    vi.mocked(getSchoolMpesa).mockResolvedValue(status());
    vi.mocked(rotateSchoolMpesaAddress).mockResolvedValue({ ok: true, message: 'This school\'s webhook address was changed.', status: status({ c2b_registered_at: null }) });
    await open();
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false);
    fireEvent.click(screen.getByText('Rotate webhook address'));
    expect(rotateSchoolMpesaAddress).not.toHaveBeenCalled();
    vi.spyOn(window, 'confirm').mockReturnValueOnce(true);
    fireEvent.click(screen.getByText('Rotate webhook address'));
    await waitFor(() => expect(rotateSchoolMpesaAddress).toHaveBeenCalledWith('sc1'));
    await waitFor(() => expect(screen.getByRole('status').textContent).toMatch(/webhook address was changed/));
  });
});
