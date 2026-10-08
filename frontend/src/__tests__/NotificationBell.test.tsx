import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NotificationBell } from '../components/NotificationBell';
import { useAuthStore } from '../store/authStore';

const navigate = vi.fn();
vi.mock('react-router-dom', async () => ({
  ...(await vi.importActual<typeof import('react-router-dom')>('react-router-dom')),
  useNavigate: () => navigate,
}));

function setRole(role: string) {
  useAuthStore.setState({ user: { id: 'u1', email: 'a@b.c', full_name: 'Test', role } as never });
}

function renderBell(props: Partial<React.ComponentProps<typeof NotificationBell>> = {}) {
  render(
    <MemoryRouter>
      <NotificationBell
        total={0}
        unreadMentions={0}
        mentions={[]}
        mentionsLoaded
        onOpen={() => {}}
        onMarkSeen={async () => {}}
        {...props}
      />
    </MemoryRouter>
  );
  fireEvent.click(screen.getByRole('button', { name: /notifications?/i }));
}

describe('NotificationBell', () => {
  beforeEach(() => navigate.mockClear());

  it('lists every kind of unread item for a parent, each linking to where it lives', () => {
    setRole('PARENT');
    renderBell({ total: 6, counts: { messages: 1, classGroups: 2, direct: 3 } });
    fireEvent.click(screen.getByText('School messages'));
    expect(navigate).toHaveBeenLastCalledWith('/parent/dashboard');
    fireEvent.click(screen.getByRole('button', { name: /notifications?/i }));
    fireEvent.click(screen.getByText('Class group chats'));
    expect(navigate).toHaveBeenLastCalledWith('/parent/class-group');
    fireEvent.click(screen.getByRole('button', { name: /notifications?/i }));
    fireEvent.click(screen.getByText('Teacher chats'));
    expect(navigate).toHaveBeenLastCalledWith('/parent/chats');
  });

  it('hides kinds with nothing waiting and says all caught up when empty', () => {
    setRole('PARENT');
    renderBell({ counts: { messages: 0, classGroups: 0, direct: 0 } });
    expect(screen.queryByText('School messages')).toBeNull();
    expect(screen.getByText("You're all caught up.")).toBeTruthy();
  });

  it('shows chat reports only to the school admin', () => {
    setRole('BURSAR');
    renderBell({ counts: { messages: 0, classGroups: 0, direct: 0, chatReports: 2 } });
    expect(screen.queryByText('Chat reports to review')).toBeNull();
  });

  it('shows chat reports to the school admin and links to them', () => {
    setRole('SCHOOL_ADMIN');
    renderBell({ counts: { messages: 0, classGroups: 0, direct: 0, chatReports: 2 } });
    fireEvent.click(screen.getByText('Chat reports to review'));
    expect(navigate).toHaveBeenLastCalledWith('/chat-reports');
  });
});
