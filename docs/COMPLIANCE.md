# Legal and privacy compliance

What Ledgr does about the "20 things so your app doesn't get sued" checklist, where each item lives, and what you
(the operator) still have to do yourself. **This is engineering work, not legal advice.** Have a Kenyan lawyer read
the Privacy Policy, Terms and Refund Policy before launch.

## The 20 items

| # | Item | Status | Where |
|---|------|--------|-------|
| 1 | Privacy policy | Done (draft, needs legal review) | `/privacy`, `frontend/src/pages/legal/PrivacyPage.tsx` |
| 2 | Terms of service | Done (draft) | `/terms` |
| 3 | Refund policy | Done (draft) | `/refunds` |
| 4 | Cookie policy | Done. Ledgr sets **no cookies** | `/cookies` |
| 5 | Cookie consent banner | A notice, not a consent choice, because nothing non-essential is used | `components/CookieNotice.tsx` |
| 6 | Check form consents | Terms + Privacy tick box (unticked by default), checked again on the server, time and version stored | `AuthPage.tsx`, `routers/auth.py`, `users.terms_*` |
| 7 | No unnecessary data | Reviewed. Date of birth is optional; no national ID, card or health data is collected | see Privacy Policy section 2 |
| 8 | Audit third-party SDKs | Done, see inventory below. Google Fonts removed; Google sign-in script now loads only on sign-in/up pages | below |
| 9 | Remove dark patterns | Reviewed: no countdowns, urgency, pre-ticked boxes or hidden opt-outs. Consent boxes start unticked | n/a |
| 10 | Remove hidden fees | The pay dialog states Ledgr adds no fee; the amount requested equals the amount shown | `PayWithMpesa.tsx` |
| 11 | Remove fake reviews | None existed (no testimonials or ratings anywhere in the UI) | n/a |
| 12 | Remove unsupported claims | Chat privacy wording corrected (reported chats can be read by the school admin); "your details stay private" replaced with a factual line | `DirectChat.tsx`, `AuthPage.tsx` |
| 13 | Accessibility alt text | Attachment preview images now have descriptive alt text; icons are decorative | `ClassGroupChat.tsx`, `DirectChat.tsx` |
| 14 | Fix color contrast | `ink-400` text was 2.9 to 3.3:1; now 4.7 to 5.4:1. Every text colour in use passes WCAG AA 4.5:1 | `index.css` |
| 15 | Keyboard navigation | Skip link, focus moves into and is trapped inside dialogs, returns on close, expandable invoice rows have a real button | `SkipLink.tsx`, `hooks/useFocusTrap.ts` |
| 16 | Add business details | Footer + legal pages read them from env vars. **You must set them** (below) | `config/legal.ts` |
| 17 | Age/guardian consent for kids' data | Sign-up requires confirming the person is 18+ and the child's parent/guardian; enforced on the server | `AuthPage.tsx`, `routers/auth.py` |
| 18 | Unsubscribe link in emails | Reminders, overdue notices and announcements carry an unsubscribe link and one-click headers and skip opted-out people. Receipts and security mail always send | `core/unsubscribe.py`, `routers/privacy.py`, `/unsubscribe` |
| 19 | License fonts and images | Fonts are self-hosted under the SIL OFL 1.1. See inventory | below |
| 20 | Data deletion request | Parents can erase their own account (Profile, Privacy & data). Staff ask their school admin | `services/account_deletion.py` |

## What you still need to do

1. **Set your business details** as Vercel environment variables (all optional, but the legal pages show an amber
   "operator to add" marker until they are set):
   `VITE_LEGAL_ENTITY`, `VITE_LEGAL_ADDRESS`, `VITE_LEGAL_EMAIL` (where privacy requests go), `VITE_LEGAL_PHONE`,
   `VITE_LEGAL_REG_NO`, `VITE_ODPC_REG_NO`.
