import { apiClient } from './client';

export interface NotificationSummary {
  unread_messages: number;
  unread_class_group_messages: number;
  total: number;
}

export async function getNotificationSummary(): Promise<NotificationSummary> {
  const { data } = await apiClient.get<NotificationSummary>('/api/parent/notifications');
  return data;
}
