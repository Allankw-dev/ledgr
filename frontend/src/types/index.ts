export type UserRole = 'SUPER_ADMIN' | 'SCHOOL_ADMIN' | 'BURSAR' | 'PARENT';

export type InvoiceStatus = 'DRAFT' | 'ISSUED' | 'PARTIALLY_PAID' | 'PAID' | 'OVERDUE' | 'CANCELLED';

export type PaymentMethod = 'MPESA' | 'BANK_TRANSFER' | 'CASH' | 'CARD' | 'CHEQUE' | 'OTHER';

export interface Term {
  id: string;
  school_id: string;
  name: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
}

export interface SchoolClass {
  id: string;
  school_id: string;
  name: string;
}

export type FeeCategory = 'TUITION' | 'TRANSPORT' | 'BOARDING' | 'MEALS' | 'ACTIVITY' | 'EXAM' | 'UNIFORM' | 'OTHER';

export interface FeeStructure {
  id: string;
  term_id: string;
  class_id: string | null;
  category: FeeCategory;
  name: string;
  amount: string;
  is_mandatory: boolean;
}

export interface ParentPaymentView {
  id: string;
  amount: string;
  method: string;
  paid_at: string | null;
}

export interface ParentInvoiceItemView {
  name: string;
  category: string;
  amount: string;
}

export interface ParentInvoiceView {
  id: string;
  total_amount: string;
  amount_paid: string;
  due_date: string;
  status: InvoiceStatus;
  items: ParentInvoiceItemView[];
  payments: ParentPaymentView[];
}

export interface ParentStudentView {
  id: string;
  full_name: string;
  admission_number: string;
  class_name: string | null;
  invoices: ParentInvoiceView[];
  balance_due: string;
}

export interface AuthUser {
  id: string;
  email: string;
  full_name?: string;
  phone?: string | null;
  role: UserRole;
  school_id: string | null;
}

export interface Student {
  id: string;
  school_id: string;
  class_id: string | null;
  admission_number: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface Invoice {
  id: string;
  student_id: string;
  term_id: string;
  total_amount: string;
  amount_paid: string;
  due_date: string;
  status: InvoiceStatus;
}

export interface InvoiceListItem extends Invoice {
  student_name: string;
  class_name: string;
}

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
}

export interface Page<T> {
  items: T[];
  meta: PageMeta;
}

export interface Payment {
  id: string;
  student_id: string;
  invoice_id: string | null;
  amount: string;
  method: PaymentMethod;
  status: string;
}
