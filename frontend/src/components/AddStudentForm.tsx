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

// Mirrors the backend's CreateStudentRequest Pydantic schema, so a mismatch
// gets caught here in the browser before the request ever leaves the machine.
// The guardian_* fields are optional as a group, but if any is filled in,
// full_name + phone are required together — a name with no phone number
// can't be matched against the parent's own signup later. Email stays
// optional even within the group.
const schema = z
  .object({
    admission_number: z.string().min(1, 'Admission number is required'),
    full_name: z.string().min(2, 'Enter the student\'s full name'),
    class_id: z.string().optional(),
    date_of_birth: z.string().optional(),
    guardian_full_name: z.string().optional(),
    guardian_phone: z.string().optional(),
    guardian_email: z.string().optional(),
    guardian_relationship_type: z.string().optional(),
  })
  .superRefine((values, ctx) => {
    const wantsGuardian =
      values.guardian_full_name || values.guardian_phone || values.guardian_email;
    if (!wantsGuardian) return;

    if (!values.guardian_full_name || values.guardian_full_name.trim().length < 2) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['guardian_full_name'],
        message: "Enter the parent's full name",
      });
    }
    if (!values.guardian_phone || values.guardian_phone.trim().length < 7) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['guardian_phone'],
        message: 'Enter a valid phone number',
      });
    }
    if (values.guardian_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.guardian_email)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['guardian_email'],
        message: 'Enter a valid email',
      });
    }
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
        guardian_full_name: values.guardian_phone ? values.guardian_full_name : undefined,
        guardian_phone: values.guardian_phone || undefined,
        guardian_email: values.guardian_phone ? values.guardian_email || undefined : undefined,
        guardian_relationship_type: values.guardian_phone ? values.guardian_relationship_type : undefined,
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
        <p className="text-sm font-medium text-ink-900 mb-1">Parent / guardian (optional)</p>
        <p className="text-xs text-ink-600 mb-4">
          Fill this in and the parent gets connected to this child automatically the moment they sign up with
          this phone number — they choose their own password, you're not setting one for them.
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
        placeholder="e.g. +254712345678"
        error={errors.guardian_phone?.message}
        {...register('guardian_phone')}
      />
      <TextField
        label="Email (optional)"
        type="email"
        placeholder="e.g. wanjiru@example.com"
        error={errors.guardian_email?.message}
        {...register('guardian_email')}
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
