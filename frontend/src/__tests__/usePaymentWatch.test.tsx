import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { usePaymentWatch } from '../hooks/usePaymentWatch';
import { makeChild } from '../test/fixtures';

const paid = (id: string, name: string, amount: number) => makeChild(id, name, [{ paid: amount }]);

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('usePaymentWatch', () => {
  it('detects the payment and reports which child it was for (several children)', async () => {
    const before = [paid('a', 'Alex Karimi', 0), paid('b', 'Brian Karimi', 100)];
    const refetch = vi.fn().mockResolvedValue([paid('a', 'Alex Karimi', 4000), paid('b', 'Brian Karimi', 100)]);
    const { result } = renderHook(() => usePaymentWatch(before, refetch));

    act(() => result.current.watch('Alex Karimi'));
    expect(result.current.polling).toBe(true);
    expect(result.current.watchingFor).toBe('Alex Karimi');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3100);
    });
    expect(result.current.received).toBe(4000);
    expect(result.current.receivedFor).toEqual(['Alex Karimi']);
    expect(result.current.polling).toBe(false);
  });

  it('keeps names out of it for a single child', async () => {
    const refetch = vi.fn().mockResolvedValue([paid('a', 'Alex Karimi', 500)]);
    const { result } = renderHook(() => usePaymentWatch([paid('a', 'Alex Karimi', 0)], refetch));
    act(() => result.current.watch('Alex Karimi'));
    expect(result.current.watchingFor).toBeNull();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3100);
    });
    expect(result.current.received).toBe(500);
    expect(result.current.receivedFor).toEqual([]);
  });

  it('gives up quietly if nothing arrives', async () => {
    const same = [paid('a', 'Alex', 0)];
    const refetch = vi.fn().mockResolvedValue(same);
    const { result } = renderHook(() => usePaymentWatch(same, refetch));
    act(() => result.current.watch());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10 * 60 * 1000);
    });
    expect(result.current.polling).toBe(false);
    expect(result.current.received).toBeNull();
  });
});
