import { describe, expect, it } from 'vitest';
import { buildAdminNotices, buildParentNotices } from '../components/dx/railData';

const NOW = new Date('2026-10-10T12:00:00Z').getTime();
const mention = (id: string, seen = false) => ({ id, seen, sender_name: 'Jane', class_name: 'Grade 5', class_id: 'c1', created_at: '2026-10-10T11:00:00Z' });
const none = { unreadMessages: 0, unreadClassGroups: 0, mentions: [] };

describe('buildAdminNotices', () => {
  it('is empty when nothing needs attention, so the rail can say so honestly', () => {
    expect(buildAdminNotices({ ...none, flagged: 0, overdue: 0 }, NOW)).toEqual([]);
  });

  it('lists each kind only when it is above zero, with links where there is somewhere to go', () => {
    const notices = buildAdminNotices({ unreadMessages: 2, unreadClassGroups: 0, mentions: [], flagged: 1, overdue: 23 }, NOW);
    expect(notices.map((n) => n.key)).toEqual(['messages', 'flagged', 'overdue']);
    expect(notices[0].title).toBe('2 new messages from parents');
    expect(notices[0].to).toBe('/messages');
    expect(notices[1].to).toBeUndefined();
    expect(notices[2].title).toBe('23 invoices overdue');
  });

  it('shows only unseen mentions, newest two, linking into the class chat', () => {
    const notices = buildAdminNotices({ ...none, mentions: [mention('a'), mention('b', true), mention('c'), mention('d')], flagged: 0, overdue: 0 }, NOW);
    expect(notices.map((n) => n.key)).toEqual(['mention-a', 'mention-c']);
    expect(notices[0].title).toBe('Jane mentioned you in Grade 5');
    expect(notices[0].hint).toBe('1h ago');
    expect(notices[0].to).toBe('/class-groups?class=c1');
  });

  it('never lists more than five', () => {
    const notices = buildAdminNotices({ unreadMessages: 1, unreadClassGroups: 1, mentions: [mention('a'), mention('b')], flagged: 1, overdue: 1 }, NOW);
    expect(notices).toHaveLength(5);
  });
});

describe('buildParentNotices', () => {
  it('points a parent at their own pages', () => {
    const notices = buildParentNotices({ ...none, unreadMessages: 1, unreadClassGroups: 3, unreadDirect: 1, mentions: [mention('a')] }, NOW);
    expect(notices.map((n) => n.to)).toEqual([
      '/parent/class-group?class=c1',
      '/parent/dashboard#messages',
      '/parent/class-group',
      '/parent/chats',
    ]);
    expect(notices[1].title).toBe('1 new message from the school office');
  });
});
