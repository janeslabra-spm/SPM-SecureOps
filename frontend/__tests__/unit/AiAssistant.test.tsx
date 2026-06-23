import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import { AiAssistant } from "@/components/widgets/AiAssistant";
import type { ComplianceEvent, AiSummaryResponse } from "@/lib/types";
import { AI_SUMMARY_MAX_LENGTH } from "@/lib/constants";

// Mock the API client
vi.mock("@/lib/api-client", () => ({
  apiClient: {
    getAiSummary: vi.fn(),
  },
}));

import { apiClient } from "@/lib/api-client";

const mockGetAiSummary = vi.mocked(apiClient.getAiSummary);

function makeEvent(id: number): ComplianceEvent {
  return {
    id,
    title: `Event ${id}`,
    detail: "test detail",
    eventType: "PHONE_ON_TABLE",
    timestamp: "2024-01-01T00:00:00Z",
    priority: "Needs Review",
    status: "Pending Review",
    confidence: 0.75,
    zone: "Main Camera",
    reviewer: "",
    notes: "",
    screenshotPath: "",
  };
}

const mockResponse: AiSummaryResponse = {
  summary: "Test AI summary response text.",
  riskLevel: "Medium",
  activeViolations: { PHONE_ON_TABLE: 2 },
  patterns: "Frequent phone usage detected in afternoon hours.",
};

describe("AiAssistant", () => {
  beforeEach(() => {
    mockGetAiSummary.mockReset();
  });

  it("renders header with AI Compliance Assistant title", () => {
    render(<AiAssistant events={[]} viewContext="dashboard" />);
    expect(screen.getByText("AI Compliance Assistant")).toBeInTheDocument();
  });

  it("shows empty state when no events provided", () => {
    render(<AiAssistant events={[]} viewContext="dashboard" />);
    expect(
      screen.getByText("No events available for AI analysis.")
    ).toBeInTheDocument();
  });

  it("shows loading skeleton when fetching summary", async () => {
    mockGetAiSummary.mockImplementation(
      () => new Promise(() => {}) // Never resolves — stays loading
    );

    render(<AiAssistant events={[makeEvent(1)]} viewContext="dashboard" />);

    await waitFor(() => {
      expect(screen.getByLabelText("Loading AI summary")).toBeInTheDocument();
    });
  });

  it("displays AI summary response after successful fetch", async () => {
    mockGetAiSummary.mockResolvedValue(mockResponse);

    render(<AiAssistant events={[makeEvent(1)]} viewContext="dashboard" />);

    await waitFor(() => {
      expect(screen.getByText("Test AI summary response text.")).toBeInTheDocument();
    });

    expect(screen.getByText("Medium Risk")).toBeInTheDocument();
    expect(
      screen.getByText("Frequent phone usage detected in afternoon hours.")
    ).toBeInTheDocument();
  });

  it("truncates responses exceeding 2000 characters with indicator", async () => {
    const longSummary = "A".repeat(2500);
    mockGetAiSummary.mockResolvedValue({
      ...mockResponse,
      summary: longSummary,
    });

    render(<AiAssistant events={[makeEvent(1)]} viewContext="dashboard" />);

    await waitFor(() => {
      // Should show truncated text (2000 chars + ellipsis "…")
      const summaryEl = screen.getByText((content) =>
        content.startsWith("A".repeat(50)) && content.endsWith("\u2026")
      );
      expect(summaryEl).toBeInTheDocument();
    });

    // Truncation indicator
    expect(screen.getByText(/Response truncated/)).toBeInTheDocument();
  });

  it("does NOT show truncation indicator for short responses", async () => {
    mockGetAiSummary.mockResolvedValue(mockResponse);

    render(<AiAssistant events={[makeEvent(1)]} viewContext="dashboard" />);

    await waitFor(() => {
      expect(screen.getByText("Test AI summary response text.")).toBeInTheDocument();
    });

    expect(screen.queryByText(/Response truncated/)).not.toBeInTheDocument();
  });

  it("shows error state with retry button on API failure", async () => {
    mockGetAiSummary.mockRejectedValue(new Error("Network error"));

    render(<AiAssistant events={[makeEvent(1)]} viewContext="dashboard" />);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("retries when retry button is clicked", async () => {
    mockGetAiSummary.mockRejectedValueOnce(new Error("Timeout"));

    render(<AiAssistant events={[makeEvent(1)]} viewContext="dashboard" />);

    await waitFor(() => {
      expect(screen.getByText("Timeout")).toBeInTheDocument();
    });

    // Set up the next response before clicking retry
    mockGetAiSummary.mockResolvedValueOnce(mockResponse);

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByText("Test AI summary response text.")).toBeInTheDocument();
    });

    expect(mockGetAiSummary).toHaveBeenCalledTimes(2);
  });

  it("has a scrollable container with max-height 400px", () => {
    render(<AiAssistant events={[]} viewContext="dashboard" />);

    const container = screen.getByText("AI Compliance Assistant").closest(".glass-card");
    expect(container).toHaveStyle({ maxHeight: "400px" });
  });

  it("calls API with correct payload shape", async () => {
    mockGetAiSummary.mockResolvedValue(mockResponse);
    const events = [makeEvent(1), makeEvent(2)];

    render(<AiAssistant events={events} viewContext="events" />);

    await waitFor(() => {
      expect(mockGetAiSummary).toHaveBeenCalledWith({
        events: [
          { id: 1, type: "PHONE_ON_TABLE", confidence: 0.75, timestamp: "2024-01-01T00:00:00Z" },
          { id: 2, type: "PHONE_ON_TABLE", confidence: 0.75, timestamp: "2024-01-01T00:00:00Z" },
        ],
        viewContext: "events",
      });
    });
  });

  it("displays correct risk badge for each risk level", async () => {
    mockGetAiSummary.mockResolvedValue({ ...mockResponse, riskLevel: "Critical" });

    render(<AiAssistant events={[makeEvent(1)]} viewContext="dashboard" />);

    await waitFor(() => {
      expect(screen.getByText("Critical Risk")).toBeInTheDocument();
    });
  });
});

describe("AiAssistant debounce behavior", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockGetAiSummary.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fires immediately on first render with events", async () => {
    mockGetAiSummary.mockResolvedValue(mockResponse);

    await act(async () => {
      render(<AiAssistant events={[makeEvent(1)]} viewContext="dashboard" />);
    });

    // With shouldAdvanceTime: true, promises resolve
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(mockGetAiSummary).toHaveBeenCalledTimes(1);
  });

  it("does not re-fire within 30s debounce window", async () => {
    mockGetAiSummary.mockResolvedValue(mockResponse);

    let result: ReturnType<typeof render>;
    await act(async () => {
      result = render(<AiAssistant events={[makeEvent(1)]} viewContext="dashboard" />);
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(mockGetAiSummary).toHaveBeenCalledTimes(1);

    // Rerender with new events within 30s
    await act(async () => {
      result!.rerender(
        <AiAssistant events={[makeEvent(1), makeEvent(2)]} viewContext="dashboard" />
      );
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Should still be 1 — debounce hasn't elapsed
    expect(mockGetAiSummary).toHaveBeenCalledTimes(1);

    // Advance past 30s
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });

    expect(mockGetAiSummary).toHaveBeenCalledTimes(2);
  });
});
