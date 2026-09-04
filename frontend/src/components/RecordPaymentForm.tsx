import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { SelectField } from './ui/SelectField';
import { recordPayment } from '../api/school';
import type { PaymentMethod } from '../types';

const METHODS: PaymentMethod[] = ['MPESA', 'BANK_TRANSFER', 'CASH', 'CARD', 'CHEQUE', 'OTHER'];

const methodLabels: Record<PaymentMethod, string> = {
  MPESA: 'M-Pesa',
  BANK_TRANSFER: 'Bank transfer',
  CASH: 'Cash',
  CARD: 'Card',
  CHEQUE: 'Cheque',
  OTHER: 'Other',
};

const schema = z.object({
  amount: z.string().regex(/^\d+(\.\d{1,2})?$/, 'Enter a valid amount').refine((v) => Number(v) > 0, 'Amount must be greater than zero'),
  method: z.enum(METHODS as [PaymentMethod, ...PaymentMethod[]]),
  reference_code: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

interface RecordPaymentFormProps {
  studentId: string;
  invoiceId: string;
  balanceDue: number;
  onSuccess: () => void;
  onCancel: () => void;
}

export function RecordPaymentForm({ studentId, invoiceId, balanceDue, onSuccess, onCancel }: RecordPaymentFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { amount: balanceDue.toFixed(2), method: 'MPESA' },
  });

  async function onSubmit(values: FormValues) {
    try {
      await recordPayment({
        student_id: studentId,
        invoice_id: invoiceId,
        amount: values.amount,
        method: values.method,
        reference_code: values.reference_code || undefined,
      });
      onSuccess();
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: string } } })?.response?.data?.error ||
        'Could not record this payment. Check the details and try again.';
      setError('root', { message });
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <p className="text-sm text-ink-600">
        Balance due: <span className="figure font-medium text-ink-900">KES {balanceDue.toLocaleString()}</span>
      </p>

      <TextField label="Amount received (KES)" error={errors.amount?.message} {...register('amount')} />
      <SelectField
        label="Payment method"
        error={errors.method?.message}
        options={METHODS.map((m) => ({ value: m, label: methodLabels[m] }))}
        {...register('method')}
      />
      <TextField
        label="Reference code (optional)"
        placeholder="e.g. M-Pesa code QGH7X..."
        error={errors.reference_code?.message}
        {...register('reference_code')}
      />

      {errors.root && (
        <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">
          {errors.root.message}
        </p>
      )}

      <div className="flex justify-end gap-2 mt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Recording…' : 'Record payment'}
        </Button>
      </div>
    </form>
  );
}
