import { apiClient } from './client';
import type { MentionNotification } from '../types';

export interface NotificationSummary {
  unread_messages: number;
  unread_class_group_messages: number;
  total: number;
}

export interface AllNotificationsSummary extends NotificationSummary {
  unread_mentions: number;
  unread_direct_messages: number;
}

/** Parent-only legacy endpoint, kept for compatibility. */
export async function getNotificationSummary(): Promise<NotificationSummary> {
  const { data } = await apiClient.get<NotificationSummary>('/api/parent/notifications');
  return data;
}

/** Works for every role. Polling it also tells senders their message was delivered. */
export async function getAllNotificationsSummary(): Promise<AllNotificationsSummary> {
  const { data } = await apiClient.get<AllNotificationsSummary>('/api/notifications/summary');
  return data;
}

export async function listMentions(): Promise<MentionNotification[]> {
  const { data } = await apiClient.get<MentionNotification[]>('/api/notifications/mentions');
  return data;
}

export async function markMentionsSeen(ids?: string[]): Promise<void> {
  await apiClient.post('/api/notifications/mentions/seen', { ids: ids ?? null });
}
