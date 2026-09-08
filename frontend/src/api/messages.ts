import { apiClient } from './client';

export interface Message {
  id: string;
  sender_role: 'PARENT' | 'STAFF';
  sender_name: string;
  body: string;
  student_id: string | null;
  student_name: string | null;
  created_at: string;
}

export interface ConversationSummary {
  parent_user_id: string;
  parent_name: string;
  last_message_body: string;
  last_message_at: string;
  last_message_sender_role: 'PARENT' | 'STAFF';
  unread_count: number;
}

// Parent side
export async function getMyMessages(): Promise<Message[]> {
  const { data } = await apiClient.get<Message[]>('/api/parent/messages');
  return data;
}

export async function sendMyMessage(body: string, studentId?: string): Promise<Message> {
  const { data } = await apiClient.post<Message>('/api/parent/messages', { body, student_id: studentId ?? null });
  return data;
}

// Staff side
export async function getConversations(): Promise<ConversationSummary[]> {
  const { data } = await apiClient.get<ConversationSummary[]>('/api/messages/conversations');
  return data;
}

export async function getConversation(parentUserId: string): Promise<Message[]> {
  const { data } = await apiClient.get<Message[]>(`/api/messages/conversations/${parentUserId}`);
  return data;
}

export async function sendConversationReply(parentUserId: string, body: string, studentId?: string): Promise<Message> {
  const { data } = await apiClient.post<Message>(`/api/messages/conversations/${parentUserId}`, {
    body,
    student_id: studentId ?? null,
  });
  return data;
}
