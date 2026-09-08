import { FileText } from 'lucide-react';
import { apiClient } from '../api/client';

export function DownloadInvoicePdfLink({ invoiceId }: { invoiceId: string }) {
  async function handleClick() {
    try {
      const response = await apiClient.get(`/api/invoices/${invoiceId}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
      window.open(url, '_blank');
      setTimeout(() => window.URL.revokeObjectURL(url), 10000);
    } catch {
      alert('Could not open the invoice. Try again in a moment.');
    }
  }

  return (
    <button
      onClick={handleClick}
      className="text-xs font-medium text-ink-900 hover:underline underline-offset-2 flex items-center gap-1"
    >
      <FileText className="w-3.5 h-3.5" /> Invoice PDF
    </button>
  );
}
