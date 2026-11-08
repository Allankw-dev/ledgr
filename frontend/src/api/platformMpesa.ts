import { apiClient } from './client';

export type MpesaMode = 'OFF' | 'GLOBAL' | 'OWN';
export type MpesaEnvironment = 'SANDBOX' | 'PRODUCTION';

/** Everything about a school's M-Pesa set-up EXCEPT its secrets, which the server never sends back. */
export interface MpesaAccountStatus {
  school_id: string;
  mode: MpesaMode;
  has_account: boolean;
  environment: MpesaEnvironment | null;
  shortcode: string | null;
  tested_at: string | null;
  c2b_registered_at: string | null;
  last_error: string | null;
  global_configured: boolean;
  addresses_ready: boolean;
  other_schools_on_global: number;
}

export interface MpesaActionResult {
  ok: boolean;
  message: string;
  status: MpesaAccountStatus;
}

/** Secrets are write-only: leave one out (or blank) to keep what is saved. */
export interface MpesaAccountInput {
  environment: MpesaEnvironment;
  shortcode: string;
  consumer_key?: string;
  consumer_secret?: string;
  passkey?: string;
}

const base = (schoolId: string) => `/api/platform/schools/${schoolId}/mpesa`;

export async function getSchoolMpesa(schoolId: string): Promise<MpesaAccountStatus> {
  const { data } = await apiClient.get<MpesaAccountStatus>(base(schoolId));
  return data;
}

export async function saveSchoolMpesa(schoolId: string, body: MpesaAccountInput): Promise<MpesaActionResult> {
  const { data } = await apiClient.put<MpesaActionResult>(base(schoolId), body);
  return data;
}

export async function testSchoolMpesa(schoolId: string): Promise<MpesaActionResult> {
  const { data } = await apiClient.post<MpesaActionResult>(`${base(schoolId)}/test`);
  return data;
}

export async function registerSchoolMpesaUrls(schoolId: string): Promise<MpesaActionResult> {
  const { data } = await apiClient.post<MpesaActionResult>(`${base(schoolId)}/register-urls`);
  return data;
}

export async function setSchoolMpesaMode(schoolId: string, mode: MpesaMode, confirmShared = false): Promise<MpesaActionResult> {
  const { data } = await apiClient.post<MpesaActionResult>(`${base(schoolId)}/mode`, { mode, ...(confirmShared ? { confirm_shared: true } : {}) });
  return data;
}

/** Gives the school a new private webhook address and kills the old one. Other schools are not touched. */
export async function rotateSchoolMpesaAddress(schoolId: string): Promise<MpesaActionResult> {
  const { data } = await apiClient.post<MpesaActionResult>(`${base(schoolId)}/rotate-address`);
  return data;
}

export async function removeSchoolMpesa(schoolId: string): Promise<MpesaActionResult> {
  const { data } = await apiClient.delete<MpesaActionResult>(base(schoolId));
  return data;
}
