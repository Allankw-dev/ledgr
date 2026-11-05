/**
 * Who runs this Ledgr and how to reach them. Shown in the footer and on the Privacy Policy, Terms and Refund
 * Policy. Set these as Vercel environment variables (see docs/COMPLIANCE.md). Nothing here is invented: a field
 * left empty shows a visible "operator to add" notice instead of made-up details.
 */
const env = import.meta.env as Record<string, string | undefined>;

/** Keep equal to TERMS_VERSION in backend/app/core/legal.py. Bump both when the Terms or Privacy Policy change. */
export const LEGAL_VERSION = '2026-11-05';
export const LEGAL_UPDATED = '5 November 2026';

export const OPERATOR = {
  /** Registered name of the business or person running this service. */
  name: env.VITE_LEGAL_ENTITY?.trim() || '',
  /** Business / company registration number, if registered. */
  registration: env.VITE_LEGAL_REG_NO?.trim() || '',
  /** Physical or postal address. */
  address: env.VITE_LEGAL_ADDRESS?.trim() || '',
  /** Where privacy requests, complaints and legal notices go. */
  email: env.VITE_LEGAL_EMAIL?.trim() || '',
  phone: env.VITE_LEGAL_PHONE?.trim() || '',
  /** Registration number with Kenya's Office of the Data Protection Commissioner (ODPC), if registered. */
  odpcRegistration: env.VITE_ODPC_REG_NO?.trim() || '',
};
