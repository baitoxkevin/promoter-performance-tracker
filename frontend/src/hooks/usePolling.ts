/**
 * Custom hook for polling data at a regular interval.
 * Used by the leaderboard to auto-refresh every N seconds.
 *
 * Features:
 *  - Auto-fetches on mount and at the specified interval.
 *  - Pauses polling when the browser tab is hidden (saves resources).
 *  - Provides loading and error states.
 *  - Returns a manual refresh function.
 */

import { useState, useEffect, useCallback, useRef } from "react";

interface UsePollingResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function usePolling<T>(
  fetchFn: () => Promise<T>,
  intervalMs: number = 5000
): UsePollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fetchRef = useRef(fetchFn);

  // Keep the fetch function ref current
  fetchRef.current = fetchFn;

  const doFetch = useCallback(async () => {
    try {
      const result = await fetchRef.current();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial fetch
    doFetch();

    // Set up polling interval
    const interval = setInterval(() => {
      // Only poll when the tab is visible
      if (!document.hidden) {
        doFetch();
      }
    }, intervalMs);

    // Pause/resume on visibility change
    const handleVisibility = () => {
      if (!document.hidden) {
        doFetch(); // Refresh immediately when tab becomes visible
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [doFetch, intervalMs]);

  return { data, loading, error, refresh: doFetch };
}
