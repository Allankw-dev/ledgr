import { apiClient } from './client';

export interface AssistantMessage {
  role: 'user' | 'assistant';
  content: string;
}

export async function queryAssistant(messages: AssistantMessage[]): Promise<string> {
  const { data } = await apiClient.post<{ answer: string }>('/api/assistant/query', { messages });
  return data.answer;
}
