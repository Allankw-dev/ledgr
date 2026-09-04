import { useEffect, useState } from 'react';
import { UserCheck, Check, X } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Button } from '../components/ui/Button';
import { listPendingRequests, approveRequest, rejectRequest, type PendingGuardianRequest } from '../api/guardianRequests';

export function GuardianRequestsPage() {
  const [requests, setRequests] = useState<PendingGuardianRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actingOn, setActingOn] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setRequests(await listPendingRequests());
    } catch {
      setError('Could not load pending requests.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleApprove(id: string) {
    setActingOn(id);
    try {
      await approveRequest(id);
      setRequests((prev) => prev.filter((r) => r.id !== id));
    } catch {
      setError('Could not approve this request. Try again.');
    } finally {
      setActingOn(null);
    }
  }

  async function handleReject(id: string) {
    setActingOn(id);
    try {
      await rejectRequest(id);
      setRequests((prev) => prev.filter((r) => r.id !== id));
    } catch {
      setError('Could not reject this request. Try again.');
    } finally {
      setActingOn(null);
    }
  }

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-8 py-8">
        <div className="mb-8">
          <h1 className="font-display text-2xl text-ink-900 font-medium">Parent requests</h1>
          <p className="text-sm text-ink-600 mt-1">
            Parents who signed up and linked themselves to a student, awaiting your confirmation.
          </p>
        </div>

        {error && (
          <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm mb-6">
            {error}
          </div>
        )}

        <div className="bg-white border border-ink-200 rounded-lg overflow-hidden">
          {loading ? (
            <div className="px-5 py-16 text-center text-sm text-ink-600">Loading…</div>
          ) : requests.length === 0 ? (
            <div className="px-5 py-16 text-center">
              <UserCheck className="w-8 h-8 text-ink-400 mx-auto mb-3" strokeWidth={1.5} />
              <p className="text-sm text-ink-900 font-medium">No pending requests</p>
              <p className="text-xs text-ink-600 mt-1">New parent sign-ups will appear here for review.</p>
            </div>
          ) : (
            <div className="divide-y divide-ink-100">
              {requests.map((req) => (
                <div key={req.id} className="px-5 py-4 flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-ink-900">
                      {req.parent_name} <span className="text-ink-400 font-normal">({req.relationship_type})</span>
                    </p>
                    <p className="text-xs text-ink-600">{req.parent_email}</p>
                    <p className="text-xs text-ink-600 mt-0.5">
                      requesting access to <span className="font-medium text-ink-900">{req.student_name}</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      variant="secondary"
                      onClick={() => handleReject(req.id)}
                      disabled={actingOn === req.id}
                      className="text-xs px-3 py-1.5 flex items-center gap-1"
                    >
                      <X className="w-3.5 h-3.5" /> Reject
                    </Button>
                    <Button
                      onClick={() => handleApprove(req.id)}
                      disabled={actingOn === req.id}
                      className="text-xs px-3 py-1.5 flex items-center gap-1"
                    >
                      <Check className="w-3.5 h-3.5" /> Approve
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
