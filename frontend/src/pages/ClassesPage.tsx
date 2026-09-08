import { useState, type FormEvent } from 'react';
import { GraduationCap, Plus } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Button } from '../components/ui/Button';
import { TextField } from '../components/ui/TextField';
import { useClasses } from '../hooks/useSchoolSetup';
import { createClass } from '../api/school';

export function ClassesPage() {
  const { classes, loading, refetch } = useClasses();
  const [name, setName] = useState('');
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);

  async function handleAdd(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setAdding(true);
    setError(null);
    try {
      await createClass(name.trim());
      setName('');
      refetch();
    } catch {
      setError('Could not add this grade. It may already exist.');
    } finally {
      setAdding(false);
    }
  }

  async function handleSeedGradesOneToNine() {
    setSeeding(true);
    setError(null);
    const existingNames = new Set(classes.map((c) => c.name.toLowerCase()));
    const wanted = Array.from({ length: 9 }, (_, i) => `Grade ${i + 1}`);
    const missing = wanted.filter((n) => !existingNames.has(n.toLowerCase()));
    try {
      for (const gradeName of missing) {
        await createClass(gradeName);
      }
      refetch();
    } catch {
      setError('Could not create all grades. Whatever went through is saved — try again for the rest.');
    } finally {
      setSeeding(false);
    }
  }

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto px-8 py-8">
        <div className="mb-6">
          <h1 className="font-display text-2xl text-ink-900 font-medium flex items-center gap-2">
            <GraduationCap className="w-5 h-5" strokeWidth={1.75} />
            Grades
          </h1>
          <p className="text-sm text-ink-600 mt-1">
            Set up the grades students belong to. Each grade can get its own announcements and fee structures,
            independent of the rest of the school — the whole-school option stays available wherever you send a
            notice.
          </p>
        </div>

        <div className="bg-white border border-ink-200 rounded-lg p-6 flex flex-col gap-4 mb-6">
          <form onSubmit={handleAdd} className="flex items-end gap-3">
            <div className="flex-1">
              <TextField
                label="Grade name"
                placeholder="e.g. Grade 1"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={adding || !name.trim()} className="flex items-center gap-2">
              <Plus className="w-4 h-4" strokeWidth={2} />
              {adding ? 'Adding…' : 'Add grade'}
            </Button>
          </form>

          {classes.length === 0 && !loading && (
            <div className="border-t border-ink-100 pt-4">
              <p className="text-sm text-ink-600 mb-3">No grades set up yet.</p>
              <Button variant="secondary" onClick={handleSeedGradesOneToNine} disabled={seeding}>
                {seeding ? 'Creating…' : 'Quick setup: create Grade 1–9'}
              </Button>
            </div>
          )}

          {error && (
            <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm">
              {error}
            </div>
          )}
        </div>

        <div className="bg-white border border-ink-200 rounded-lg overflow-hidden">
          {loading ? (
            <div className="px-5 py-16 text-center text-sm text-ink-600">Loading grades…</div>
          ) : classes.length === 0 ? (
            <div className="px-5 py-16 text-center">
              <GraduationCap className="w-8 h-8 text-ink-400 mx-auto mb-3" strokeWidth={1.5} />
              <p className="text-sm text-ink-900 font-medium">No grades yet</p>
              <p className="text-xs text-ink-600 mt-1">Add one above, or use the quick setup for Grade 1–9.</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-ink-600">
                  <th className="px-5 py-2 font-medium">Name</th>
                </tr>
              </thead>
              <tbody>
                {classes.map((c) => (
                  <tr key={c.id} className="h-9 text-ink-900 border-t border-ink-100">
                    <td className="px-5">{c.name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </AppShell>
  );
}
