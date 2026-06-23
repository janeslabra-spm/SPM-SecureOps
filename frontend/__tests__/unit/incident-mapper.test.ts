import { describe, it, expect } from "vitest";
import {
  mapBackendIncident,
  mapBackendIncidents,
  derivePriority,
  BackendIncident,
} from "@/lib/incident-mapper";

describe("derivePriority", () => {
  it("returns 'High Review Priority' for confidence >= 0.85", () => {
    expect(derivePriority(0.85)).toBe("High Review Priority");
    expect(derivePriority(0.99)).toBe("High Review Priority");
    expect(derivePriority(1.0)).toBe("High Review Priority");
  });

  it("returns 'Needs Review' for confidence >= 0.50 and < 0.85", () => {
    expect(derivePriority(0.50)).toBe("Needs Review");
    expect(derivePriority(0.70)).toBe("Needs Review");
    expect(derivePriority(0.84)).toBe("Needs Review");
  });

  it("returns 'Informational' for confidence < 0.50", () => {
    expect(derivePriority(0.49)).toBe("Informational");
    expect(derivePriority(0.0)).toBe("Informational");
    expect(derivePriority(0.25)).toBe("Informational");
  });
});

describe("mapBackendIncident", () => {
  const baseIncident: BackendIncident = {
    incident_id: 42,
    incident_type: "PHONE_ON_TABLE",
    confidence: 0.92,
    camera_name: "Front Desk Camera",
    timestamp: "2024-01-15T10:30:00Z",
    status: "Pending Review",
    notes: "Detected during morning shift",
    screenshot_path: "screenshots/incident_42.jpg",
  };

  it("maps incident_id to id", () => {
    const event = mapBackendIncident(baseIncident);
    expect(event.id).toBe(42);
  });

  it("maps incident_type to detail (underscores replaced with spaces)", () => {
    const event = mapBackendIncident(baseIncident);
    expect(event.detail).toBe("PHONE ON TABLE");
  });

  it("maps incident_type to eventType (raw value)", () => {
    const event = mapBackendIncident(baseIncident);
    expect(event.eventType).toBe("PHONE_ON_TABLE");
  });

  it("maps incident_type to title (capitalized with spaces)", () => {
    const event = mapBackendIncident(baseIncident);
    expect(event.title).toBe("Phone On Table");
  });

  it("maps confidence to priority using derivePriority thresholds", () => {
    const highConfidence = mapBackendIncident({
      ...baseIncident,
      confidence: 0.90,
    });
    expect(highConfidence.priority).toBe("High Review Priority");

    const medConfidence = mapBackendIncident({
      ...baseIncident,
      confidence: 0.65,
    });
    expect(medConfidence.priority).toBe("Needs Review");

    const lowConfidence = mapBackendIncident({
      ...baseIncident,
      confidence: 0.30,
    });
    expect(lowConfidence.priority).toBe("Informational");
  });

  it("preserves confidence as-is", () => {
    const event = mapBackendIncident(baseIncident);
    expect(event.confidence).toBe(0.92);
  });

  it("maps status 'False Alarm' to 'False Positive'", () => {
    const event = mapBackendIncident({
      ...baseIncident,
      status: "False Alarm",
    });
    expect(event.status).toBe("False Positive");
  });

  it("preserves other status values directly", () => {
    const pending = mapBackendIncident({
      ...baseIncident,
      status: "Pending Review",
    });
    expect(pending.status).toBe("Pending Review");

    const confirmed = mapBackendIncident({
      ...baseIncident,
      status: "Confirmed",
    });
    expect(confirmed.status).toBe("Confirmed");
  });

  it("maps camera_name to zone", () => {
    const event = mapBackendIncident(baseIncident);
    expect(event.zone).toBe("Front Desk Camera");
  });

  it("maps timestamp directly", () => {
    const event = mapBackendIncident(baseIncident);
    expect(event.timestamp).toBe("2024-01-15T10:30:00Z");
  });

  it("maps notes directly", () => {
    const event = mapBackendIncident(baseIncident);
    expect(event.notes).toBe("Detected during morning shift");
  });

  it("parses reviewer from notes when pattern is present", () => {
    const event = mapBackendIncident({
      ...baseIncident,
      notes: "Reviewer: John Smith",
    });
    expect(event.reviewer).toBe("John Smith");
  });

  it("returns empty reviewer when no reviewer pattern in notes", () => {
    const event = mapBackendIncident(baseIncident);
    expect(event.reviewer).toBe("");
  });

  it("handles empty notes gracefully", () => {
    const event = mapBackendIncident({ ...baseIncident, notes: "" });
    expect(event.reviewer).toBe("");
    expect(event.notes).toBe("");
  });
});

describe("mapBackendIncidents", () => {
  it("maps an array of backend incidents to ComplianceEvent[]", () => {
    const incidents: BackendIncident[] = [
      {
        incident_id: 1,
        incident_type: "PHONE_HELD_OR_NEAR_PERSON",
        confidence: 0.88,
        camera_name: "Zone A",
        timestamp: "2024-01-15T09:00:00Z",
        status: "Confirmed",
        notes: "",
        screenshot_path: "screenshots/incident_1.jpg",
      },
      {
        incident_id: 2,
        incident_type: "PHONE_ON_TABLE",
        confidence: 0.45,
        camera_name: "Zone B",
        timestamp: "2024-01-15T09:05:00Z",
        status: "False Alarm",
        notes: "Reviewed by: Jane Doe",
        screenshot_path: "",
      },
    ];

    const events = mapBackendIncidents(incidents);
    expect(events).toHaveLength(2);
    expect(events[0].id).toBe(1);
    expect(events[0].priority).toBe("High Review Priority");
    expect(events[1].id).toBe(2);
    expect(events[1].status).toBe("False Positive");
    expect(events[1].priority).toBe("Informational");
  });

  it("returns empty array for empty input", () => {
    expect(mapBackendIncidents([])).toEqual([]);
  });
});
