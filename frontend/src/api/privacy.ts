import { apiClient } from './client';

export interface PrivacySettings {
  email_opt_out: boolean;
  terms_accepted_at: string | null;
  terms_version: string | null;
}

export async function getPrivacySettings(): Promise<PrivacySettings> {
  const { data } = await apiClient.get<PrivacySettings>('/api/privacy/me');
  return data;
}

export async function setEmailOptOut(email_opt_out: boolean): Promise<{ email_opt_out: boolean }> {
  const { data } = await apiClient.put('/api/privacy/me/email-preferences', { email_opt_out });
  return data;
}

export async function deleteMyAccount(password: string, confirm: string): Promise<void> {
  await apiClient.post('/api/privacy/me/delete-account', { password, confirm });
}

// The unsubscribe page is opened from an email link, usually while signed out. These go through apiClient too:
// the token in the link is what authorises them, and a missing session simply isn't sent.
export async function unsubscribeWithToken(token: string): Promise<void> {
  await apiClient.post('/api/privacy/unsubscribe', { token });
}

export async function resubscribeWithToken(token: string): Promise<void> {
  await apiClient.post('/api/privacy/resubscribe', { token });
}
