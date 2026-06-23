import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  ComplianceScore,
  calculateComplianceScore,
} from "@/components/widgets/ComplianceScore";
import { ComplianceEvent } from "@/lib/types";

function makeEvent(
  id: number,
  status: ComplianceEvent["status"]
): ComplianceEvent {
  return {
    id,
    title: `Event ${id}`,
    detail: "test detail",
    eventType: "PHONE_ON_TABLE",
    timestamp: "2024-01-01T00:00:00Z",
    priority: "Needs Review",
    status,
    confidence: 0.75,
    zone: "Main Camera",
    reviewer: "",
    notes: "",
  };
}

describe("calculateComplianceScore", () => {
  it("returns 0 when events array is empty", () => {
    expect(calculateComplianceScore([])).toBe(0);
  });

  it("returns 100 when all events are reviewed (non-pending)", () => {
    const events = [
      makeEvent(1, "Confirmed"),
      makeEvent(2, "False Positive"),
      makeEvent(3, "Resolved"),
    ];
    expect(calculateComplianceScore(events)).toBe(100);
  });

  it("returns 0 when all events are Pending Review", () => {
    const events = [
      makeEvent(1, "Pending Review"),
      makeEvent(2, "Pending Review"),
    ];
    expect(calculateComplianceScore(events)).toBe(0);
  });

  it("calculates correctly with mixed statuses", () => {
    const events = [
      makeEvent(1, "Confirmed"),
      makeEvent(2, "Pending Review"),
      makeEvent(3, "Resolved"),
      makeEvent(4, "Pending Review"),
    ];
    // 2 non-pending / 4 total = 50%
    expect(calculateComplianceScore(events)).toBe(50);
  });

  it("handles single reviewed event", () => {
    const events = [makeEvent(1, "Warning Issued")];
    expect(calculateComplianceScore(events)).toBe(100);
  });

  it("handles single pending event", () => {
    const events = [makeEvent(1, "Pending Review")];
    expect(calculateComplianceScore(events)).toBe(0);
  });
});

describe("ComplianceScore component", () => {
  it("renders 0% with no events", () => {
    render(<ComplianceScore events={[]} />);
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getByText("%")).toBeInTheDocument();
    expect(screen.getByText("No incidents recorded")).toBeInTheDocument();
  });

  it("renders correct percentage and count text", () => {
    const events = [
      makeEvent(1, "Confirmed"),
      makeEvent(2, "Pending Review"),
      makeEvent(3, "Resolved"),
    ];
    render(<ComplianceScore events={events} />);
    // 2 of 3 = 66.67%, rounded to 67
    expect(screen.getByText("67")).toBeInTheDocument();
    expect(screen.getByText("2 of 3 incidents reviewed")).toBeInTheDocument();
  });

  it("renders Compliance Score heading", () => {
    render(<ComplianceScore events={[]} />);
    expect(screen.getByText("Compliance Score")).toBeInTheDocument();
  });
});
