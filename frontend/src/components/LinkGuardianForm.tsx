import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { SelectField } from './ui/SelectField';
import { linkGuardian, type GuardianResponse } from '../api/parent';
import { getErrorMessage } from '../api/client';

const RELATIONSHIPS = ['mother', 'father', 'guardian'] as const;

const schema = z.object({
  full_name: z.string().min(2, "Enter the parent's full name"),
  phone: z.string().min(7, 'Enter a valid phone number'),
  relationship_type: z.enum(RELATIONSHIPS),
});

type FormValues = z.infer<typeof schema>;

interface LinkGuardianFormProps {
  studentId: string;
  onSuccess: (result: GuardianResponse) => void;
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
      const result = await linkGuardian(studentId, values);
      onSuccess(result);
    } catch (err: unknown) {
      setError('root', { message: getErrorMessage(err, 'Could not link this guardian. Check the details and try again.') });
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <p className="text-xs text-ink-600">
        If this phone number already has a parent account (e.g. another child at this school), they're linked
        right away. Otherwise we just save these details — the parent gets connected automatically, with their
        own password, the moment they sign up using this same name and phone number.
      </p>

      <TextField label="Parent's full name" error={errors.full_name?.message} {...register('full_name')} />
      <TextField
        label="Parent's phone number"
        type="tel"
        placeholder="e.g. 0712 345 678"
        error={errors.phone?.message}
        {...register('phone')}
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
          {isSubmitting ? 'Saving…' : 'Save parent'}
        </Button>
      </div>
    </form>
  );
}
