import { useEffect, useRef, useState, useCallback } from "react";

interface UsePollingOptions<T> {
  /** Async function that fetches data */
  fetchFn: () => Promise<T>;
  /** Polling interval in milliseconds */
  interval: number;
  /** Whether polling is enabled (default: true) */
  enabled?: boolean;
}

interface UsePollingReturn<T> {
  /** Most recent data from the fetch function */
  data: T | null;
  /** Whether a fetch is currently in progress */
  loading: boolean;
  /** Most recent error, if any */
  error: Error | null;
  /** Manually trigger a fetch */
  refresh: () => void;
}

/**
 * Custom hook for periodic data fetching at a configurable interval.
 * Accepts an interval parameter (ms) and a fetch function.
 */
export function usePolling<T>({
  fetchFn,
  interval,
  enabled = true,
}: UsePollingOptions<T>): UsePollingReturn<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fetchFnRef = useRef(fetchFn);

  // Keep fetchFn ref current without triggering re-renders
  useEffect(() => {
    fetchFnRef.current = fetchFn;
  }, [fetchFn]);

  const executeFetch = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchFnRef.current();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(() => {
    executeFetch();
  }, [executeFetch]);

  useEffect(() => {
    if (!enabled) {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }

    // Fetch immediately on mount/enable
    executeFetch();

    // Set up polling interval
    timerRef.current = setInterval(executeFetch, interval);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [interval, enabled, executeFetch]);

  return { data, loading, error, refresh };
}
