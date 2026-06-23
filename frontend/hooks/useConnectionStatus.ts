"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { apiClient } from "@/lib/api-client";
import { POLLING_INTERVALS } from "@/lib/constants";

/**
 * Lightweight hook that polls GET /health every 30s to determine
 * whether the backend is reachable.
 *
 * Returns:
 * - `connected`: true if the last health check succeeded
 * - `retry`: manually trigger a health check
 */
export function useConnectionStatus() {
  const [connected, setConnected] = useState<boolean>(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const check = useCallback(async () => {
    try {
      await apiClient.getHealth();
      setConnected(true);
    } catch {
      setConnected(false);
    }
  }, []);

  useEffect(() => {
    // Initial check
    void check();

    // Poll at health interval (30s)
    intervalRef.current = setInterval(() => {
      void check();
    }, POLLING_INTERVALS.HEALTH);

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [check]);

  return { connected, retry: check };
}
