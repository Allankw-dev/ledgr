import { Link } from 'react-router-dom';
import { LegalLayout, H2, P, UL } from '../../components/legal/LegalLayout';

export function CookiePage() {
  return (
    <LegalLayout
      title="Cookie Policy"
      intro="Short version: Ledgr does not set cookies and has no advertising or analytics trackers. It does keep a few things on your device so the app works."
    >
      <H2>1. What Ledgr keeps on your device</H2>
      <P>These are stored in your browser&apos;s local storage (similar to cookies, but not sent to the server with every request). All are strictly necessary or purely a display preference, so we do not ask for consent to use them.</P>
      <UL>
        <li><strong>ledgr-auth</strong>: your sign-in session (access and refresh tokens and your basic account details), so you stay signed in. Removed when you sign out.</li>
        <li><strong>Sidebar setting</strong>: whether you collapsed the side menu.</li>
        <li><strong>Notice dismissed</strong>: remembers that you closed the storage notice, so we do not show it again.</li>
        <li><strong>App files cache</strong>: a copy of the app&apos;s own pages and images so repeat visits load faster. It never holds your fee, invoice or payment data.</li>
      </UL>

      <H2>2. Third parties</H2>
      <UL>
        <li><strong>Google sign-in:</strong> only on the sign-in and sign-up pages, and only if your school has switched it on, Google&apos;s sign-in script loads and Google may set its own cookies under <em>its</em> privacy policy. You can avoid this by signing in with email or phone.</li>
        <li><strong>Error reports:</strong> if switched on, a report goes to our error-monitoring provider when the app crashes. It does not include cookies or your personal details.</li>
        <li><strong>Fonts:</strong> the app&apos;s fonts are part of the app. Nothing is requested from Google Fonts.</li>
      </UL>
      <P>There is no advertising, no analytics, and no tracking across other websites.</P>

      <H2>3. Controlling it</H2>
      <P>Signing out removes your session. You can also clear site data for Ledgr in your browser settings at any time; you will just need to sign in again. More about how we handle your data is in the <Link className="underline" to="/privacy">Privacy Policy</Link>.</P>

      <H2>4. If this changes</H2>
      <P>If Ledgr ever adds analytics or other non-essential tracking, it will ask for your permission first and this page will be updated.</P>
    </LegalLayout>
  );
}
