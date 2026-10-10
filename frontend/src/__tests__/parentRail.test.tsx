import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ParentRail } from '../components/dx/RightRail';
import { MessagePanel } from '../components/MessagePanel';

vi.mock('../api/messages', () => ({
  getMyMessages: vi.fn().mockResolvedValue([]),
  sendMyMessage: vi.fn(),
  pingMyTyping: vi.fn(),
  getStaffTypingStatus: vi.fn().mockResolvedValue({ typing: false }),
}));

function Where() {
  const l = useLocation();
  return <p data-testid="where">{l.pathname + l.hash}</p>;
}

describe('ParentRail "Get in touch"', () => {
  it.each([
    ['School office', '/parent/dashboard#messages'],
    ['Teacher chats', '/parent/chats'],
    ['Class group', '/parent/class-group'],
    ['Ask Ledgr', '/parent/assistant'],
  ])('%s goes there on the first tap', (name, target) => {
    render(
      <MemoryRouter initialEntries={['/parent/dashboard']}>
        <ParentRail />
        <Where />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByText(name).closest('a')!);
    expect(screen.getByTestId('where').textContent).toBe(target);
  });
});

describe('MessagePanel deep link', () => {
  beforeEach(() => {
    // The test DOM defines its own scrollIntoView on HTMLElement, so that is where the stub has to go.
    HTMLElement.prototype.scrollIntoView = vi.fn();
    Element.prototype.scrollTo = vi.fn(); // jsdom has no scrollTo; the panel scrolls its message list to the bottom
  });

  it('opens itself and scrolls into view for /parent/dashboard#messages', async () => {
    render(
      <MemoryRouter initialEntries={['/parent/dashboard#messages']}>
        <Routes>
          <Route path="/parent/dashboard" element={<MessagePanel />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByPlaceholderText(/type a message/i)).toBeTruthy());
    await waitFor(() => expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled());
  });

  it('stays closed without the link', () => {
    render(
      <MemoryRouter initialEntries={['/parent/dashboard']}>
        <MessagePanel />
      </MemoryRouter>
    );
    expect(screen.queryByPlaceholderText(/type a message/i)).toBeNull();
  });
});
