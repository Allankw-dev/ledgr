import { useState } from 'react';
import { UserPlus, Users, UserCog, UserMinus } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import { PaginationControls } from '../components/ui/PaginationControls';
import { AddStudentForm } from '../components/AddStudentForm';
import { LinkGuardianForm } from '../components/LinkGuardianForm';
import { useStudents } from '../hooks/useStudents';
import { useClasses } from '../hooks/useSchoolSetup';
import { deactivateStudent, updateStudentClass } from '../api/school';
import type { Student } from '../types';

export function StudentsPage() {
  const [classFilter, setClassFilter] = useState('');
  const { students, meta, setPage, loading, error, refetch } = useStudents(classFilter || undefined);
  const { classes } = useClasses();
  const [showAddModal, setShowAddModal] = useState(false);
  const [guardianTarget, setGuardianTarget] = useState<Student | null>(null);
  const [removeTarget, setRemoveTarget] = useState<Student | null>(null);
  const [removing, setRemoving] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const [linkedNotice, setLinkedNotice] = useState<string | null>(null);
  const [classUpdatingId, setClassUpdatingId] = useState<string | null>(null);

  async function handleClassChange(student: Student, classId: string) {
    setClassUpdatingId(student.id);
    try {
      await updateStudentClass(student.id, classId || null);
      refetch();
    } catch {
      // Leave as-is; refetch/no-op reverts the select.
    } finally {
      setClassUpdatingId(null);
    }
  }

  function handleAdded() {
    setShowAddModal(false);
    refetch();
  }

  function handleGuardianLinked() {
    setLinkedNotice(`Parent account linked to ${guardianTarget?.full_name}. Share the temporary password with them.`);
    setGuardianTarget(null);
  }

  async function handleConfirmRemove() {
    if (!removeTarget) return;
    setRemoving(true);
    setRemoveError(null);
    try {
      await deactivateStudent(removeTarget.id);
      setRemoveTarget(null);
      refetch();
    } catch {
      setRemoveError('Could not remove this student. Try again.');
    } finally {
      setRemoving(false);
    }
  }

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto px-8 py-8">
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="font-display text-2xl text-ink-900 font-medium">Students</h1>
            <p className="text-sm text-ink-600 mt-1">
              {loading ? 'Loading…' : `${meta?.total ?? students.length} student${(meta?.total ?? students.length) === 1 ? '' : 's'} enrolled`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={classFilter}
              onChange={(e) => {
                setClassFilter(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 rounded-md border border-ink-200 bg-white text-ink-900 text-sm focus-visible:outline-2 focus-visible:outline-ink-600"
            >
              <option value="">All grades</option>
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <Button onClick={() => setShowAddModal(true)} className="flex items-center gap-2">
              <UserPlus className="w-4 h-4" strokeWidth={2} />
              Add student
            </Button>
          </div>
        </div>

        {error && (
          <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm mb-6">
            {error}
          </div>
        )}

        {linkedNotice && (
          <div role="status" className="bg-emerald-100 text-emerald-700 rounded-md px-4 py-3 text-sm mb-6">
            {linkedNotice}
          </div>
        )}

        <div className="bg-white border border-ink-200 rounded-lg overflow-hidden">
          {loading ? (
            <div className="px-5 py-16 text-center text-sm text-ink-600">Loading students…</div>
          ) : students.length === 0 ? (
            <div className="px-5 py-16 text-center">
              <Users className="w-8 h-8 text-ink-400 mx-auto mb-3" strokeWidth={1.5} />
              <p className="text-sm text-ink-900 font-medium">No students yet</p>
              <p className="text-xs text-ink-600 mt-1 mb-4">Add your first student to start tracking their fees.</p>
              <Button variant="secondary" onClick={() => setShowAddModal(true)}>
                Add student
              </Button>
            </div>
          ) : (
            <div className="ledger-lines">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-ink-600">
                    <th className="px-5 py-2 font-medium">Admission no.</th>
                    <th className="px-5 py-2 font-medium">Name</th>
                    <th className="px-5 py-2 font-medium">Grade</th>
                    <th className="px-5 py-2 font-medium">Status</th>
                    <th className="px-5 py-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {students.map((s) => (
                    <tr key={s.id} className="h-9 text-ink-900">
                      <td className="px-5 figure text-ink-600">{s.admission_number}</td>
                      <td className="px-5">{s.full_name}</td>
                      <td className="px-5">
                        <select
                          value={s.class_id || ''}
                          onChange={(e) => handleClassChange(s, e.target.value)}
                          disabled={classUpdatingId === s.id}
                          className="px-2 py-1 rounded-md border border-ink-200 bg-white text-ink-900 text-xs focus-visible:outline-2 focus-visible:outline-ink-600 disabled:opacity-50"
                        >
                          <option value="">Unassigned</option>
                          {classes.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-5">
                        <span
                          className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                            s.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-ink-100 text-ink-400'
                          }`}
                        >
                          {s.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-5 text-right">
                        <div className="flex items-center justify-end gap-3">
                          <button
                            onClick={() => setGuardianTarget(s)}
                            className="text-xs font-medium text-ink-900 hover:underline underline-offset-2 flex items-center gap-1"
                          >
                            <UserCog className="w-3.5 h-3.5" /> Link parent
                          </button>
                          <button
                            onClick={() => setRemoveTarget(s)}
                            className="text-xs font-medium text-clay-700 hover:underline underline-offset-2 flex items-center gap-1"
                          >
                            <UserMinus className="w-3.5 h-3.5" /> Remove
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {meta && <PaginationControls meta={meta} onPageChange={setPage} />}
        </div>
      </div>

      {showAddModal && (
        <Modal title="Add student" onClose={() => setShowAddModal(false)}>
          <AddStudentForm onSuccess={handleAdded} onCancel={() => setShowAddModal(false)} />
        </Modal>
      )}

      {guardianTarget && (
        <Modal title={`Link parent — ${guardianTarget.full_name}`} onClose={() => setGuardianTarget(null)}>
          <LinkGuardianForm
            studentId={guardianTarget.id}
            onSuccess={handleGuardianLinked}
            onCancel={() => setGuardianTarget(null)}
          />
        </Modal>
      )}

      {removeTarget && (
        <Modal title="Remove student" onClose={() => setRemoveTarget(null)}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-ink-700">
              Remove <span className="font-medium text-ink-900">{removeTarget.full_name}</span> from active
              students — for example, if they've transferred to another school?
            </p>
            <p className="text-xs text-ink-600">
              Their invoice and payment history stays on record. They'll no longer appear in your active
              student list or be billed going forward. This can be undone by a bursar if needed.
            </p>
            {removeError && <p className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2">{removeError}</p>}
            <div className="flex justify-end gap-2 mt-2">
              <Button variant="secondary" onClick={() => setRemoveTarget(null)} disabled={removing}>
                Cancel
              </Button>
              <Button variant="danger" onClick={handleConfirmRemove} disabled={removing}>
                {removing ? 'Removing…' : 'Remove student'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </AppShell>
  );
}
