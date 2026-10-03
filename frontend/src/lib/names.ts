// Titles people put at the front of their name. When one is present we keep
// it together with the first real name ("Dr Rebecca"), instead of greeting
// someone with just "Dr".
const TITLES = new Set([
  'dr', 'prof', 'professor', 'mr', 'mrs', 'ms', 'miss', 'mw', 'eng', 'engr', 'hon', 'rev', 'fr', 'sr',
  'sir', 'madam', 'mdm', 'pastor', 'bishop', 'adv', 'cpa', 'capt', 'col', 'maj', 'gen',
]);

function cap(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
}

function isTitle(word: string): boolean {
  return TITLES.has(word.toLowerCase().replace(/\.$/, ''));
}

/** "Dr. Rebecca Ndegwa" -> "Dr. Rebecca", "josh kamau" -> "Josh". */
export function friendlyName(fullName?: string | null): string {
  const parts = (fullName ?? '').trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '';
  if (isTitle(parts[0]) && parts.length > 1) {
    return `${cap(parts[0])} ${cap(parts[1])}`;
  }
  return cap(parts[0]);
}

/** Initial for an avatar: the first real name, skipping any title ("Dr Rebecca" -> "R"). */
export function nameInitial(fullName?: string | null): string {
  const parts = (fullName ?? '').trim().split(/\s+/).filter(Boolean);
  const real = parts.find((p) => !isTitle(p)) ?? parts[0] ?? '';
  return real.charAt(0).toUpperCase();
}
