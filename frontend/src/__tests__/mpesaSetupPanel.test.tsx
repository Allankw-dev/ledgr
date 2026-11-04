import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MpesaSetupPanel } from '../components/MpesaSetupPanel';
import * as api from '../api/platformMpesa';
import type { MpesaAccountStatus, MpesaActionResult } from '../api/platformMpesa';

vi.mock('../api/platformMpesa');

const status = (over: Partial<MpesaAccountStatus> = {}): MpesaAccountStatus => ({
  school_id: 'sc1', mode: 'OFF', has_account: false, environment: null, shortcode: null, tested_at: null,
  c2b_registered_at: null, last_error: null, global_configured: true, addresses_ready: true, other_schools_on_global: 0, ...over,
});
const result = (over: Partial<MpesaAccountStatus> = {}, ok = true, message = 'Saved.'): MpesaActionResult => ({ ok, message, status: status(over) });

const SAVED = { has_account: true, environment: 'PRODUCTION', shortcode: '111111' } as const;

function renderPanel() {
  return render(<MpesaSetupPanel schoolId="sc1" schoolName="Greenfield Academy" />);
}
const field = (label: RegExp) => screen.getByLabelText(label) as HTMLInputElement;

describe('MpesaSetupPanel', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('starts as Off, with nothing that could switch the school onto an untried paybill', async () => {
    vi.mocked(api.getSchoolMpesa).mockResolvedValue(status());
    renderPanel();
    await screen.findByText(/Online M-Pesa for Greenfield Academy/);
    expect(screen.getByText('Off', { selector: 'strong' })).toBeTruthy();
    expect((screen.getByText(/Use this school.s own paybill/) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByText('Test connection') as HTMLButtonElement).disabled).toBe(true); // nothing saved yet
  });

  it('keeps the three secrets in password fields, sends all of them the first time, then clears them', async () => {
    vi.mocked(api.getSchoolMpesa).mockResolvedValue(status());
    vi.mocked(api.saveSchoolMpesa).mockResolvedValue(result(SAVED));
    renderPanel();
    await screen.findByText(/Online M-Pesa for/);
    for (const label of [/Consumer key/, /Consumer secret/, /Passkey/]) expect(field(label).type).toBe('password');
    fireEvent.change(field(/Paybill number/), { target: { value: '111111' } });
    fireEvent.change(screen.getByLabelText(/Environment/), { target: { value: 'PRODUCTION' } });
    fireEvent.change(field(/Consumer key/), { target: { value: ' KEY123456 ' } });
    fireEvent.change(field(/Consumer secret/), { target: { value: 'SECRET123456' } });
    fireEvent.change(field(/Passkey/), { target: { value: 'PASSKEY123456' } });
    fireEvent.click(screen.getByText('Save details'));
    await waitFor(() =>
      expect(api.saveSchoolMpesa).toHaveBeenCalledWith('sc1', {
        environment: 'PRODUCTION', shortcode: '111111', consumer_key: 'KEY123456', consumer_secret: 'SECRET123456', passkey: 'PASSKEY123456',
      }),
    );
    await waitFor(() => expect(field(/Consumer key/).value).toBe(''));
    expect(field(/Consumer secret/).value).toBe('');
    expect(field(/Passkey/).value).toBe('');
    expect(document.body.textContent).not.toContain('SECRET123456'); // nothing ever echoes a secret back
  });

  it('leaving a secret blank on a later edit sends nothing for it, so the saved one is kept', async () => {
    vi.mocked(api.getSchoolMpesa).mockResolvedValue(status({ ...SAVED }));
    vi.mocked(api.saveSchoolMpesa).mockResolvedValue(result({ ...SAVED, shortcode: '111112' }));
    renderPanel();
    await screen.findByText(/Online M-Pesa for/);
    expect(field(/Paybill number/).value).toBe('111111'); // the non-secret details come back
    expect(field(/Passkey/).placeholder).toMatch(/Saved/);
    expect(field(/Passkey/).required).toBe(false);
    fireEvent.change(field(/Paybill number/), { target: { value: '111112' } });
    fireEvent.click(screen.getByText('Save details'));
    await waitFor(() => expect(api.saveSchoolMpesa).toHaveBeenCalledTimes(1));
    expect(vi.mocked(api.saveSchoolMpesa).mock.calls[0][1]).toEqual({ environment: 'PRODUCTION', shortcode: '111112' });
  });

  it('only lets the school go onto its own paybill after a successful test, then switches it', async () => {
    vi.mocked(api.getSchoolMpesa).mockResolvedValue(status({ ...SAVED }));
    vi.mocked(api.testSchoolMpesa).mockResolvedValue(result({ ...SAVED, tested_at: '2026-11-01T10:00:00Z' }, true, 'Connected. Safaricom accepted the key and secret.'));
    vi.mocked(api.setSchoolMpesaMode).mockResolvedValue(result({ ...SAVED, tested_at: '2026-11-01T10:00:00Z', mode: 'OWN' }, true, 'M-Pesa for this school is set to the school\'s own paybill.'));
    renderPanel();
    await screen.findByText(/Online M-Pesa for/);
    const own = () => screen.getByText(/Use this school.s own paybill/) as HTMLButtonElement;
    expect(own().disabled).toBe(true);
    fireEvent.click(screen.getByText('Test connection'));
    await screen.findByText(/Safaricom accepted the key and secret/);
    await waitFor(() => expect(own().disabled).toBe(false));
    fireEvent.click(own());
    await waitFor(() => expect(api.setSchoolMpesaMode).toHaveBeenCalledWith('sc1', 'OWN'));
    await screen.findByText("This school's own paybill", { selector: 'strong' });
  });

  it('shows a failed test plainly, as an alert', async () => {
    vi.mocked(api.getSchoolMpesa).mockResolvedValue(status({ ...SAVED }));
    vi.mocked(api.testSchoolMpesa).mockResolvedValue(result({ ...SAVED, last_error: 'Safaricom rejected the consumer key and secret.' }, false, 'Safaricom rejected the consumer key and secret for the live environment.'));
    renderPanel();
    await screen.findByText(/Online M-Pesa for/);
    fireEvent.click(screen.getByText('Test connection'));
    expect((await screen.findByRole('alert')).textContent).toMatch(/rejected the consumer key and secret/);
  });

  it('will not offer the server-wide paybill when the server settings are incomplete, and explains why registering is blocked', async () => {
    vi.mocked(api.getSchoolMpesa).mockResolvedValue(status({ ...SAVED, global_configured: false, addresses_ready: false }));
    renderPanel();
    await screen.findByText(/Online M-Pesa for/);
    expect((screen.getByText('Use the server-wide paybill') as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByText(/Register paybill addresses/) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/does not know its own public address/)).toBeTruthy();
  });

  it('asks before removing saved details, and does nothing if the answer is no', async () => {
    vi.mocked(api.getSchoolMpesa).mockResolvedValue(status({ ...SAVED }));
    vi.mocked(api.removeSchoolMpesa).mockResolvedValue(result({ mode: 'OFF' }, true, 'The saved M-Pesa details were removed.'));
    renderPanel();
    await screen.findByText(/Online M-Pesa for/);
    vi.mocked(window.confirm).mockReturnValueOnce(false);
    fireEvent.click(screen.getByText('Remove saved details'));
    expect(api.removeSchoolMpesa).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText('Remove saved details'));
    await waitFor(() => expect(api.removeSchoolMpesa).toHaveBeenCalledWith('sc1'));
  });

  it('says so when the settings cannot be loaded', async () => {
    vi.mocked(api.getSchoolMpesa).mockRejectedValue(new Error('boom'));
    renderPanel();
    expect((await screen.findByRole('alert')).textContent).toMatch(/Couldn.t load/);
  });
});
