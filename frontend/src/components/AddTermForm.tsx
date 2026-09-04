import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { createTerm } from '../api/school';

const schema = z
  .object({
    name: z.string().min(2, 'Give this term a name, e.g. "Term 1 2026"'),
    start_date: z.string().min(1, 'Start date is required'),
    end_date: z.string().min(1, 'End date is required'),
  })
  .refine((v) => new Date(v.end_date) > new Date(v.start_date), {
    message: 'End date must be after the start date',
    path: ['end_date'],
  });

type FormValues = z.infer<typeof schema>;

export function AddTermForm({ onSuccess, onCancel }: { onSuccess: () => void; onCancel: () => void }) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    try {
      await createTerm({
        name: values.name,
        start_date: new Date(values.start_date).toISOString(),
        end_date: new Date(values.end_date).toISOString(),
      });
      onSuccess();
    } catch {
      setError('root', { message: 'Could not create this term. Check the dates and try again.' });
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <TextField label="Term name" placeholder="e.g. Term 1 2026" error={errors.name?.message} {...register('name')} />
      <TextField label="Start date" type="date" error={errors.start_date?.message} {...register('start_date')} />
      <TextField label="End date" type="date" error={errors.end_date?.message} {...register('end_date')} />

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
          {isSubmitting ? 'Creating…' : 'Create term'}
        </Button>
      </div>
    </form>
  );
}
