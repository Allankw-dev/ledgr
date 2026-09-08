import { apiClient } from './client';
import type { Student, InvoiceListItem, Page, Term, SchoolClass, FeeStructure, FeeCategory } from '../types';

export async function listStudents(page = 1, pageSize = 25, classId?: string): Promise<Page<Student>> {
  const { data } = await apiClient.get<Page<Student>>('/api/students', {
    params: { page, page_size: pageSize, class_id: classId },
  });
  return data;
}

export async function deactivateStudent(studentId: string): Promise<Student> {
  const { data } = await apiClient.post<Student>(`/api/students/${studentId}/deactivate`);
  return data;
}

interface CreateStudentPayload {
  admission_number: string;
  full_name: string;
  class_id?: string;
  date_of_birth?: string;
}

export async function createStudent(payload: CreateStudentPayload): Promise<Student> {
  const { data } = await apiClient.post<Student>('/api/students', payload);
  return data;
}

export async function getStudent(id: string): Promise<Student> {
  const { data } = await apiClient.get<Student>(`/api/students/${id}`);
  return data;
}

export async function listInvoices(page = 1, pageSize = 25, status?: string, termId?: string): Promise<Page<InvoiceListItem>> {
  const { data } = await apiClient.get<Page<InvoiceListItem>>('/api/invoices', {
    params: { page, page_size: pageSize, status, term_id: termId },
  });
  return data;
}

interface RecordPaymentPayload {
  student_id: string;
  invoice_id?: string;
  amount: string;
  method: string;
  reference_code?: string;
}

export async function recordPayment(payload: RecordPaymentPayload) {
  const { data } = await apiClient.post('/api/payments', payload);
  return data;
}

// --- Terms ---
export async function listTerms(): Promise<Term[]> {
  const { data } = await apiClient.get<Term[]>('/api/terms');
  return data;
}

export async function createTerm(payload: { name: string; start_date: string; end_date: string }): Promise<Term> {
  const { data } = await apiClient.post<Term>('/api/terms', payload);
  return data;
}

// --- Classes ---
export async function listClasses(): Promise<SchoolClass[]> {
  const { data } = await apiClient.get<SchoolClass[]>('/api/classes');
  return data;
}

export async function createClass(name: string): Promise<SchoolClass> {
  const { data } = await apiClient.post<SchoolClass>('/api/classes', { name });
  return data;
}

export async function updateStudentClass(studentId: string, classId: string | null): Promise<Student> {
  const { data } = await apiClient.patch<Student>(`/api/students/${studentId}/class`, { class_id: classId });
  return data;
}

// --- Fee structures ---
export async function listFeeStructures(termId?: string): Promise<FeeStructure[]> {
  const { data } = await apiClient.get<FeeStructure[]>('/api/fee-structures', { params: { term_id: termId } });
  return data;
}

interface CreateFeeStructurePayload {
  term_id: string;
  class_id?: string;
  category: FeeCategory;
  name: string;
  amount: string;
}

export async function createFeeStructure(payload: CreateFeeStructurePayload): Promise<FeeStructure> {
  const { data } = await apiClient.post<FeeStructure>('/api/fee-structures', payload);
  return data;
}

// --- Bulk invoice generation ---
interface BulkGeneratePayload {
  term_id: string;
  class_id?: string;
  due_date: string;
}

export async function sendInvoiceReminder(invoiceId: string): Promise<{
  recipients_notified: number;
  results: { guardian_email: string | null; guardian_phone: string | null; email_sent: boolean; sms_sent: boolean; errors: string[] }[];
}> {
  const { data } = await apiClient.post(`/api/invoices/${invoiceId}/send-reminder`);
  return data;
}

interface BulkGenerateResult {
  created: number;
  skipped: number;
  errors: { student_id: string; error: string }[];
}

export async function bulkGenerateInvoices(payload: BulkGeneratePayload): Promise<BulkGenerateResult> {
  const { data } = await apiClient.post<BulkGenerateResult>('/api/invoices/bulk-generate', payload);
  return data;
}

// --- Bursar report export ---
export async function exportBursarReport(termId: string, format: 'xlsx' | 'csv'): Promise<Blob> {
  const { data } = await apiClient.get('/api/reports/bursar-export', {
    params: { term_id: termId, format },
    responseType: 'blob',
  });
  return data;
}
