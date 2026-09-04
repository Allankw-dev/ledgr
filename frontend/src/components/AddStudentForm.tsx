import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { createStudent } from '../api/school';

// Mirrors the backend's CreateStudentRequest Pydantic schema, so a mismatch
// gets caught here in the browser before the request ever leaves the machine.
const schema = z.object({
  admission_number: z.string().min(1, 'Admission number is required'),
  full_name: z.string().min(2, 'Enter the student\'s full name'),
  date_of_birth: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

interface AddStudentFormProps {
  onSuccess: () => void;
  onCancel: () => void;
}

export function AddStudentForm({ onSuccess, onCancel }: AddStudentFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    try {
      await createStudent({
        admission_number: values.admission_number,
        full_name: values.full_name,
        date_of_birth: values.date_of_birth ? new Date(values.date_of_birth).toISOString() : undefined,
      });
      onSuccess();
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: string } } })?.response?.data?.error ||
        'Could not add this student. Check the details and try again.';
      setError('root', { message });
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <TextField
        label="Admission number"
        placeholder="e.g. GA-2026-014"
        error={errors.admission_number?.message}
        {...register('admission_number')}
      />
      <TextField
        label="Full name"
        placeholder="e.g. Amani Otieno"
        error={errors.full_name?.message}
        {...register('full_name')}
      />
      <TextField
        label="Date of birth"
        type="date"
        error={errors.date_of_birth?.message}
        {...register('date_of_birth')}
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
          {isSubmitting ? 'Adding…' : 'Add student'}
        </Button>
      </div>
    </form>
  );
}
