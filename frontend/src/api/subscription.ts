import { apiClient } from './client';

export type SubscriptionStatus = 'TRIAL' | 'ACTIVE' | 'GRACE' | 'EXPIRED' | 'SUSPENDED';

/** What a school's own staff see. */
export interface Subscription {
  status: SubscriptionStatus;
  read_only: boolean;
  days_left: number | null;
  ends_at: string | null;
  plan: string;
  learner_count: number;
  learner_limit: number | null;
  over_limit: boolean;
}

export async function getMySubscription(): Promise<Subscription> {
  const { data } = await apiClient.get<Subscription>('/api/subscription');
  return data;
}

/** One school, as the platform operator sees it. */
export interface PlatformSchool {
  id: string;
  name: string;
  contact_email: string;
  created_at: string;
  plan: string;
  subscription_status: 'TRIAL' | 'ACTIVE' | 'SUSPENDED';
  status: SubscriptionStatus;
  read_only: boolean;
  days_left: number | null;
  trial_ends_at: string | null;
  paid_until: string | null;
  learner_count: number;
  learner_limit: number | null;
  /** The school's most recent (non-voided) payment to the operator. */
  last_payment_on?: string | null;
}

/** Send only what should change. `null` clears a date or the learner limit. */
export interface SubscriptionUpdate {
  status?: 'TRIAL' | 'ACTIVE' | 'SUSPENDED';
  plan?: string;
  paid_until?: string | null;
  trial_ends_at?: string | null;
  learner_limit?: number | null;
  extend_months?: number;
  trial_days?: number;
}

export async function listPlatformSchools(): Promise<PlatformSchool[]> {
  const { data } = await apiClient.get<PlatformSchool[]>('/api/platform/schools');
  return data;
}

export async function updateSchoolSubscription(schoolId: string, body: SubscriptionUpdate): Promise<PlatformSchool> {
  const { data } = await apiClient.patch<PlatformSchool>(`/api/platform/schools/${schoolId}/subscription`, body);
  return data;
}

/** What the operator fills in to onboard a school. The admin gets an emailed link to set their own password. */
export interface CreateSchoolRequest {
  school_name: string;
  admin_full_name: string;
  admin_email: string;
  country?: string;
  currency?: string;
  plan?: string;
  learner_limit?: number;
  trial_days?: number;
}

/** The new school's row, plus whether the admin's set-password email actually went out. */
export interface CreatedSchool extends PlatformSchool {
  invite_sent: boolean;
}

export async function createSchool(body: CreateSchoolRequest): Promise<CreatedSchool> {
  const { data } = await apiClient.post<CreatedSchool>('/api/platform/schools', body);
  return data;
}

// ---- what schools pay the operator -------------------------------------------------------------------

export type PaymentMethodName = 'MPESA' | 'BANK_TRANSFER' | 'CASH' | 'CHEQUE' | 'OTHER';

export interface SubscriptionPaymentRow {
  id: string;
  school_id: string;
  amount: string;
  currency: string;
  method: PaymentMethodName;
  reference: string | null;
  paid_on: string;
  months_added: number;
  note: string | null;
  created_at: string | null;
  voided_at: string | null;
  void_reason: string | null;
}

export interface SubscriptionPaymentList {
  payments: SubscriptionPaymentRow[];
  total_paid: string;
  currency: string;
}

export interface SubscriptionPaymentInput {
  amount: string;
  method: PaymentMethodName;
  reference?: string;
  paid_on?: string;
  months: number;
  note?: string;
}

export async function listSubscriptionPayments(schoolId: string): Promise<SubscriptionPaymentList> {
  const { data } = await apiClient.get<SubscriptionPaymentList>(`/api/platform/schools/${schoolId}/subscription-payments`);
  return data;
}

export async function recordSubscriptionPayment(schoolId: string, body: SubscriptionPaymentInput): Promise<SubscriptionPaymentRow> {
  const { data } = await apiClient.post<SubscriptionPaymentRow>(`/api/platform/schools/${schoolId}/subscription-payments`, body);
  return data;
}

export async function voidSubscriptionPayment(paymentId: string, reason: string): Promise<SubscriptionPaymentRow> {
  const { data } = await apiClient.post<SubscriptionPaymentRow>(`/api/platform/subscription-payments/${paymentId}/void`, { reason });
  return data;
}

// ---- payments health ---------------------------------------------------------------------------------

export type HealthSeverity = 'ok' | 'info' | 'warn' | 'bad';

/** How one school's online payments are doing. Counts only: never a name, phone number or amount per person. */
export interface SchoolPaymentsHealth {
  school_id: string;
  school_name: string;
  currency: string;
  subscription_status: SubscriptionStatus;
  read_only: boolean;
  mpesa_mode: 'OFF' | 'GLOBAL' | 'OWN';
  environment: string | null;
  shortcode: string | null;
  tested_at: string | null;
  c2b_registered_at: string | null;
  last_error: string | null;
  confirmed_30d_count: number;
  confirmed_30d_amount: string;
  last_confirmed_at: string | null;
  stuck_pending: number;
  failed_7d: number;
  mismatches: number;
  unallocated: number;
  unmatched_c2b: number;
  shared_paybill: boolean;
  severity: HealthSeverity;
  attention: string[];
}

export async function getPaymentsHealth(): Promise<SchoolPaymentsHealth[]> {
  const { data } = await apiClient.get<SchoolPaymentsHealth[]>('/api/platform/payments-health');
  return data;
}
