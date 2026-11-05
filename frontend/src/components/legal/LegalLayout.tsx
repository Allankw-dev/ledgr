import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { LEGAL_UPDATED } from '../../config/legal';
import { SiteFooter } from '../SiteFooter';

/** Shared frame for the four public legal pages. No sign-in needed to read them. */
export function LegalLayout({ title, intro, children }: { title: string; intro?: string; children: ReactNode }) {
  return (
    <div className="min-h-dvh flex flex-col">
      <main id="main-content" className="flex-1 w-full max-w-3xl mx-auto px-5 py-8 sm:py-12">
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-ink-700 hover:text-ink-900 mb-6">
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          Back to Ledgr
        </Link>
        <h1 className="font-display text-3xl text-ink-900 font-medium mb-1">{title}</h1>
        <p className="text-xs text-ink-600 mb-4">Last updated {LEGAL_UPDATED}</p>
        {intro && <p className="text-sm text-ink-700 leading-relaxed mb-2">{intro}</p>}
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}

export function H2({ children }: { children: ReactNode }) {
  return <h2 className="font-display text-lg text-ink-900 font-medium mt-8 mb-2">{children}</h2>;
}

export function P({ children }: { children: ReactNode }) {
  return <p className="text-sm text-ink-700 leading-relaxed mb-3">{children}</p>;
}

export function UL({ children }: { children: ReactNode }) {
  return <ul className="list-disc pl-5 text-sm text-ink-700 leading-relaxed mb-3 flex flex-col gap-1.5">{children}</ul>;
}

/** Shown where the operator has not filled in a detail yet, so a gap is visible instead of silently hidden. */
export function ToAdd({ what }: { what: string }) {
  return (
    <span className="rounded border border-amber/40 bg-amber-100 px-1.5 py-0.5 text-xs text-amber">
      [operator to add: {what}]
    </span>
  );
}
