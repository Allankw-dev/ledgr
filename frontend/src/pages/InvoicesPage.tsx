import { useState } from 'react';
import { Plus, FileText, Receipt, Wallet } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import { SelectField } from '../components/ui/SelectField';
import { StatusBadge } from '../components/ui/StatusBadge';
import { AddTermForm } from '../components/AddTermForm';
import { AddFeeStructureForm } from '../components/AddFeeStructureForm';
import { BulkGenerateForm } from '../components/BulkGenerateForm';
import { RecordPaymentForm } from '../components/RecordPaymentForm';
import { RiskBadge } from '../components/RiskBadge';
import { SuggestPaymentPlan } from '../components/SuggestPaymentPlan';
import { ViewPaymentsButton } from '../components/ViewPaymentsButton';
import { SendReminderButton } from '../components/SendReminderButton';
import { useTerms, useClasses, useFeeStructures } from '../hooks/useSchoolSetup';
import { useInvoices } from '../hooks/useInvoices';
import { useStudents } from '../hooks/useStudents';
import type { Invoice } from '../types';

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(amount);
}

type ModalKind = 'term' | 'fee' | 'generate' | 'payment' | null;

export function InvoicesPage() {
  const { terms, loading: termsLoading, refetch: refetchTerms } = useTerms();
  const { classes } = useClasses();
  const { students } = useStudents();
  const [selectedTermId, setSelectedTermId] = useState<string>('');
  const { feeStructures, refetch: refetchFees } = useFeeStructures(selectedTermId || terms[0]?.id);
  const { invoices, loading: invoicesLoading, error, refetch: refetchInvoices } = useInvoices();
  const [modal, setModal] = useState<ModalKind>(null);
  const [generateResult, setGenerateResult] = useState<{ created: number; skipped: number } | null>(null);
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);

  const activeTermId = selectedTermId || terms[0]?.id || '';
  const activeTerm = terms.find((t) => t.id === activeTermId);
  const studentName = (id: string) => students.find((s) => s.id === id)?.full_name || id.slice(0, 8);

  function handleGenerateSuccess(result: { created: number; skipped: number }) {
    setModal(null);
    setGenerateResult(result);
    refetchInvoices();
  }

  function openPaymentModal(invoice: Invoice) {
    setSelectedInvoice(invoice);
    setModal('payment');
  }

  function handlePaymentSuccess() {
    setModal(null);
    setSelectedInvoice(null);
    refetchInvoices();
  }

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto px-8 py-8">
        <div className="mb-8">
          <h1 className="font-display text-2xl text-ink-900 font-medium">Invoices</h1>
          <p className="text-sm text-ink-600 mt-1">Set up terms and fees, then generate bills for your students.</p>
        </div>

        {error && (
          <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm mb-6">
            {error}
          </div>
        )}

        {generateResult && (
          <div role="status" className="bg-emerald-100 text-emerald-700 rounded-md px-4 py-3 text-sm mb-6">
            Generated {generateResult.created} invoice{generateResult.created === 1 ? '' : 's'}.
            {generateResult.skipped > 0 && ` ${generateResult.skipped} skipped (already invoiced or missing fee data).`}
          </div>
        )}

        {/* Term setup */}
        <div className="bg-white border border-ink-200 rounded-lg p-5 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display text-base text-ink-900 font-medium">Term</h2>
            <Button variant="secondary" onClick={() => setModal('term')} className="flex items-center gap-1.5 text-xs px-3 py-1.5">
              <Plus className="w-3.5 h-3.5" /> New term
            </Button>
          </div>

          {termsLoading ? (
            <p className="text-sm text-ink-600">Loading…</p>
          ) : terms.length === 0 ? (
            <p className="text-sm text-ink-600">No terms yet. Create one to start setting up fees.</p>
          ) : (
            <div className="max-w-xs">
              <SelectField
                label="Active term"
                value={activeTermId}
                onChange={(e) => setSelectedTermId(e.target.value)}
                options={terms.map((t) => ({ value: t.id, label: t.name }))}
              />
            </div>
          )}
        </div>

        {/* Fee structures for the active term */}
        {activeTerm && (
          <div className="bg-white border border-ink-200 rounded-lg p-5 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-display text-base text-ink-900 font-medium">Fees for {activeTerm.name}</h2>
              <Button variant="secondary" onClick={() => setModal('fee')} className="flex items-center gap-1.5 text-xs px-3 py-1.5">
                <Plus className="w-3.5 h-3.5" /> Add fee
              </Button>
            </div>

            {feeStructures.length === 0 ? (
              <p className="text-sm text-ink-600">
                No fees set up for this term yet. Add at least one before generating invoices.
              </p>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {feeStructures.map((fs) => (
                    <tr key={fs.id} className="h-9 text-ink-900 border-t border-ink-100 first:border-t-0">
                      <td className="py-1.5 text-ink-600">{fs.name}</td>
                      <td className="py-1.5 text-ink-400 text-xs">
                        {classes.find((c) => c.id === fs.class_id)?.name || 'All classes'}
                      </td>
                      <td className="py-1.5 figure text-right">{formatCurrency(Number(fs.amount))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {feeStructures.length > 0 && (
              <Button onClick={() => setModal('generate')} className="mt-4 flex items-center gap-2">
                <Receipt className="w-4 h-4" /> Generate invoices for this term
              </Button>
            )}
          </div>
        )}

        {/* Invoices list */}
        <div className="bg-white border border-ink-200 rounded-lg overflow-hidden">
          <div className="px-5 py-4 border-b border-ink-200">
            <h2 className="font-display text-base text-ink-900 font-medium">All invoices</h2>
          </div>

          {invoicesLoading ? (
            <div className="px-5 py-12 text-center text-sm text-ink-600">Loading…</div>
          ) : invoices.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <FileText className="w-8 h-8 text-ink-400 mx-auto mb-3" strokeWidth={1.5} />
              <p className="text-sm text-ink-900 font-medium">No invoices yet</p>
              <p className="text-xs text-ink-600 mt-1">Set up a term and fees above, then generate invoices.</p>
            </div>
          ) : (
            <div className="ledger-lines">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-ink-600">
                    <th className="px-5 py-2 font-medium">Student</th>
                    <th className="px-5 py-2 font-medium">Due date</th>
                    <th className="px-5 py-2 font-medium text-right">Total</th>
                    <th className="px-5 py-2 font-medium text-right">Paid</th>
                    <th className="px-5 py-2 font-medium">Status</th>
                    <th className="px-5 py-2 font-medium">Risk</th>
                    <th className="px-5 py-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => {
                    const canPay = inv.status !== 'PAID' && inv.status !== 'CANCELLED';
                    return (
                      <tr key={inv.id} className="h-9 text-ink-900">
                        <td className="px-5">{studentName(inv.student_id)}</td>
                        <td className="px-5">{new Date(inv.due_date).toLocaleDateString('en-KE')}</td>
                        <td className="px-5 figure text-right">{formatCurrency(Number(inv.total_amount))}</td>
                        <td className="px-5 figure text-right">{formatCurrency(Number(inv.amount_paid))}</td>
                        <td className="px-5">
                          <StatusBadge status={inv.status} />
                        </td>
                        <td className="px-5">{canPay && <RiskBadge invoiceId={inv.id} />}</td>
                        <td className="px-5 text-right">
                          <div className="flex items-center justify-end gap-3">
                            <ViewPaymentsButton invoiceId={inv.id} />
                            {canPay && (
                              <>
                                <SendReminderButton invoiceId={inv.id} />
                                <SuggestPaymentPlan invoiceId={inv.id} />
                                <button
                                  onClick={() => openPaymentModal(inv)}
                                  className="text-xs font-medium text-ink-900 hover:underline underline-offset-2 flex items-center gap-1"
                                >
                                  <Wallet className="w-3.5 h-3.5" /> Record payment
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {modal === 'term' && (
        <Modal title="New term" onClose={() => setModal(null)}>
          <AddTermForm onSuccess={() => { setModal(null); refetchTerms(); }} onCancel={() => setModal(null)} />
        </Modal>
      )}

      {modal === 'fee' && activeTerm && (
        <Modal title={`Add fee — ${activeTerm.name}`} onClose={() => setModal(null)}>
          <AddFeeStructureForm
            termId={activeTerm.id}
            classes={classes}
            onSuccess={() => { setModal(null); refetchFees(); }}
            onCancel={() => setModal(null)}
          />
        </Modal>
      )}

      {modal === 'generate' && activeTerm && (
        <Modal title={`Generate invoices — ${activeTerm.name}`} onClose={() => setModal(null)}>
          <BulkGenerateForm
            termId={activeTerm.id}
            classes={classes}
            onSuccess={handleGenerateSuccess}
            onCancel={() => setModal(null)}
          />
        </Modal>
      )}

      {modal === 'payment' && selectedInvoice && (
        <Modal title={`Record payment — ${studentName(selectedInvoice.student_id)}`} onClose={() => setModal(null)}>
          <RecordPaymentForm
            studentId={selectedInvoice.student_id}
            invoiceId={selectedInvoice.id}
            balanceDue={Number(selectedInvoice.total_amount) - Number(selectedInvoice.amount_paid)}
            onSuccess={handlePaymentSuccess}
            onCancel={() => setModal(null)}
          />
        </Modal>
      )}
    </AppShell>
  );
}
