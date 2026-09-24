import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from './ui/Button';
import { TextField } from './ui/TextField';
import { getMyProfile, updateMyProfile } from '../api/user';
import { getErrorMessage } from '../api/client';
import { useAuthStore } from '../store/authStore';

const schema = z.object({
  full_name: z.string().min(2, 'Enter your full name'),
  phone: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

interface EditStaffProfileFormProps {
  onSuccess: () => void;
  onCancel: () => void;
}

// Staff accounts (school admin, bursar, teacher) are usually created once —
// by the setup wizard, or by hand while testing the API directly — so a
// typo or a leftover placeholder in the name has had no way to get fixed
// since. This mirrors the parent side's self-service phone/email editing.
// Fetches the profile itself (rather than taking it as props) because the
// login response doesn't include phone — only /api/users/me does.
export function EditStaffProfileForm({ onSuccess, onCancel }: EditStaffProfileFormProps) {
  const updateUser = useAuthStore((s) => s.updateUser);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { full_name: '', phone: '' } });

  useEffect(() => {
    getMyProfile()
      .then((profile) => reset({ full_name: profile.full_name, phone: profile.phone ?? '' }))
      .catch((err: unknown) => setLoadError(getErrorMessage(err, 'Could not load your profile.')))
      .finally(() => setLoading(false));
  }, [reset]);

  async function onSubmit(values: FormValues) {
    try {
      const updated = await updateMyProfile({
        full_name: values.full_name.trim(),
        phone: values.phone?.trim() || undefined,
      });
      updateUser({ full_name: updated.full_name, phone: updated.phone });
      onSuccess();
    } catch (err: unknown) {
      setError('root', { message: getErrorMessage(err, 'Could not save your details. Try again.') });
    }
  }

  if (loading) {
    return <p className="text-sm text-ink-600">Loading…</p>;
  }

  if (loadError) {
    return <p className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">{loadError}</p>;
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <TextField label="Full name" error={errors.full_name?.message} {...register('full_name')} />
      <TextField
        label="Phone number (optional)"
        type="tel"
        placeholder="e.g. +254712345678"
        error={errors.phone?.message}
        {...register('phone')}
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
          {isSubmitting ? 'Saving…' : 'Save'}
        </Button>
      </div>
    </form>
  );
}
