import { initialsOf } from './format';

const GRADIENTS = [
  'from-lime to-emerald-800',
  'from-sky to-cyan',
  'from-amber to-coral',
  'from-[#C4B5FD] to-[#6366F1]',
  'from-[#F9A8D4] to-[#EC4899]',
];

function hash(s: string) {
  let h = 0;
  for (const ch of s) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return h;
}

/** Initials on a gradient picked from the name, so the same person always gets the same colour. */
export function Avatar({ name, size = 36, className = '' }: { name: string; size?: number; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br ${GRADIENTS[hash(name) % GRADIENTS.length]} font-semibold text-[#0B1203] ${className}`}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.38) }}
    >
      {initialsOf(name)}
    </span>
  );
}
