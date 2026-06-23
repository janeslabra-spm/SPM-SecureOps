import { formatIncidentType, formatIncidentTitle } from "./utils";
import type { ComplianceEvent, EventStatus, ReviewPriority } from "./types";

/**
 * Backend incident structure from GET /incidents.
 */
export interface BackendIncident {
  incident_id: number;
  incident_type: string;
  confidence: number;
  camera_name: string;
  timestamp: string;
  status: string;
  notes: string;
  screenshot_path: string;
}

/**
 * Derive review priority from confidence score.
 *
 * - confidence >= 0.85 → "High Review Priority"
 * - confidence >= 0.50 → "Needs Review"
 * - confidence < 0.50  → "Informational"
 */
export function derivePriority(confidence: number): ReviewPriority {
  if (confidence >= 0.85) return "High Review Priority";
  if (confidence >= 0.50) return "Needs Review";
  return "Informational";
}

/**
 * Map backend status to frontend EventStatus.
 * "False Alarm" → "False Positive"; all others pass through directly.
 */
function mapStatus(backendStatus: string): EventStatus {
  if (backendStatus === "False Alarm") return "False Positive";
  return backendStatus as EventStatus;
}

/**
 * Parse a reviewer name from the notes field.
 * Looks for patterns like "Reviewer: Name" or "Assigned to: Name".
 * Returns empty string if no reviewer is found.
 */
function parseReviewer(notes: string): string {
  if (!notes) return "";
  const reviewerMatch = notes.match(
    /(?:reviewer|assigned to|reviewed by):\s*(.+)/i
  );
  if (reviewerMatch && reviewerMatch[1]) return reviewerMatch[1].trim();
  return "";
}

/**
 * Map a single backend incident response to a ComplianceEvent.
 */
export function mapBackendIncident(incident: BackendIncident): ComplianceEvent {
  return {
    id: incident.incident_id,
    title: formatIncidentTitle(incident.incident_type),
    detail: formatIncidentType(incident.incident_type),
    eventType: incident.incident_type,
    timestamp: incident.timestamp,
    priority: derivePriority(incident.confidence),
    status: mapStatus(incident.status),
    confidence: incident.confidence,
    zone: incident.camera_name,
    reviewer: parseReviewer(incident.notes),
    notes: incident.notes,
    screenshotPath: incident.screenshot_path ?? "",
  };
}

/**
 * Map an array of backend incident responses to ComplianceEvent[].
 */
export function mapBackendIncidents(
  incidents: BackendIncident[]
): ComplianceEvent[] {
  return incidents.map(mapBackendIncident);
}
