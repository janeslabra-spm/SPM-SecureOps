/** Review priority classification derived from confidence score */
export type ReviewPriority =
  | "High Review Priority"
  | "Needs Review"
  | "Informational";

/** Compliance event lifecycle status */
export type EventStatus =
  | "Pending Review"
  | "Confirmed"
  | "False Positive"
  | "Warning Issued"
  | "Coaching Required"
  | "Escalated"
  | "Resolved";

/** Compliance event mapped from backend Incident model */
export interface ComplianceEvent {
  id: number;
  title: string;
  detail: string;
  eventType: string;
  timestamp: string; // ISO 8601
  priority: ReviewPriority;
  status: EventStatus;
  confidence: number;
  zone: string;
  reviewer: string;
  notes: string;
}

/** Backend GET /health response */
export interface HealthStatus {
  status: "healthy" | "degraded" | "unhealthy";
  database: boolean;
  detection_engine_active: boolean;
  uptime_seconds: number;
}

/** Backend GET /stream/status response */
export interface StreamMetrics {
  people: number;
  phones: number;
  active_rule_matches: number;
  logged_this_frame: number;
  inference_ms: number;
  fps: number;
  message: string;
}

/** Backend GET/PUT /zones/desk */
export interface DeskZoneConfig {
  x1_percent: number;
  y1_percent: number;
  x2_percent: number;
  y2_percent: number;
}

/** AI summary request payload */
export interface AiSummaryRequest {
  events: Array<{
    id: number;
    type: string;
    confidence: number;
    timestamp: string;
  }>;
  viewContext: string;
}

/** AI summary response */
export interface AiSummaryResponse {
  summary: string;
  riskLevel: "Low" | "Medium" | "High" | "Critical";
  activeViolations: Record<string, number>;
  patterns: string;
}

/** Incident query parameters */
export interface IncidentQueryParams {
  start_date?: string;
  end_date?: string;
  incident_type?: string;
  status?: string;
}

/** AWS service card display model */
export interface AwsServiceCard {
  name: string;
  role: string;
  region: string;
  uptimePercent: number;
  status: "Operational" | "Degraded";
}
