import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { usePolling } from "@/hooks/usePolling";
import { useViewState } from "@/hooks/useViewState";
import { useClock } from "@/hooks/useClock";
import { useApiClient } from "@/hooks/useApiClient";

describe("useClock", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns time in HH:MM:SS format", () => {
    vi.setSystemTime(new Date(2024, 0, 1, 14, 30, 45));
    const { result } = renderHook(() => useClock());
    // Initial render is empty; useEffect sets the time on mount
    act(() => {
      vi.advanceTimersByTime(0);
    });
    expect(result.current).toBe("14:30:45");
  });

  it("updates every second", () => {
    vi.setSystemTime(new Date(2024, 0, 1, 10, 0, 0));
    const { result } = renderHook(() => useClock());
    // Flush mount effect
    act(() => {
      vi.advanceTimersByTime(0);
    });
    expect(result.current).toBe("10:00:00");

    // advanceTimersByTime also advances the fake system clock
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current).toBe("10:00:01");

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current).toBe("10:00:02");
  });

  it("pads single-digit values with leading zeros", () => {
    vi.setSystemTime(new Date(2024, 0, 1, 1, 2, 3));
    const { result } = renderHook(() => useClock());
    act(() => {
      vi.advanceTimersByTime(0);
    });
    expect(result.current).toBe("01:02:03");
  });

  it("cleans up interval on unmount", () => {
    const clearSpy = vi.spyOn(global, "clearInterval");
    const { unmount } = renderHook(() => useClock());
    unmount();
    expect(clearSpy).toHaveBeenCalled();
    clearSpy.mockRestore();
  });
});

describe("useViewState", () => {
  it("defaults to 'dashboard'", () => {
    const { result } = renderHook(() => useViewState());
    expect(result.current.activeView).toBe("dashboard");
  });

  it("updates active view when setActiveView is called", () => {
    const { result } = renderHook(() => useViewState());
    act(() => {
      result.current.setActiveView("live");
    });
    expect(result.current.activeView).toBe("live");
  });

  it("allows switching to all valid view keys", () => {
    const { result } = renderHook(() => useViewState());
    const viewKeys = [
      "dashboard",
      "live",
      "events",
      "review",
      "analytics",
      "aws",
      "status",
      "settings",
    ] as const;

    for (const key of viewKeys) {
      act(() => {
        result.current.setActiveView(key);
      });
      expect(result.current.activeView).toBe(key);
    }
  });
});

describe("usePolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fetches immediately on mount when enabled", async () => {
    const fetcher = vi.fn().mockResolvedValue("data");
    renderHook(() => usePolling(fetcher, 5000));

    // Flush microtasks for the initial async fetch
    await act(async () => {
      await Promise.resolve();
    });

    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("polls at the specified interval", async () => {
    const fetcher = vi.fn().mockResolvedValue("data");
    renderHook(() => usePolling(fetcher, 5000));

    // Flush initial fetch
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(fetcher).toHaveBeenCalledTimes(1);

    // Advance by interval
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("returns fetched data", async () => {
    const fetcher = vi.fn().mockResolvedValue({ value: 42 });
    const { result } = renderHook(() => usePolling(fetcher, 5000));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.data).toEqual({ value: 42 });
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("does not fetch when enabled is false", async () => {
    const fetcher = vi.fn().mockResolvedValue("data");
    renderHook(() => usePolling(fetcher, 5000, { enabled: false }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });

    expect(fetcher).not.toHaveBeenCalled();
  });

  it("stops polling when enabled changes to false", async () => {
    const fetcher = vi.fn().mockResolvedValue("data");
    const { rerender } = renderHook(
      ({ enabled }) => usePolling(fetcher, 5000, { enabled }),
      { initialProps: { enabled: true } }
    );

    // Flush initial fetch
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(fetcher).toHaveBeenCalledTimes(1);

    rerender({ enabled: false });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });

    // Should not have been called again after disabling
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("restarts polling when enabled changes back to true", async () => {
    const fetcher = vi.fn().mockResolvedValue("data");
    const { rerender } = renderHook(
      ({ enabled }) => usePolling(fetcher, 5000, { enabled }),
      { initialProps: { enabled: false } }
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(fetcher).not.toHaveBeenCalled();

    rerender({ enabled: true });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("retains last successful data on error", async () => {
    let callCount = 0;
    const fetcher = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount === 1) return Promise.resolve("good data");
      return Promise.reject(new Error("Network error"));
    });

    const { result } = renderHook(() => usePolling(fetcher, 5000));

    // Flush initial (successful) fetch
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.data).toBe("good data");

    // Advance to trigger second (failing) fetch
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(result.current.error).not.toBeNull();
    // Data should still be the last successful value
    expect(result.current.data).toBe("good data");
  });

  it("calls onError callback when fetch fails", async () => {
    const onError = vi.fn();
    const fetcher = vi.fn().mockRejectedValue(new Error("Fail"));

    renderHook(() => usePolling(fetcher, 5000, { onError }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(onError).toHaveBeenCalledWith(expect.any(Error));
    expect(onError.mock.calls[0]![0].message).toBe("Fail");
  });

  it("refresh triggers an immediate re-fetch", async () => {
    const fetcher = vi.fn().mockResolvedValue("data");
    const { result } = renderHook(() => usePolling(fetcher, 5000));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(fetcher).toHaveBeenCalledTimes(1);

    await act(async () => {
      result.current.refresh();
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("cleans up interval on unmount", async () => {
    const fetcher = vi.fn().mockResolvedValue("data");
    const { unmount } = renderHook(() => usePolling(fetcher, 5000));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(fetcher).toHaveBeenCalledTimes(1);

    unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });

    // No additional calls after unmount
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});

describe("useApiClient", () => {
  it("returns the ApiClient instance with expected methods", () => {
    const { result } = renderHook(() => useApiClient());
    expect(result.current).toBeDefined();
    expect(typeof result.current.getHealth).toBe("function");
    expect(typeof result.current.getIncidents).toBe("function");
    expect(typeof result.current.getStreamStatus).toBe("function");
  });

  it("returns the same instance on re-render", () => {
    const { result, rerender } = renderHook(() => useApiClient());
    const first = result.current;
    rerender();
    expect(result.current).toBe(first);
  });
});
