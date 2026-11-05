import { Link } from 'react-router-dom';
import { LegalLayout, H2, P, UL } from '../../components/legal/LegalLayout';
import { OperatorDetails } from '../../components/legal/OperatorDetails';

export function PrivacyPage() {
  return (
    <LegalLayout
      title="Privacy Policy"
      intro="Ledgr helps schools in Kenya keep fee records and helps parents see and pay what they owe. This page explains what personal data Ledgr holds, why, who sees it, and what you can do about it. It follows Kenya's Data Protection Act, 2019."
    >
      <H2>1. Who is responsible for your data</H2>
      <P>
        Two parties are involved, and they have different roles. Your child&apos;s school decides what fee and student records are kept and why: the school is the <strong>data controller</strong> for student and fee records. The operator of this Ledgr service provides the software and handles that data on the school&apos;s instructions (a <strong>data processor</strong>). The operator is the controller for the sign-in accounts, security logs and this website.
      </P>
      <OperatorDetails />

      <H2>2. What data we hold</H2>
      <UL>
        <li><strong>Parents and guardians:</strong> full name, email address, phone number, and a one-way scrambled form of your password (we cannot read your password). If you sign in with Google, we receive your name and verified email from Google. If you turn on fingerprint or passkey sign-in, we store only the public key; your fingerprint never leaves your device.</li>
        <li><strong>Children (supplied by the school, not collected from the child):</strong> name, admission number, class, and optionally date of birth, plus the fee invoices, payments and balances for that child.</li>
        <li><strong>Payments:</strong> amount, date, method, the M-Pesa receipt number, and the phone number M-Pesa reports as having paid.</li>
        <li><strong>Teachers and school staff:</strong> name, email or phone, role, and an activity log of important actions (such as recording a payment) kept for accountability.</li>
        <li><strong>Messages:</strong> messages between a parent and the school, class group chat posts, private chats between a teacher and a parent, and any photos or files you attach.</li>
        <li><strong>Technical data:</strong> IP address, browser and device type, and sign-in times, kept in server logs and used to stop abuse and keep accounts safe. If error reporting is switched on, a report of what went wrong (without your personal details) is sent to our error-monitoring provider.</li>
      </UL>
      <P>We ask for the minimum needed. A child&apos;s date of birth is optional. We do not collect national ID numbers, bank card numbers, health data or religion.</P>

      <H2>3. Why we use it, and our legal basis</H2>
      <UL>
        <li>To run your school&apos;s fee accounts: send invoices, record and match payments, show balances and issue receipts. <em>Basis: performing the service the school and you rely on.</em></li>
        <li>To keep records the school must keep for accounting and audit. <em>Basis: legal obligation.</em></li>
        <li>To keep accounts secure and prevent fraud and abuse. <em>Basis: legitimate interest.</em></li>
        <li>To send fee reminders, overdue notices and school announcements. <em>Basis: the school&apos;s legitimate interest in collecting fees. You can switch these emails off at any time (see section 9).</em></li>
        <li>For optional features you turn on yourself, such as Google sign-in or fingerprint sign-in. <em>Basis: your consent, which you can withdraw by turning the feature off.</em></li>
      </UL>
      <P>We do not sell your data, we do not show advertising, and we do not use your data for marketing unrelated to your child&apos;s school.</P>

      <H2>4. Who can see it</H2>
      <UL>
        <li><strong>Your school:</strong> administrators and bursars see student and fee records. Class teachers see only what their role allows. A parent sees only their own approved children.</li>
        <li><strong>Other parents:</strong> only your name and messages in a class group chat you share. Never fee details.</li>
        <li><strong>Service providers</strong> that run Ledgr for us. Depending on how your school&apos;s Ledgr is set up these may include: a database and file-storage host (Supabase), a web host (Vercel and an API host), Safaricom (M-Pesa payments), an SMS provider (Africa&apos;s Talking), an email provider (Brevo, Resend or the school&apos;s own mail server), Google (only if you use Google sign-in), and an error-monitoring service (Sentry). Each receives only what it needs for its job.</li>
        <li><strong>Authorities</strong> when the law requires it.</li>
      </UL>

      <H2>5. The AI assistant</H2>
      <P>
        If your school has switched on the assistant, the question you type and the fee information needed to answer it are sent to an AI provider (Google Gemini or Anthropic Claude, depending on the setup). A parent&apos;s assistant can only look at that parent&apos;s own approved children. Please do not type anything sensitive that you would not want processed this way. The assistant can be wrong: check amounts in your invoices and receipts before you act on them.
      </P>

      <H2>6. Where data is processed</H2>
      <P>Some providers process data outside Kenya. Where that happens we rely on the safeguards the Data Protection Act requires, such as contracts that oblige the provider to protect the data.</P>

      <H2>7. How long we keep it</H2>
      <UL>
        <li>Financial records (invoices, payments, receipts, audit entries) are kept for as long as the school needs them for its accounting and audit duties, and are then deleted or anonymised.</li>
        <li>Sign-in sessions expire automatically.</li>
        <li>If you delete your account, your personal details are removed straight away (see section 9). The payments linked to it stay, with your name and contact details removed.</li>
      </UL>

      <H2>8. How we protect it</H2>
      <UL>
        <li>All traffic is encrypted in transit (HTTPS). Passwords are stored only as one-way hashes. Staff accounts can use two-factor authentication.</li>
        <li>Each school&apos;s data is separated from every other school&apos;s, both in the application and in the database.</li>
        <li>Private teacher-to-parent chats and the schools&apos; M-Pesa credentials are stored encrypted. Class group chats and parent-to-school messages are protected by access controls but are not individually encrypted.</li>
        <li>Sessions end after a period of inactivity. Important actions are recorded in an audit log designed to be append-only.</li>
      </UL>
      <P>No system is perfectly secure. If a breach affects you, we will tell you and the Data Protection Commissioner as the law requires.</P>

      <H2>9. Children&apos;s data, and your rights</H2>
      <P>
        Ledgr holds children&apos;s information only because their school supplies it to manage school fees, and only a verified parent or guardian can see it. When you sign up you confirm that you are 18 or older and the child&apos;s parent or legal guardian. We do not allow children to create accounts, and we do not use a child&apos;s data for advertising or profiling.
      </P>
      <P>Under the Data Protection Act you can:</P>
      <UL>
        <li><strong>See and correct</strong> the data held about you. Your name, email and phone can be changed in <Link className="underline" to="/parent/profile">Profile</Link>; for anything else, ask us or your school.</li>
        <li><strong>Delete your account.</strong> Parents can do this themselves in Profile → Privacy &amp; data. It removes your name, email, phone, password, links to your children, messages and chat posts, and signs you out everywhere. Records the school must keep (payments and the audit log) remain but no longer identify you, and a private chat that was reported for safeguarding may be kept. Your child&apos;s school record belongs to the school; to change or erase it, ask the school office.</li>
        <li><strong>Stop optional email.</strong> Every fee reminder and announcement email has an unsubscribe link, and you can switch it off in Profile → Privacy &amp; data. Payment receipts and security emails are always sent because they are part of the service.</li>
        <li><strong>Object, restrict or withdraw consent</strong>, or ask for a copy of your data, by emailing us (details above).</li>
        <li><strong>Complain</strong> to the Office of the Data Protection Commissioner (odpc.go.ke) if you think your data has been mishandled. We would like the chance to fix it first.</li>
      </UL>

      <H2>10. Cookies and similar storage</H2>
      <P>Ledgr does not set cookies and has no advertising or analytics trackers. See the <Link className="underline" to="/cookies">Cookie Policy</Link>.</P>

      <H2>11. Changes to this policy</H2>
      <P>If we change this policy in a way that matters, we will update the date above and, for significant changes, tell you in the app or by email.</P>
    </LegalLayout>
  );
}
