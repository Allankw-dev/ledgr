import { useState } from 'react';
import { Plus, FileText, Receipt, Wallet, Search, Pencil, Trash2, Ban } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import { SelectField } from '../components/ui/SelectField';
import { StatusBadge } from '../components/ui/StatusBadge';
import { PaginationControls } from '../components/ui/PaginationControls';
import { AddTermForm } from '../components/AddTermForm';
import { AddFeeStructureForm } from '../components/AddFeeStructureForm';
import { EditFeeStructureForm } from '../components/EditFeeStructureForm';
import { EditInvoiceDueDateForm } from '../components/EditInvoiceDueDateForm';
import { BulkGenerateForm } from '../components/BulkGenerateForm';
import { RecordPaymentForm } from '../components/RecordPaymentForm';
import { RiskBadge } from '../components/RiskBadge';
import { SuggestPaymentPlan } from '../components/SuggestPaymentPlan';
import { ReconcileMpesaPayment } from '../components/ReconcileMpesaPayment';
import { DownloadStatementLink } from '../components/DownloadStatementLink';
import { DownloadInvoicePdfLink } from '../components/DownloadInvoicePdfLink';
import { ViewPaymentsButton } from '../components/ViewPaymentsButton';
import { SendReminderButton } from '../components/SendReminderButton';
import { ExportReportButton } from '../components/ExportReportButton';
import { AutomationCard } from '../components/AutomationCard';
import { useTerms, useClasses, useFeeStructures } from '../hooks/useSchoolSetup';
import { useInvoices } from '../hooks/useInvoices';
import { deleteFeeStructure, voidInvoice } from '../api/school';
import type { InvoiceListItem, FeeStructure } from '../types';

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-KE', { style: 'currency', currency: 'KES', maximumFractionDigits: 0 }).format(amount);
}

type ModalKind = 'term' | 'fee' | 'edit-fee' | 'edit-due-date' | 'generate' | 'payment' | 'reconcile' | null;

