import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { CheckCircle2, XCircle, Clock, School as SchoolIcon } from 'lucide-react';
import { ParentShell } from '../components/ParentShell';
import { Button } from '../components/ui/Button';
import { SelectField } from '../components/ui/SelectField';
import { lookupStudent, requestLink, type StudentLookupResult } from '../api/guardianRequests';

const RELATIONSHIPS = ['mother', 'father', 'guardian'] as const;

type Stage = 'loading' | 'found' | 'not-found' | 'confirming' | 'pending' | 'error';

export function VerifyChildPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const admissionNumber = (location.state as { admissionNumber?: string } | null)?.admissionNumber;

  const [stage, setStage] = useState<Stage>('loading');
  const [student, setStudent] = useState<StudentLookupResult | null>(null);
  const [relationship, setRelationship] = useState<string>('mother');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!admissionNumber) {
      navigate('/signup', { replace: true });
      return;
    }
    lookupStudent(admissionNumber)
      .then((result) => {
        setStudent(result);
        setStage('found');
      })
      .catch((err: unknown) => {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 404) {
          setStage('not-found');
        } else {
          setError('Something went wrong looking that up. Try again in a moment.');
          setStage('error');
        }
      });
  }, [admissionNumber, navigate]);

  async function handleConfirm() {
    if (!student) return;
    setStage('confirming');
    try {
      await requestLink(student.student_id, relationship);
      setStage('pending');
    } catch {
      setError('Could not send your request. Try again.');
      setStage('found');
    }
  }

  return (
    <ParentShell>
      <div className="max-w-md mx-auto">
        {stage === 'loading' && <p className="text-sm text-ink-600 text-center py-12">Looking that up…</p>}

        {stage === 'error' && (
          <div className="bg-white border border-ink-200 rounded-lg p-6 text-center">
            <p className="text-sm text-clay-700 mb-4">{error}</p>
            <Button variant="secondary" onClick={() => window.location.reload()}>
              Try again
            </Button>
          </div>
        )}

        {stage === 'not-found' && (
          <div className="bg-white border border-ink-200 rounded-lg p-6 text-center">
            <XCircle className="w-8 h-8 text-clay-600 mx-auto mb-3" strokeWidth={1.5} />
            <h1 className="font-display text-lg text-ink-900 mb-2">We couldn't verify that number</h1>
            <p className="text-sm text-ink-600 mb-6">
              Double-check the admission number and try again, or contact the school office if you're not
              sure what it is.
            </p>
            <Button onClick={() => navigate('/signup', { replace: true })}>Try a different number</Button>
          </div>
        )}

        {(stage === 'found' || stage === 'confirming') && student && (
          <div className="bg-white border border-ink-200 rounded-lg overflow-hidden">
            <div className="px-6 py-5 border-b border-ink-200 text-center">
              <SchoolIcon className="w-7 h-7 text-ink-400 mx-auto mb-2" strokeWidth={1.5} />
              <h1 className="font-display text-lg text-ink-900">Is this your child?</h1>
            </div>
            <div className="px-6 py-5">
              <p className="font-display text-xl text-ink-900 font-medium mb-1">{student.full_name}</p>
              <p className="text-sm text-ink-600 mb-4">
                {student.class_name || 'Class not set'} · {student.school_name}
              </p>

              <div className="mb-4">
                <SelectField
                  label="Your relationship to this student"
                  value={relationship}
                  onChange={(e) => setRelationship(e.target.value)}
                  options={RELATIONSHIPS.map((r) => ({ value: r, label: r.charAt(0).toUpperCase() + r.slice(1) }))}
                />
              </div>

              {error && <p className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2 mb-4">{error}</p>}

              <div className="flex flex-col gap-2">
                <Button onClick={handleConfirm} disabled={stage === 'confirming'} className="flex items-center justify-center gap-2">
                  <CheckCircle2 className="w-4 h-4" />
                  {stage === 'confirming' ? 'Sending…' : 'Yes, this is my child'}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => navigate('/signup', { replace: true })}
                  disabled={stage === 'confirming'}
                >
                  This isn't my child
                </Button>
              </div>
            </div>
          </div>
        )}

        {stage === 'pending' && (
          <div className="bg-white border border-ink-200 rounded-lg p-6 text-center">
            <Clock className="w-8 h-8 text-amber-600 mx-auto mb-3" strokeWidth={1.5} />
            <h1 className="font-display text-lg text-ink-900 mb-2">Sent for confirmation</h1>
            <p className="text-sm text-ink-600 mb-6">
              We've sent this to the school office to confirm. Once approved, you'll see your child's fee
              details here — this usually doesn't take long.
            </p>
            <Button onClick={() => navigate('/parent/dashboard')}>Go to my dashboard</Button>
          </div>
        )}
      </div>
    </ParentShell>
  );
}
