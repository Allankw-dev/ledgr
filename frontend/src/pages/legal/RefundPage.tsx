import { LegalLayout, H2, P, UL } from '../../components/legal/LegalLayout';
import { OperatorDetails } from '../../components/legal/OperatorDetails';

export function RefundPage() {
  return (
    <LegalLayout
      title="Refund Policy"
      intro="Ledgr does not charge parents anything to view invoices or to pay school fees. This page explains what happens when money is paid by mistake or a refund is needed."
    >
      <H2>1. School fees belong to the school</H2>
      <P>
        When you pay through Ledgr the money goes straight to your school&apos;s M-Pesa paybill. Whether any part of it can be refunded is decided by the school under its own fee policy, not by Ledgr. Please ask the school bursar. If the school agrees to a refund, it records it in Ledgr as a separate reversal entry; the original payment is never edited or erased, so the history stays accurate.
      </P>

      <H2>2. Paid too much</H2>
      <P>If you pay more than is owed, the extra is kept as credit on your child&apos;s account. Ask the school bursar how it will be used, or whether you would rather have it returned.</P>

      <H2>3. Money left your phone but Ledgr shows nothing</H2>
      <UL>
        <li>Wait a few minutes: M-Pesa confirmations can be slow.</li>
        <li>If your balance still has not updated, keep the M-Pesa confirmation SMS and show it to the school bursar. They can match the payment to your child&apos;s account.</li>
        <li>A payment that does not match any invoice, or whose amount differs from the request, is held for the bursar to review. It is not lost.</li>
      </UL>

      <H2>4. Paid the wrong paybill, number or amount outside Ledgr</H2>
      <P>Ledgr cannot reverse M-Pesa transactions. Contact Safaricom promptly about reversing a transaction sent to the wrong number or paybill, and tell the school office so records stay straight.</P>

      <H2>5. Schools and subscriptions</H2>
      <P>Charges to schools for using Ledgr, and any refund of them, follow the agreement between the school and the operator. If you are a school and believe you were charged in error, contact us below.</P>

      <H2>6. Contact</H2>
      <OperatorDetails />
    </LegalLayout>
  );
}
