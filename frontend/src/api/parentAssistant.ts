import { apiClient } from './client';

export interface AssistantMessage {
  role: 'user' | 'assistant';
  content: string;
}

export async function queryParentAssistant(messages: AssistantMessage[]): Promise<string> {
  const { data } = await apiClient.post<{ answer: string }>('/api/parent/assistant/query', { messages });
  return data.answer;
}
