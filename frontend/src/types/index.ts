export type UserRole = 'SUPER_ADMIN' | 'SCHOOL_ADMIN' | 'BURSAR' | 'TEACHER' | 'PARENT';

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
  has_active_payment_plan: boolean;
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
  has_active_payment_plan: boolean;
}

export interface Teacher {
  id: string;
  full_name: string;
  email: string | null; // null for teachers who signed up with a phone number only
  phone: string | null;
  invite_channels?: string[]; // set on create/resend: 'email' and/or 'sms'
  is_active: boolean;
  created_at: string;
  class_ids: string[];
  class_names: string[];
}

export interface ClassGroupSummary {
  class_id: string;
  class_name: string;
  last_message_preview: string | null;
  last_message_at: string | null;
  unread_count?: number;
  unread_mentions?: number;
}

export interface ClassGroupMessage {
  id: string;
  class_id: string;
  sender_user_id: string;
  sender_name: string;
  sender_role: UserRole;
  sender_subtitle?: string | null; // e.g. "Parent of Kevin"
  body: string;
  created_at: string;
  attachment?: ChatAttachment | null;
  mentions?: { user_id: string; name: string }[];
  mentions_me?: boolean;
  // Only on your own messages: sent = 1 grey tick, delivered = 2 grey, read = 2 blue (read by everyone).
  status?: MessageStatus | null;
  read_count?: number | null;
  delivered_count?: number | null;
  recipient_count?: number | null;
}

export type MessageStatus = 'sent' | 'delivered' | 'read';

export interface ChatAttachment {
  name: string;
  mime: string;
  size: number;
  is_image: boolean;
}

export interface AttachmentUrl extends ChatAttachment {
  url: string;
  expires_in: number;
}

export interface GroupMember {
  user_id: string;
  name: string;
  role: UserRole;
  subtitle: string | null;
}

export interface MessageReceipt extends GroupMember {
  read: boolean;
  delivered: boolean;
}

export interface MentionNotification {
  id: string;
  class_id: string;
  class_name: string;
  message_id: string;
  sender_name: string;
  preview: string;
  created_at: string;
  seen: boolean;
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
