import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { SelectField } from './ui/SelectField';
import { linkGuardian } from '../api/parent';

const RELATIONSHIPS = ['mother', 'father', 'guardian'] as const;

const schema = z.object({
  email: z.string().email('Enter a valid email'),
  full_name: z.string().min(2, 'Enter the parent\'s full name'),
  phone: z.string().optional(),
  password: z.string().min(8, 'At least 8 characters — this is only used if the parent doesn\'t have an account yet'),
  relationship_type: z.enum(RELATIONSHIPS),
});

type FormValues = z.infer<typeof schema>;

interface LinkGuardianFormProps {
  studentId: string;
  onSuccess: () => void;
  onCancel: () => void;
}

export function LinkGuardianForm({ studentId, onSuccess, onCancel }: LinkGuardianFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { relationship_type: 'guardian' } });

  async function onSubmit(values: FormValues) {
    try {
      await linkGuardian(studentId, values);
      onSuccess();
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: string } } })?.response?.data?.error ||
        'Could not link this guardian. Check the details and try again.';
      setError('root', { message });
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <p className="text-xs text-ink-600">
        This gives the parent their own login to view this child's balance and payment history. If the email is
        already registered as a parent, they'll just be linked to this child too — their existing password stays
        unchanged.
      </p>

      <TextField label="Parent's email" type="email" error={errors.email?.message} {...register('email')} />
      <TextField label="Parent's full name" error={errors.full_name?.message} {...register('full_name')} />
      <TextField
        label="Phone number (optional)"
        type="tel"
        placeholder="e.g. +254712345678"
        error={errors.phone?.message}
        {...register('phone')}
      />
      <TextField
        label="Temporary password"
        type="text"
        placeholder="Share this with the parent to log in"
        error={errors.password?.message}
        {...register('password')}
      />
      <SelectField
        label="Relationship"
        error={errors.relationship_type?.message}
        options={RELATIONSHIPS.map((r) => ({ value: r, label: r.charAt(0).toUpperCase() + r.slice(1) }))}
        {...register('relationship_type')}
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
          {isSubmitting ? 'Linking…' : 'Link guardian'}
        </Button>
      </div>
    </form>
  );
}
