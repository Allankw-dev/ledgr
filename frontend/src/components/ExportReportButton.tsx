import { useState } from 'react';
import { FileSpreadsheet, FileText } from 'lucide-react';
import { exportBursarReport } from '../api/school';

interface ExportReportButtonProps {
  termId: string;
  termName: string;
}

export function ExportReportButton({ termId, termName }: ExportReportButtonProps) {
  const [downloading, setDownloading] = useState<'xlsx' | 'csv' | null>(null);

  async function handleDownload(format: 'xlsx' | 'csv') {
    setDownloading(format);
    try {
      const blob = await exportBursarReport(termId, format);
      const mimeType =
        format === 'xlsx' ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' : 'text/csv';
      const url = window.URL.createObjectURL(new Blob([blob], { type: mimeType }));
      const link = document.createElement('a');
      link.href = url;
      link.download = `bursar-report-${termName.replace(/\s+/g, '-')}.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => window.URL.revokeObjectURL(url), 10000);
    } catch {
      alert('Could not generate the report. Try again in a moment.');
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={() => handleDownload('xlsx')}
        disabled={downloading !== null}
        className="text-xs font-medium text-ink-900 hover:underline underline-offset-2 flex items-center gap-1 disabled:opacity-60 disabled:no-underline"
      >
        <FileSpreadsheet className="w-3.5 h-3.5" /> {downloading === 'xlsx' ? 'Preparing…' : 'Export Excel'}
      </button>
      <button
        onClick={() => handleDownload('csv')}
        disabled={downloading !== null}
        className="text-xs font-medium text-ink-900 hover:underline underline-offset-2 flex items-center gap-1 disabled:opacity-60 disabled:no-underline"
      >
        <FileText className="w-3.5 h-3.5" /> {downloading === 'csv' ? 'Preparing…' : 'Export CSV'}
      </button>
    </div>
  );
}
