import { apiClient } from './client';

export interface SendAnnouncementPayload {
  subject: string;
  message: string;
  classId?: string;
  classIds?: string[];
}

export interface SendAnnouncementResult {
  recipient_count: number;
  jobs_queued: number;
  errors: string[];
}

export async function sendAnnouncement(payload: SendAnnouncementPayload): Promise<SendAnnouncementResult> {
  const { data } = await apiClient.post<SendAnnouncementResult>('/api/announcements/send', {
    subject: payload.subject,
    message: payload.message,
    class_id: payload.classId || null,
    class_ids: payload.classIds ?? [],
  });
  return data;
}
