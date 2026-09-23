import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { SelectField } from './ui/SelectField';
import { createStudent } from '../api/school';
import { getErrorMessage } from '../api/client';
import { useClasses } from '../hooks/useSchoolSetup';

const RELATIONSHIPS = ['mother', 'father', 'guardian'] as const;

// Mirrors the backend's CreateStudentRequest Pydantic schema. Parent name +
// phone are required alongside the student, not optional extras — that's
// what lets the parent be connected automatically the moment they sign up.
const schema = z.object({
  admission_number: z.string().min(1, 'Admission number is required'),
  full_name: z.string().min(2, "Enter the student's full name"),
  class_id: z.string().optional(),
  date_of_birth: z.string().optional(),
  guardian_full_name: z.string().min(2, "Enter the parent's full name"),
  guardian_phone: z.string().min(7, 'Enter a valid phone number'),
  guardian_relationship_type: z.string().min(1),
});

type FormValues = z.infer<typeof schema>;

interface AddStudentFormProps {
  onSuccess: () => void;
  onCancel: () => void;
}

export function AddStudentForm({ onSuccess, onCancel }: AddStudentFormProps) {
  const { classes } = useClasses();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { guardian_relationship_type: 'guardian' } });

  async function onSubmit(values: FormValues) {
    try {
      await createStudent({
        admission_number: values.admission_number,
        full_name: values.full_name,
        class_id: values.class_id || undefined,
        date_of_birth: values.date_of_birth ? new Date(values.date_of_birth).toISOString() : undefined,
        guardian_full_name: values.guardian_full_name,
        guardian_phone: values.guardian_phone,
        guardian_relationship_type: values.guardian_relationship_type,
      });
      onSuccess();
    } catch (err: unknown) {
      setError('root', { message: getErrorMessage(err, 'Could not add this student. Check the details and try again.') });
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
      <SelectField
        label="Grade"
        placeholder="Unassigned"
        options={classes.map((c) => ({ value: c.id, label: c.name }))}
        error={errors.class_id?.message}
        {...register('class_id')}
      />
      <TextField
        label="Date of birth"
        type="date"
        error={errors.date_of_birth?.message}
        {...register('date_of_birth')}
      />

      <div className="pt-2 mt-1 border-t border-ink-200">
        <p className="text-sm font-medium text-ink-900 mb-1">Parent / guardian</p>
        <p className="text-xs text-ink-600 mb-4">
          The parent gets connected to this child automatically the moment they sign up with this same name and
          phone number — they choose their own password, you're not setting one for them.
        </p>
      </div>

      <TextField
        label="Parent's full name"
        placeholder="e.g. Wanjiru Otieno"
        error={errors.guardian_full_name?.message}
        {...register('guardian_full_name')}
      />
      <TextField
        label="Parent's phone number"
        type="tel"
        placeholder="e.g. 0712 345 678"
        error={errors.guardian_phone?.message}
        {...register('guardian_phone')}
      />
      <SelectField
        label="Relationship"
        error={errors.guardian_relationship_type?.message}
        options={RELATIONSHIPS.map((r) => ({ value: r, label: r.charAt(0).toUpperCase() + r.slice(1) }))}
        {...register('guardian_relationship_type')}
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
