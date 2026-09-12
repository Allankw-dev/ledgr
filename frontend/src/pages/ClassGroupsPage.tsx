import { AppShell } from '../components/AppShell';
import { ClassGroupChat } from '../components/ClassGroupChat';

export function ClassGroupsPage() {
  return (
    <AppShell>
      <div className="max-w-6xl mx-auto px-4 sm:px-8 py-6 sm:py-8">
        <div className="mb-6">
          <h1 className="font-display text-2xl text-ink-900 font-medium reveal">Class groups</h1>
          <p className="text-sm text-ink-600 mt-1">
            One conversation per grade — like a class WhatsApp group for parents, teachers, and the school office.
          </p>
        </div>
        <ClassGroupChat />
      </div>
    </AppShell>
  );
}
