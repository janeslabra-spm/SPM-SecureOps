import axios, { AxiosInstance } from "axios";
import type {
  ComplianceEvent,
  HealthStatus,
  StreamMetrics,
  DeskZoneConfig,
  AiSummaryRequest,
  AiSummaryResponse,
  IncidentQueryParams,
  EventStatus,
} from "./types";
import { API_TIMEOUT } from "./constants";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: BASE_URL,
      timeout: API_TIMEOUT,
      headers: { "Content-Type": "application/json" },
    });
  }

  // ─── Incidents ──────────────────────────────────────────────────────

  /**
   * Fetch incidents from the backend.
   * Returns raw backend response data. Use the mapping function
   * (from lib/incident-mapper) to convert to ComplianceEvent[].
   */
  async getIncidents(params?: IncidentQueryParams): Promise<unknown[]> {
    const response = await this.client.get("/incidents", { params });
    return response.data;
  }

  /**
   * Update an incident's status.
   */
  async updateIncidentStatus(
    id: number,
    status: EventStatus
  ): Promise<ComplianceEvent> {
    const response = await this.client.patch(
      `/incidents/${id}/status`,
      { status }
    );
    return response.data;
  }

  /**
   * Export incidents as CSV. Returns a Blob suitable for download.
   */
  async exportIncidentsCsv(params?: IncidentQueryParams): Promise<Blob> {
    const response = await this.client.get("/incidents/export", {
      params,
      responseType: "blob",
    });
    return response.data;
  }

  // ─── Health ─────────────────────────────────────────────────────────

  /**
   * Fetch system health status from the backend.
   */
  async getHealth(): Promise<HealthStatus> {
    const response = await this.client.get("/health");
    return response.data;
  }

  // ─── Stream ─────────────────────────────────────────────────────────

  /**
   * Fetch stream detection metrics.
   */
  async getStreamStatus(): Promise<StreamMetrics> {
    const response = await this.client.get("/stream/status");
    return response.data;
  }

  /**
   * Returns the MJPEG stream URL (synchronous — just constructs the URL).
   */
  getStreamUrl(): string {
    return `${BASE_URL}/stream/video.mjpg`;
  }

  // ─── Zones ──────────────────────────────────────────────────────────

  /**
   * Fetch the current desk zone configuration.
   */
  async getDeskZone(): Promise<DeskZoneConfig> {
    const response = await this.client.get("/zones/desk");
    return response.data;
  }

  /**
   * Update the desk zone configuration.
   */
  async updateDeskZone(config: DeskZoneConfig): Promise<DeskZoneConfig> {
    const response = await this.client.put("/zones/desk", config);
    return response.data;
  }

  // ─── AI ─────────────────────────────────────────────────────────────

  /**
   * Request an AI-generated compliance summary from the backend proxy.
   */
  async getAiSummary(context: AiSummaryRequest): Promise<AiSummaryResponse> {
    const response = await this.client.post("/api/ai/summary", context);
    return response.data;
  }
}

/** Singleton API client instance */
export const apiClient = new ApiClient();
