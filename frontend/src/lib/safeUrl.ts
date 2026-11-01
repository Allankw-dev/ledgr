/**
 * Only http(s) and blob URLs may ever be put in an href / src that came from data. A `javascript:` or `data:`
 * URL in a link is script execution waiting to happen, so anything else becomes undefined and renders as a
 * dead link instead.
 *
 * The attachment URLs the app gets today come from our own backend (signed, expiring links), so this is a
 * second wall, not the first: it keeps working even if that backend response were ever tampered with.
 */
export function safeUrl(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  try {
    // A base is needed so relative URLs parse; they resolve to the page's own http(s) origin, which is fine.
    const parsed = new URL(value, window.location.origin);
    return ['http:', 'https:', 'blob:'].includes(parsed.protocol) ? value : undefined;
  } catch {
    return undefined;
  }
}
