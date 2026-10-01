import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { UserPlus, Users, UserCog, UserMinus, Pencil, ChevronDown, ChevronRight, Plus, Search, X } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Button } from '../components/ui/Button';
import { MultiGradeSelect } from '../components/ui/MultiGradeSelect';
import { Modal } from '../components/ui/Modal';
import { StudentDetailsPanel } from '../components/StudentDetailsPanel';
import { AddStudentForm } from '../components/AddStudentForm';
import { EditStudentForm } from '../components/EditStudentForm';
import { LinkGuardianForm } from '../components/LinkGuardianForm';
import { useStudents } from '../hooks/useStudents';
import { useClasses } from '../hooks/useSchoolSetup';
import { deactivateStudent, updateStudentClass } from '../api/school';
import type { GuardianResponse } from '../api/parent';
import type { Student } from '../types';

export function StudentsPage() {
  const [classFilter, setClassFilter] = useState<string[]>([]);
  const { students, loading, error, refetch } = useStudents(classFilter);
  const { classes } = useClasses();
  const [showAddModal, setShowAddModal] = useState(false);
  const [addClassId, setAddClassId] = useState<string | undefined>(undefined);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [openDetails, setOpenDetails] = useState<Set<string>>(new Set());
  const autoOpened = useRef<string | null>(null);
  const [editTarget, setEditTarget] = useState<Student | null>(null);
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

  const classNameById = new Map(classes.map((c) => [c.id, c.name]));
  const groupLabel = (classId: string | null) =>
    classId ? classNameById.get(classId) ?? 'Unknown grade' : 'Unassigned';

  // Search by name or admission number (every student is already loaded, so this is instant).
  const searchTerms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const searching = searchTerms.length > 0;
  const visibleStudents = useMemo(() => {
    if (!searching) return students;
    return students.filter((st) => {
      const hay = `${st.full_name} ${st.admission_number}`.toLowerCase();
      return searchTerms.every((t) => hay.includes(t));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [students, query]);

  // One cluster per grade, in the order the API returns them (Grade 1 … 9, Unassigned last).
  const clusters = useMemo(() => {
    const map = new Map<string, Student[]>();
    for (const st of visibleStudents) {
      const key = st.class_id ?? '';
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(st);
    }
    return Array.from(map.entries()).map(([key, items]) => ({ key, classId: key || null, items }));
  }, [visibleStudents]);

  function toggleDetails(id: string) {
    setOpenDetails((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // Searching down to exactly one student: show their details straight away.
  useEffect(() => {
    if (searching && visibleStudents.length === 1) {
      const only = visibleStudents[0].id;
      if (autoOpened.current !== only) {
        autoOpened.current = only;
        setOpenDetails((prev) => new Set(prev).add(only));
      }
    } else if (!searching) {
      autoOpened.current = null;
    }
  }, [searching, visibleStudents]);

  function toggleCluster(key: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function openAdd(classId?: string) {
    setAddClassId(classId);
    setShowAddModal(true);
  }

  // After adding: open the new student's cluster, scroll to them and flash the row.
  function handleAdded(created: Student) {
    setShowAddModal(false);
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.delete(created.class_id ?? '');
      return next;
    });
    setQuery('');
    setHighlightId(created.id);
    refetch();
  }

  useEffect(() => {
    if (!highlightId || loading) return;
    const el = document.getElementById(`student-${highlightId}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    const t = setTimeout(() => setHighlightId(null), 4000);
    return () => clearTimeout(t);
  }, [highlightId, loading, students]);

  function handleGuardianLinked(result: GuardianResponse) {
    setLinkedNotice(
      result.status === 'linked'
        ? `${result.full_name} is linked to ${guardianTarget?.full_name} and can log in now.`
        : `Saved. When ${result.full_name} signs up with ${result.phone}, they'll be connected to ${guardianTarget?.full_name} automatically.`
    );
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
      <div className="max-w-6xl mx-auto px-4 sm:px-8 py-6 sm:py-8">
        <div className="flex items-start justify-between mb-8 flex-wrap gap-3">
          <div>
            <h1 className="font-display text-2xl text-ink-900 font-medium">Students</h1>
            <p className="text-sm text-ink-600 mt-1">
              {loading
                ? 'Loading…'
                : searching
                  ? `${visibleStudents.length} of ${students.length} student${students.length === 1 ? '' : 's'} match`
                  : `${students.length} student${students.length === 1 ? '' : 's'} in ${clusters.length} grade group${clusters.length === 1 ? '' : 's'}`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <MultiGradeSelect
              variant="dropdown"
              classes={classes}
              value={classFilter}
              allLabel="All grades"
              onChange={(ids) => {
                setClassFilter(ids);
              }}
            />
            <Button onClick={() => openAdd(classFilter.length === 1 ? classFilter[0] : undefined)} className="flex items-center gap-2">
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

        {!loading && students.length > 0 && (
          <div className="relative mb-5">
            <Search className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name or admission number"
              aria-label="Search students"
              className="w-full pl-9 pr-9 py-2.5 rounded-md border border-ink-200 bg-panel text-ink-900 text-sm placeholder:text-ink-400 focus-visible:outline-2 focus-visible:outline-ink-600"
            />
            {query && (
              <button
                onClick={() => setQuery('')}
                aria-label="Clear search"
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-900"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        )}

        {loading ? (
          <div className="bg-panel border border-ink-200 rounded-lg px-5 py-16 text-center text-sm text-ink-600">Loading students…</div>
        ) : students.length === 0 ? (
          <div className="bg-panel border border-ink-200 rounded-lg px-5 py-16 text-center">
            <Users className="w-8 h-8 text-ink-400 mx-auto mb-3" strokeWidth={1.5} />
            <p className="text-sm text-ink-900 font-medium">No students yet</p>
            <p className="text-xs text-ink-600 mt-1 mb-4">Add your first student to start tracking their fees.</p>
            <Button variant="secondary" onClick={() => openAdd()}>
              Add student
            </Button>
          </div>
        ) : visibleStudents.length === 0 ? (
          <div className="bg-panel border border-ink-200 rounded-lg px-5 py-12 text-center">
            <p className="text-sm text-ink-900 font-medium">No student matches “{query.trim()}”</p>
            <p className="text-xs text-ink-600 mt-1 mb-4">Check the spelling or try part of the admission number.</p>
            <Button variant="secondary" onClick={() => setQuery('')}>
              Clear search
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            {clusters.map((cluster) => {
              // While searching, always show the matches even inside a folded grade.
              const isCollapsed = !searching && collapsed.has(cluster.key);
              return (
                <section key={cluster.key || 'unassigned'} className="bg-panel border border-ink-200 rounded-lg overflow-hidden">
                  <div className="flex items-center justify-between gap-3 px-5 py-3 bg-ink-100">
                    <button
                      onClick={() => toggleCluster(cluster.key)}
                      aria-expanded={!isCollapsed}
                      className="flex items-center gap-2 text-left"
                    >
                      {isCollapsed ? <ChevronRight className="w-4 h-4 text-ink-600" /> : <ChevronDown className="w-4 h-4 text-ink-600" />}
                      <span className="text-sm font-semibold text-ink-900">{groupLabel(cluster.classId)}</span>
                      <span className="text-xs text-ink-600">
                        {cluster.items.length} student{cluster.items.length === 1 ? '' : 's'}
                      </span>
                    </button>
                    <button
                      onClick={() => openAdd(cluster.classId ?? undefined)}
                      className="text-xs font-medium text-ink-900 hover:underline underline-offset-2 flex items-center gap-1"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      {cluster.classId ? `Add to ${groupLabel(cluster.classId)}` : 'Add student'}
                    </button>
                  </div>
                  {!isCollapsed && (
                    <div className="ledger-lines overflow-x-auto">
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
                          {cluster.items.map((s) => (
                            <Fragment key={s.id}>
                            <tr
                              id={`student-${s.id}`}
                              className={`h-9 text-ink-900 transition-colors ${highlightId === s.id ? 'bg-emerald-100' : ''}`}
                            >
                              <td className="px-5 figure text-ink-600">{s.admission_number}</td>
                              <td className="px-5">
                                {s.full_name}
                                {highlightId === s.id && (
                                  <span className="ml-2 text-xs font-medium text-emerald-700">Just added</span>
                                )}
                              </td>
                              <td className="px-5">
                                <select
                                  value={s.class_id || ''}
                                  onChange={(e) => handleClassChange(s, e.target.value)}
                                  disabled={classUpdatingId === s.id}
                                  className="px-2 py-1 rounded-md border border-ink-200 bg-panel text-ink-900 text-xs focus-visible:outline-2 focus-visible:outline-ink-600 disabled:opacity-50"
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
                                    onClick={() => toggleDetails(s.id)}
                                    aria-expanded={openDetails.has(s.id)}
                                    className="text-xs font-medium text-ink-900 hover:underline underline-offset-2 flex items-center gap-1"
                                  >
                                    {openDetails.has(s.id) ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />} Details
                                  </button>
                                  <button
                                    onClick={() => setEditTarget(s)}
                                    className="text-xs font-medium text-ink-900 hover:underline underline-offset-2 flex items-center gap-1"
                                  >
                                    <Pencil className="w-3.5 h-3.5" /> Edit
                                  </button>
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
                            {openDetails.has(s.id) && (
                              <tr>
                                <td colSpan={5} className="bg-ink-800 border-y border-ink-200 p-0">
                                  <StudentDetailsPanel studentId={s.id} />
                                </td>
                              </tr>
                            )}
                            </Fragment>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              );
            })}
          </div>
        )}
      </div>

      {showAddModal && (
        <Modal title="Add student" onClose={() => setShowAddModal(false)}>
          <AddStudentForm onSuccess={handleAdded} onCancel={() => setShowAddModal(false)} defaultClassId={addClassId} />
        </Modal>
      )}

      {editTarget && (
        <Modal title={`Edit — ${editTarget.full_name}`} onClose={() => setEditTarget(null)}>
          <EditStudentForm
            student={editTarget}
            onSuccess={() => { setEditTarget(null); refetch(); }}
            onCancel={() => setEditTarget(null)}
          />
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
