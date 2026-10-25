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
