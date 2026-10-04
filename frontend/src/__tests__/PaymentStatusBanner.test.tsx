import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PaymentStatusBanner } from '../components/PaymentStatusBanner';

describe('PaymentStatusBanner', () => {
  it('says whose payment it is waiting for when the parent has several children', () => {
    render(<PaymentStatusBanner polling received={null} watchingFor="Alex Karimi" />);
    expect(document.body.textContent).toContain('confirm the payment for Alex Karimi');
  });

  it('names the child whose balance moved, and uses plain wording for one child', () => {
    const { rerender } = render(<PaymentStatusBanner polling={false} received={4000} receivedFor={['Alex Karimi']} />);
    expect(document.body.textContent).toContain('KES 4,000 received for Alex Karimi');
    expect(document.body.textContent).toContain('their balance has been updated');
    rerender(<PaymentStatusBanner polling={false} received={4000} />);
    expect(document.body.textContent).toContain('your balance has been updated');
  });

  it('joins several names naturally', () => {
    render(<PaymentStatusBanner polling={false} received={900} receivedFor={['Alex', 'Brian', 'Cara']} />);
    expect(document.body.textContent).toContain('Alex, Brian and Cara');
  });

  it('renders nothing when idle', () => {
    const { container } = render(<PaymentStatusBanner polling={false} received={null} />);
    expect(container.textContent).toBe('');
  });
});
