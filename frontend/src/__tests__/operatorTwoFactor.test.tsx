import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OperatorTwoFactor } from '../components/OperatorTwoFactor';
import * as api from '../api/auth';

vi.mock('../api/auth');

describe('OperatorTwoFactor', () => {
  beforeEach(() => vi.resetAllMocks());

  it('starts with only the set-up button, then shows the secret and a code box', async () => {
    vi.mocked(api.setup2FA).mockResolvedValue({ secret: 'JBSWY3DPEHPK3PXP', provisioning_uri: 'otpauth://totp/Ledgr:op?secret=JBSWY3DPEHPK3PXP' });
    render(<OperatorTwoFactor onEnabled={() => {}} />);
    expect(screen.queryByLabelText(/6-digit code/)).toBeNull();
    fireEvent.click(screen.getByText('Set up two-factor sign-in'));
    await screen.findByText('JBSWY3DPEHPK3PXP');
    expect(screen.getByLabelText(/6-digit code/)).toBeTruthy();
  });

  it('only allows a full 6-digit code, then tells the page it is on', async () => {
    vi.mocked(api.setup2FA).mockResolvedValue({ secret: 'SECRET', provisioning_uri: 'otpauth://x' });
    vi.mocked(api.enable2FA).mockResolvedValue({ enabled: true });
    const onEnabled = vi.fn();
    render(<OperatorTwoFactor onEnabled={onEnabled} />);
    fireEvent.click(screen.getByText('Set up two-factor sign-in'));
    const box = (await screen.findByLabelText(/6-digit code/)) as HTMLInputElement;
    const turnOn = screen.getByText('Turn on') as HTMLButtonElement;

    fireEvent.change(box, { target: { value: '12ab34' } });
    expect(box.value).toBe('1234');
    expect(turnOn.disabled).toBe(true);

    fireEvent.change(box, { target: { value: '123456' } });
    expect(turnOn.disabled).toBe(false);
    fireEvent.click(turnOn);
    await waitFor(() => expect(onEnabled).toHaveBeenCalledTimes(1));
    expect(api.enable2FA).toHaveBeenCalledWith('123456');
  });

  it('shows an error and stays on the card when the code is wrong', async () => {
    vi.mocked(api.setup2FA).mockResolvedValue({ secret: 'SECRET', provisioning_uri: 'otpauth://x' });
    vi.mocked(api.enable2FA).mockRejectedValue(new Error('401'));
    const onEnabled = vi.fn();
    render(<OperatorTwoFactor onEnabled={onEnabled} />);
    fireEvent.click(screen.getByText('Set up two-factor sign-in'));
    fireEvent.change(await screen.findByLabelText(/6-digit code/), { target: { value: '000000' } });
    fireEvent.click(screen.getByText('Turn on'));
    await screen.findByText(/Incorrect code/);
    expect(onEnabled).not.toHaveBeenCalled();
  });
});
