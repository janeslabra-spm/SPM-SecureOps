"use client";

import { useState, useEffect, useRef, useCallback } from "react";

interface UsePollingOptions {
  enabled?: boolean;
  onError?: (err: Error) => void;
}

interface UsePollingResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refresh: () => void;
}

/**
 * Generic interval polling hook with cleanup.
 *
 * Fetches immediately on mount (when enabled), then polls at `intervalMs`.
 * Retains last successful data on error. Cleans up interval on unmount or
 * when `enabled` becomes false.
 */
export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  options?: UsePollingOptions
): UsePollingResult<T> {
  const { enabled = true, onError } = options ?? {};

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const fetcherRef = useRef(fetcher);
  const onErrorRef = useRef(onError);
  const intervalIdRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Keep refs in sync without triggering re-renders
  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const executeFetch = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
    } catch (err) {
      const fetchError =
        err instanceof Error ? err : new Error(String(err));
      setError(fetchError);
      onErrorRef.current?.(fetchError);
      // Retain last successful data — don't clear `data`
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      // Clear interval when disabled
      if (intervalIdRef.current !== null) {
        clearInterval(intervalIdRef.current);
        intervalIdRef.current = null;
      }
      return;
    }

    // Fetch immediately on mount / when enabled
    void executeFetch();

    // Set up polling interval
    intervalIdRef.current = setInterval(() => {
      void executeFetch();
    }, intervalMs);

    return () => {
      if (intervalIdRef.current !== null) {
        clearInterval(intervalIdRef.current);
        intervalIdRef.current = null;
      }
    };
  }, [enabled, intervalMs, executeFetch]);

  const refresh = useCallback(() => {
    void executeFetch();
  }, [executeFetch]);

  return { data, loading, error, refresh };
}
