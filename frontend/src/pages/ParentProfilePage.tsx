import { useEffect, useState } from 'react';
import { ParentShell } from '../components/ParentShell';
import { UpdatePhoneForm } from '../components/UpdatePhoneForm';
import { getMyProfile, type MyProfile } from '../api/user';

export function ParentProfilePage() {
  const [profile, setProfile] = useState<MyProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMyProfile()
      .then(setProfile)
      .finally(() => setLoading(false));
  }, []);

  return (
    <ParentShell>
      <h1 className="font-display text-2xl text-ink-900 font-medium mb-1">Profile</h1>
      <p className="text-sm text-ink-600 mb-6">Your account and contact details.</p>

      {loading ? (
        <p className="text-sm text-ink-600">Loading…</p>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="bg-panel border border-ink-200 rounded-lg px-5 py-4">
            <p className="text-xs text-ink-600 mb-1">Name</p>
            <p className="text-sm text-ink-900 font-medium mb-3">{profile?.full_name}</p>
            <p className="text-xs text-ink-600 mb-1">Email</p>
            <p className="text-sm text-ink-900 font-medium">{profile?.email}</p>
          </div>

          <div className="bg-panel border border-ink-200 rounded-lg px-5 py-4">
            <UpdatePhoneForm currentPhone={profile?.phone ?? null} onUpdated={(phone) => setProfile((p) => (p ? { ...p, phone } : p))} />
          </div>

          <div className="bg-ink-100 border border-ink-200 rounded-lg px-5 py-4">
            <p className="text-sm text-ink-900 font-medium mb-1">Password and two-factor authentication</p>
            <p className="text-xs text-ink-600">
              Not available for parent accounts yet — reach out to the school office if you need help signing in.
            </p>
          </div>
        </div>
      )}
    </ParentShell>
  );
}