2. **Run the migration** `alembic upgrade head` (adds consent, opt-out and deletion columns to `users`).
3. **Deploy the backend and frontend together.** The backend now refuses parent sign-up without the two consent
   flags, which only the new frontend sends.
4. **Optional:** set `API_PUBLIC_URL` on the backend (for example `https://your-api.onrender.com`) so mail apps show
   their own one-tap Unsubscribe button. Without it, the footer link still works.
5. **Register with the Office of the Data Protection Commissioner (ODPC)** if the law requires it for you or for
   your schools, and put the registration number in `VITE_ODPC_REG_NO`. Ask your lawyer whether you need a data
   processing agreement with each school (the school is the controller of student data; you are its processor).
6. **Have a lawyer review** the three policies, especially retention periods, the limit-of-liability wording and
   anything about refunds of school subscription charges.
7. **Check `APP_DATABASE_URL` is set in production.** The Privacy Policy says each school's data is kept separate.
   The database-level wall (Row-Level Security) only applies when the app connects as the restricted role.
8. **Bump the version** in both `backend/app/core/legal.py` (`TERMS_VERSION`) and `frontend/src/config/legal.ts`
   (`LEGAL_VERSION`, `LEGAL_UPDATED`) whenever the Terms or Privacy Policy change materially.

## Known limits (decide knowingly)

- **SMS opt-out.** Unsubscribe covers email only. Reminders by SMS continue; the Privacy Policy tells people to
  contact their school or you. Add a STOP keyword if you want parity.
- **Staff and teacher accounts** cannot self-delete (a school needs an administrator). They email you or ask their
  school admin.
- **Erasure keeps financial records** (payments, invoices, audit log) with the person's details removed, and a
  private chat that was reported for safeguarding. This is stated in the Privacy Policy.
- **Data export.** The Data Protection Act also gives a right to a copy of your data. There is no self-serve export
  yet; requests go to the contact email.
- **If you add analytics or ads later**, replace the notice with a real accept/decline banner that blocks the
  tracker until the person agrees, and update the Cookie Policy.

## Third-party inventory

| Service | Used for | When it is contacted | Data it can see |
|---------|----------|----------------------|-----------------|
| Supabase | Database and file storage | Always (backend) | All app data (it is the database) |
| Vercel | Hosts the web app | Always | Normal web-server logs (IP, browser) |
| Safaricom Daraja | M-Pesa payment prompts | When a parent pays | Amount, school paybill, payer phone |
| Africa's Talking | SMS | When SMS is configured | Phone number, message text |
| Brevo / Resend / SMTP | Email | When email is configured | Email address, subject, body |
| Google Sign-In | Optional sign-in | Only on the sign-in/up pages when `VITE_GOOGLE_CLIENT_ID` is set | Google's own cookies and data under Google's policy |
| Sentry | Error reports | Only if a DSN is configured | Error details (no personal data by default) |
| Google Gemini or Anthropic Claude | AI assistant | Only when someone uses the assistant | The question and the fee data needed to answer it |
| ~~Google Fonts~~ | removed | never | fonts are now bundled |

Keep the Privacy Policy section 4 in step with this table whenever a service is added or removed.

## Licences

- **Fonts:** Space Grotesk, IBM Plex Sans and IBM Plex Mono, bundled from the `@fontsource` packages under the SIL
  Open Font License 1.1 (free to embed and redistribute; the licence text ships inside each package).
- **Icons:** `lucide-react` (ISC). **Frontend dependencies:** a check of the production tree found MIT, ISC,
  BSD-3-Clause, Apache-2.0 and OFL-1.1. The only MPL-2.0 packages are `lightningcss` (a build tool, not shipped).
  No GPL or AGPL.
- **Images:** everything in `frontend/public` (favicon, app icons) should be your own artwork. If any came from a
  stock site or an AI generator, confirm its licence permits commercial use.
- **Backend:** run `pip-licenses` against `backend/requirements.txt` before launch and review any copyleft result.
