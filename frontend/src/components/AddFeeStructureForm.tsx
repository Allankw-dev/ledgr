import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { SelectField } from './ui/SelectField';
import { createFeeStructure } from '../api/school';
import type { SchoolClass, FeeCategory } from '../types';

const CATEGORIES: FeeCategory[] = ['TUITION', 'TRANSPORT', 'BOARDING', 'MEALS', 'ACTIVITY', 'EXAM', 'UNIFORM', 'OTHER'];

const schema = z.object({
  name: z.string().min(2, 'Give this fee a name, e.g. "Tuition Fee"'),
  category: z.enum(CATEGORIES as [FeeCategory, ...FeeCategory[]]),
  amount: z.string().regex(/^\d+(\.\d{1,2})?$/, 'Enter a valid amount, e.g. 25000'),
  class_id: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

interface AddFeeStructureFormProps {
  termId: string;
  classes: SchoolClass[];
  onSuccess: () => void;
  onCancel: () => void;
}

export function AddFeeStructureForm({ termId, classes, onSuccess, onCancel }: AddFeeStructureFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    try {
      await createFeeStructure({
        term_id: termId,
        class_id: values.class_id || undefined,
        category: values.category,
        name: values.name,
        amount: values.amount,
      });
      onSuccess();
    } catch {
      setError('root', { message: 'Could not add this fee. Check the details and try again.' });
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <TextField label="Fee name" placeholder="e.g. Tuition Fee" error={errors.name?.message} {...register('name')} />
      <SelectField
        label="Category"
        error={errors.category?.message}
        options={CATEGORIES.map((c) => ({ value: c, label: c.charAt(0) + c.slice(1).toLowerCase() }))}
        {...register('category')}
      />
      <TextField label="Amount (KES)" placeholder="e.g. 25000" error={errors.amount?.message} {...register('amount')} />
      <SelectField
        label="Applies to"
        placeholder="All classes"
        error={errors.class_id?.message}
        options={classes.map((c) => ({ value: c.id, label: c.name }))}
        {...register('class_id')}
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
          {isSubmitting ? 'Adding…' : 'Add fee'}
        </Button>
      </div>
    </form>
  );
}