export function InvoicesPage() {
  const { terms, loading: termsLoading, refetch: refetchTerms } = useTerms();
  const { classes } = useClasses();
  const [selectedTermId, setSelectedTermId] = useState<string>('');
  const { feeStructures, refetch: refetchFees } = useFeeStructures(selectedTermId || terms[0]?.id);
  const activeTermId = selectedTermId || terms[0]?.id || '';
  const {
    invoices,
    meta: invoicesMeta,
    setPage: setInvoicesPage,
    loading: invoicesLoading,
    error,
    refetch: refetchInvoices,
  } = useInvoices(activeTermId || undefined);
  const [modal, setModal] = useState<ModalKind>(null);
  const [generateResult, setGenerateResult] = useState<{ created: number; skipped: number } | null>(null);
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceListItem | null>(null);
  const [editingFee, setEditingFee] = useState<FeeStructure | null>(null);
  const [feeActionError, setFeeActionError] = useState<string | null>(null);
  const [invoiceActionError, setInvoiceActionError] = useState<string | null>(null);
  const [voidingId, setVoidingId] = useState<string | null>(null);

  async function handleDeleteFeeStructure(fs: FeeStructure) {
    if (!window.confirm(`Delete "${fs.name}"? This can't be undone.`)) return;
    setFeeActionError(null);
    try {
      await deleteFeeStructure(fs.id);
      refetchFees();
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Could not delete this fee.';
      setFeeActionError(message);
    }
  }

  async function handleVoidInvoice(inv: InvoiceListItem) {
    if (!window.confirm(`Void this invoice for ${inv.student_name}? This can't be undone.`)) return;
    setInvoiceActionError(null);
    setVoidingId(inv.id);
    try {
      await voidInvoice(inv.id);
      refetchInvoices();
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Could not void this invoice.';
      setInvoiceActionError(message);
    } finally {
      setVoidingId(null);
    }
  }

  const activeTerm = terms.find((t) => t.id === activeTermId);

  function handleGenerateSuccess(result: { created: number; skipped: number }) {
    setModal(null);
    setGenerateResult(result);
    refetchInvoices();
  }

  function openPaymentModal(invoice: InvoiceListItem) {
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
      <div className="max-w-6xl mx-auto px-4 sm:px-8 py-6 sm:py-8">
        <div className="mb-8 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="font-display text-2xl text-ink-900 font-medium">Invoices</h1>
            <p className="text-sm text-ink-600 mt-1">Set up terms and fees, then generate bills for your students.</p>
          </div>
          <Button
            variant="secondary"
            onClick={() => setModal('reconcile')}
            className="shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5"
          >
            <Search className="w-3.5 h-3.5" /> Reconcile M-Pesa payment
          </Button>
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
        <div className="bg-panel border border-ink-200 rounded-lg p-5 mb-6">
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
          <div className="bg-panel border border-ink-200 rounded-lg p-5 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-display text-base text-ink-900 font-medium">Fees for {activeTerm.name}</h2>
              <Button variant="secondary" onClick={() => setModal('fee')} className="flex items-center gap-1.5 text-xs px-3 py-1.5">
                <Plus className="w-3.5 h-3.5" /> Add fee
              </Button>
            </div>

            {feeActionError && (
              <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2 mb-3">
                {feeActionError}
              </p>
            )}

            {feeStructures.length === 0 ? (
              <p className="text-sm text-ink-600">
                No fees set up for this term yet. Add at least one before generating invoices.
              </p>
            ) : (
              <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <tbody>
                  {feeStructures.map((fs) => (
                    <tr key={fs.id} className="h-9 text-ink-900 border-t border-ink-100 first:border-t-0">
                      <td className="py-1.5 text-ink-600">{fs.name}</td>
                      <td className="py-1.5 text-ink-400 text-xs">
                        {classes.find((c) => c.id === fs.class_id)?.name || 'All classes'}
                      </td>
                      <td className="py-1.5 figure text-right">{formatCurrency(Number(fs.amount))}</td>
                      <td className="py-1.5 text-right">
                        <div className="flex items-center justify-end gap-3">
                          <button
                            onClick={() => { setEditingFee(fs); setModal('edit-fee'); }}
                            className="text-ink-400 hover:text-ink-900"
                            title="Edit"
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDeleteFeeStructure(fs)}
                            className="text-ink-400 hover:text-clay-700"
                            title="Delete"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            )}

            {feeStructures.length > 0 && (
              <Button onClick={() => setModal('generate')} className="mt-4 flex items-center gap-2">
                <Receipt className="w-4 h-4" /> Generate invoices for this term
              </Button>
            )}
          </div>
        )}

        <div className="mb-6">
          <AutomationCard />
        </div>

        {/* Invoices list */}
        <div className="bg-panel border border-ink-200 rounded-lg overflow-hidden">
          <div className="px-5 py-4 border-b border-ink-200 flex items-center justify-between">
            <h2 className="font-display text-base text-ink-900 font-medium">All invoices</h2>
            {activeTerm && <ExportReportButton termId={activeTerm.id} termName={activeTerm.name} />}
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
            <div className="ledger-lines overflow-x-auto">
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
                        <td className="px-5">{inv.student_name}</td>
                        <td className="px-5">{new Date(inv.due_date).toLocaleDateString('en-KE')}</td>
                        <td className="px-5 figure text-right">{formatCurrency(Number(inv.total_amount))}</td>
                        <td className="px-5 figure text-right">{formatCurrency(Number(inv.amount_paid))}</td>
                        <td className="px-5">
                          <StatusBadge status={inv.status} hasActivePaymentPlan={inv.has_active_payment_plan} />
                        </td>
                        <td className="px-5">{canPay && <RiskBadge invoiceId={inv.id} />}</td>
                        <td className="px-5 text-right">
                          <div className="flex items-center justify-end gap-3">
                            <ViewPaymentsButton invoiceId={inv.id} />
                            <DownloadInvoicePdfLink invoiceId={inv.id} />
                            <DownloadStatementLink studentId={inv.student_id} />
                            <button
                              onClick={() => { setSelectedInvoice(inv); setModal('edit-due-date'); }}
                              className="text-xs font-medium text-ink-900 hover:underline underline-offset-2 flex items-center gap-1"
                              title="Edit due date"
                            >
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            {Number(inv.amount_paid) === 0 && inv.status !== 'CANCELLED' && (
                              <button
                                onClick={() => handleVoidInvoice(inv)}
                                disabled={voidingId === inv.id}
                                className="text-xs font-medium text-clay-700 hover:underline underline-offset-2 flex items-center gap-1 disabled:opacity-50"
                                title="Void invoice"
                              >
                                <Ban className="w-3.5 h-3.5" /> {voidingId === inv.id ? 'Voiding…' : 'Void'}
                              </button>
                            )}
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
          {invoiceActionError && (
            <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-5 py-2">
              {invoiceActionError}
            </p>
          )}
          {invoicesMeta && <PaginationControls meta={invoicesMeta} onPageChange={setInvoicesPage} />}
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

      {modal === 'edit-fee' && editingFee && (
        <Modal title={`Edit fee — ${editingFee.name}`} onClose={() => { setModal(null); setEditingFee(null); }}>
          <EditFeeStructureForm
            feeStructure={editingFee}
            classes={classes}
            onSuccess={() => { setModal(null); setEditingFee(null); refetchFees(); }}
            onCancel={() => { setModal(null); setEditingFee(null); }}
          />
        </Modal>
      )}

      {modal === 'edit-due-date' && selectedInvoice && (
        <Modal title={`Edit due date — ${selectedInvoice.student_name}`} onClose={() => setModal(null)}>
          <EditInvoiceDueDateForm
            invoiceId={selectedInvoice.id}
            currentDueDate={selectedInvoice.due_date}
            onSuccess={() => { setModal(null); refetchInvoices(); }}
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
        <Modal title={`Record payment — ${selectedInvoice.student_name}`} onClose={() => setModal(null)}>
          <RecordPaymentForm
            studentId={selectedInvoice.student_id}
            invoiceId={selectedInvoice.id}
            balanceDue={Number(selectedInvoice.total_amount) - Number(selectedInvoice.amount_paid)}
            onSuccess={handlePaymentSuccess}
            onCancel={() => setModal(null)}
          />
        </Modal>
      )}

      {modal === 'reconcile' && (
        <Modal title="Reconcile an M-Pesa payment" onClose={() => setModal(null)}>
          <ReconcileMpesaPayment
            invoices={invoices}
            onMatched={() => {
              refetchInvoices();
            }}
            onCancel={() => setModal(null)}
          />
        </Modal>
      )}
    </AppShell>
  );
}
