import { ParentShell } from '../components/ParentShell';
import { ClassGroupChat } from '../components/ClassGroupChat';

export function ParentClassGroupPage() {
  return (
    <ParentShell>
      <div className="mb-6">
        <h1 className="font-display text-2xl text-ink-900 font-medium reveal">Class group</h1>
        <p className="text-sm text-ink-600 mt-1">
          Chat with your child's teacher, the school office, and other parents in their grade.
        </p>
      </div>
      <ClassGroupChat />
    </ParentShell>
  );
}
