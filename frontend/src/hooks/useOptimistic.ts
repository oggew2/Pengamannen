import { useState, useCallback } from 'react';

/**
 * Hook for optimistic UI updates.
 * Shows optimistic state immediately, then syncs with server.
 */
export function useOptimistic<T>(
  initialValue: T,
  onUpdate: (value: T) => Promise<T>
) {
  const [value, setValue] = useState(initialValue);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const update = useCallback(async (optimisticValue: T) => {
    const previousValue = value;
    setValue(optimisticValue); // Optimistic update
    setIsPending(true);
    setError(null);

    try {
      const serverValue = await onUpdate(optimisticValue);
      setValue(serverValue); // Sync with server response
    } catch (e) {
      setValue(previousValue); // Rollback on error
      setError(e instanceof Error ? e : new Error('Update failed'));
    } finally {
      setIsPending(false);
    }
  }, [value, onUpdate]);

  return { value, update, isPending, error, setValue };
}
