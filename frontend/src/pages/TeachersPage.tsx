import { useState, type FormEvent } from 'react';
import { GraduationCap, Plus, Mail } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Button } from '../components/ui/Button';
import { TextField } from '../components/ui/TextField';
import { useClasses } from '../hooks/useSchoolSetup';
import { listTeachers, createTeacher, updateTeacherClasses } from '../api/teachers';
import { useEffect } from 'react';
import type { Teacher } from '../types';

export function TeachersPage() {
  const { classes } = useClasses();
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [loading, setLoading] = useState(true);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [selectedClasses, setSelectedClasses] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [justAdded, setJustAdded] = useState<string | null>(null);
  const [savingClassesFor, setSavingClassesFor] = useState<string | null>(null);

  function refetch() {
    setLoading(true);
    listTeachers()
      .then(setTeachers)
      .catch(() => setError('Could not load teachers.'))
      .finally(() => setLoading(false));
  }

  useEffect(refetch, []);

  function toggleClass(classId: string) {
    setSelectedClasses((prev) => {
      const next = new Set(prev);
      if (next.has(classId)) next.delete(classId);
      else next.add(classId);
      return next;
    });
  }

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    if (!fullName.trim() || !email.trim()) return;
    setSubmitting(true);
    setError(null);
    setJustAdded(null);
    try {
      const teacher = await createTeacher(fullName.trim(), email.trim(), Array.from(selectedClasses));
      setFullName('');
      setEmail('');
      setSelectedClasses(new Set());
      setJustAdded(teacher.email);
      refetch();
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Could not add this teacher. Check the details and try again.';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleTeacherClass(teacher: Teacher, classId: string) {
    const next = teacher.class_ids.includes(classId)
      ? teacher.class_ids.filter((id) => id !== classId)
      : [...teacher.class_ids, classId];
    setSavingClassesFor(teacher.id);
    try {
      await updateTeacherClasses(teacher.id, next);
      refetch();
    } catch {
      setError('Could not update this teacher\'s grades.');
    } finally {
      setSavingClassesFor(null);
    }
  }

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-8 py-8">
        <div className="mb-6">
          <h1 className="font-display text-2xl text-ink-900 font-medium reveal flex items-center gap-2">
            <GraduationCap className="w-5 h-5" strokeWidth={1.75} />
            Teachers
          </h1>
          <p className="text-sm text-ink-600 mt-1">
            Add a teacher and assign the grades they teach — that's what puts them in each grade's class group.
          </p>
        </div>

        <div className="bg-panel border border-ink-200 rounded-lg p-6 mb-6">
          <form onSubmit={handleAdd} className="flex flex-col gap-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <TextField label="Full name" placeholder="e.g. Grace Wambui" value={fullName} onChange={(e) => setFullName(e.target.value)} />
              <TextField label="Email" type="email" placeholder="grace@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>

            <div>
              <p className="text-sm font-medium text-ink-700 mb-2">Grades taught</p>
              <div className="flex flex-wrap gap-2">
                {classes.map((c) => (
                  <button
                    type="button"
                    key={c.id}
                    onClick={() => toggleClass(c.id)}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                      selectedClasses.has(c.id)
                        ? 'bg-emerald-100 text-emerald-700 border-emerald-700'
                        : 'border-ink-200 text-ink-600 hover:bg-ink-100'
                    }`}
                  >
                    {c.name}
                  </button>
                ))}
                {classes.length === 0 && <p className="text-xs text-ink-400">Set up grades first, under Grades.</p>}
              </div>
            </div>

            {error && (
              <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm">
                {error}
              </div>
            )}
            {justAdded && (
              <div className="bg-emerald-100 text-emerald-700 rounded-md px-4 py-3 text-sm flex items-center gap-2">
                <Mail className="w-4 h-4 shrink-0" strokeWidth={2} />
                Sent {justAdded} a link to set their password and get started.
              </div>
            )}

            <Button type="submit" disabled={submitting || !fullName.trim() || !email.trim()} className="self-start flex items-center gap-2">
              <Plus className="w-4 h-4" strokeWidth={2} />
              {submitting ? 'Adding…' : 'Add teacher'}
            </Button>
          </form>
        </div>

        <div className="bg-panel border border-ink-200 rounded-lg overflow-hidden">
          {loading ? (
            <div className="px-5 py-12 text-center text-sm text-ink-600">Loading teachers…</div>
          ) : teachers.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <p className="text-sm text-ink-900 font-medium">No teachers yet</p>
              <p className="text-xs text-ink-600 mt-1">Add one above to get started.</p>
            </div>
          ) : (
            <div className="divide-y divide-ink-100">
              {teachers.map((t) => (
                <div key={t.id} className="px-5 py-4">
                  <div className="flex items-center justify-between gap-3 mb-2.5">
                    <div>
                      <p className="text-sm font-medium text-ink-900">{t.full_name}</p>
                      <p className="text-xs text-ink-400">{t.email}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {classes.map((c) => {
                      const assigned = t.class_ids.includes(c.id);
                      return (
                        <button
                          key={c.id}
                          onClick={() => handleToggleTeacherClass(t, c.id)}
                          disabled={savingClassesFor === t.id}
                          className={`px-2.5 py-1 rounded-full text-[11px] font-medium border transition-colors disabled:opacity-50 ${
                            assigned
                              ? 'bg-emerald-100 text-emerald-700 border-emerald-700'
                              : 'border-ink-200 text-ink-400 hover:bg-ink-100'
                          }`}
                        >
                          {c.name}
                        </button>
                      );
                    })}
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
