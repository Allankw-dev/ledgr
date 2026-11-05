import { Link } from 'react-router-dom';
import { LegalLayout, H2, P, UL } from '../../components/legal/LegalLayout';
import { OperatorDetails } from '../../components/legal/OperatorDetails';

export function TermsPage() {
  return (
    <LegalLayout
      title="Terms of Service"
      intro="These terms apply when you use Ledgr, the school fee management service. By creating an account or using Ledgr you agree to them and to the Privacy Policy."
    >
      <H2>1. Who may use Ledgr</H2>
      <UL>
        <li><strong>Parents and guardians</strong> must be 18 or older and the parent or legal guardian of the child they link to their account.</li>
        <li><strong>School staff and teachers</strong> use accounts created for them by their school. If you leave the school, your access should be removed.</li>
        <li>Children may not create accounts.</li>
      </UL>

      <H2>2. Your account</H2>
      <UL>
        <li>Give accurate details and keep them up to date. Keep your password private and tell us if you think someone else has used your account.</li>
        <li>You are responsible for what happens under your account.</li>
        <li>Linking to a child is checked by the school. We may remove a link the school does not confirm.</li>
      </UL>

      <H2>3. What Ledgr is, and is not</H2>
      <P>
        Ledgr is a record-keeping and payment-prompt tool for school fees. Invoices, fee structures and balances are set and owned by your school. Ledgr shows what the school has recorded; if you think a balance is wrong, raise it with the school office. Ledgr is not a bank, and is not itself a payment service provider.
      </P>

      <H2>4. Paying fees through M-Pesa</H2>
      <UL>
        <li>When you choose to pay, Ledgr asks Safaricom to send a payment prompt to your phone. You approve it with your M-Pesa PIN. Ledgr never sees your PIN.</li>
        <li>The money goes to the school&apos;s own paybill, not to Ledgr. <strong>Ledgr adds no fee to your payment.</strong> Safaricom&apos;s own terms and any charges it applies are between you and Safaricom.</li>
        <li>A payment counts once Safaricom confirms it. If your balance does not update, keep your M-Pesa confirmation message and show it to the school bursar, who can match it. An amount above what is owed is kept as credit on the child&apos;s account.</li>
        <li>See the <Link className="underline" to="/refunds">Refund Policy</Link> for mistakes and refunds.</li>
      </UL>

      <H2>5. Acceptable use</H2>
      <P>Do not:</P>
      <UL>
        <li>use another person&apos;s account, or try to see a child&apos;s records you are not linked to;</li>
        <li>attack, probe or overload the service, or try to get around its security;</li>
        <li>send unlawful, abusive, threatening or misleading messages, or upload malicious files;</li>
        <li>use Ledgr for anything other than managing and paying school fees and communicating with the school.</li>
      </UL>
      <P>We, or your school, may suspend an account that breaks these rules.</P>

      <H2>6. Messages and group chats</H2>
      <P>Class group chats are shared with the parents, teachers and staff of that class. Be respectful and do not share other people&apos;s personal information. Any chat participant can report a private chat; the school administrator can then review the reported messages. The school may remove content that breaks these terms.</P>

      <H2>7. The AI assistant</H2>
      <P>If enabled, the assistant answers questions using your school&apos;s records. It can make mistakes and is not financial or legal advice. Treat invoices and receipts, not the assistant&apos;s wording, as the official record.</P>

      <H2>8. For schools</H2>
      <UL>
        <li>The school is responsible for the accuracy of the student and fee records it enters, and for having a lawful basis to share children&apos;s details with Ledgr and with parents.</li>
        <li>The school is the data controller and the operator its processor (see the Privacy Policy). Schools should register with the Office of the Data Protection Commissioner where the law requires it.</li>
        <li>Plans, limits and charges for schools are as agreed between the school and the operator.</li>
      </UL>

      <H2>9. Availability</H2>
      <P>We work to keep Ledgr running but do not promise it will be uninterrupted or error-free. Planned maintenance and events outside our control (for example a Safaricom or internet outage) can interrupt the service. If an outage interrupts a payment, a prompt may need to be repeated.</P>

      <H2>10. Responsibility</H2>
      <P>
        To the extent the law allows, the operator is not liable for indirect or consequential loss, or for losses caused by incorrect records entered by a school, by a payment network, or by something outside our reasonable control. Nothing in these terms limits responsibility that cannot be limited by law, including for fraud or for death or personal injury caused by negligence, or your rights under Kenyan consumer and data protection law.
      </P>

      <H2>11. Ending your use</H2>
      <P>You can stop using Ledgr at any time. Parents can delete their account in Profile → Privacy &amp; data. We or the school may suspend or close an account that breaks these terms. Records the school must keep stay with the school.</P>

      <H2>12. Changes</H2>
      <P>We may update these terms. If a change matters, we will update the date and tell you in the app or by email. Continuing to use Ledgr after that means you accept the new terms.</P>

      <H2>13. Law and disputes</H2>
      <P>These terms are governed by the laws of Kenya. Please contact us first so we can try to sort out any problem; failing that, the courts of Kenya have jurisdiction.</P>

      <H2>14. Contact</H2>
      <OperatorDetails />
    </LegalLayout>
  );
}
