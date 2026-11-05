import { OPERATOR } from '../../config/legal';
import { ToAdd } from './LegalLayout';

/** The business details block used on the legal pages. */
export function OperatorDetails() {
  return (
    <ul className="text-sm text-ink-700 leading-relaxed mb-3 flex flex-col gap-1">
      <li>Service operated by: {OPERATOR.name || <ToAdd what="registered business name" />}</li>
      {OPERATOR.registration && <li>Registration number: {OPERATOR.registration}</li>}
      <li>Address: {OPERATOR.address || <ToAdd what="postal or physical address" />}</li>
      <li>
        Email:{' '}
        {OPERATOR.email ? <a className="underline" href={`mailto:${OPERATOR.email}`}>{OPERATOR.email}</a> : <ToAdd what="contact email for privacy and legal requests" />}
      </li>
      {OPERATOR.phone && <li>Phone: {OPERATOR.phone}</li>}
      {OPERATOR.odpcRegistration && <li>Data Protection Commissioner registration no.: {OPERATOR.odpcRegistration}</li>}
    </ul>
  );
}
