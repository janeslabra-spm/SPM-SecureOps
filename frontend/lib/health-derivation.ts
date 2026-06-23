/**
 * Component health derivation utilities.
 *
 * Each function maps raw API response data to a health percentage (0–100)
 * for the corresponding system component.
 */

// ─── Interfaces ───────────────────────────────────────────────────────────────

/** Input data derived from /stream/status and /health API responses */
export interface HealthDerivationInput {
  /** null = endpoint unreachable or timed out */
  streamStatus: { ok: boolean; fps: number } | null;
  /** null = endpoint unreachable or timed out */
  healthStatus: { ok: boolean; database: boolean; status: string } | null;
}

/** Per-component health percentages */
export interface ComponentHealth {
  camera: number;
  aiEngine: number;
  backend: number;
  database: number;
  aws: number;
  retention: number;
}

// ─── Individual Derivation Functions ──────────────────────────────────────────

/**
 * Camera health: 100% if stream endpoint returns 200, else 0%.
 */
export function deriveCameraHealth(streamOk: boolean): number {
  return streamOk ? 100 : 0;
}

/**
 * AI Engine health: 100% if stream returns 200 AND fps > 0, else 0%.
 */
export function deriveAiEngineHealth(streamOk: boolean, fps: number): number {
  return streamOk && fps > 0 ? 100 : 0;
}

/**
 * Backend health: 100% if health endpoint returns 200, else 0%.
 */
export function deriveBackendHealth(healthOk: boolean): number {
  return healthOk ? 100 : 0;
}

/**
 * Database health: 100% if health endpoint returns 200 AND database is true, else 0%.
 */
export function deriveDatabaseHealth(healthOk: boolean, database: boolean): number {
  return healthOk && database ? 100 : 0;
}

/**
 * AWS health: static placeholder value of 99.9%.
 */
export function deriveAwsHealth(): number {
  return 99.9;
}

/**
 * Retention health: 100% if health status is NOT "unhealthy", else 0%.
 */
export function deriveRetentionHealth(healthStatus: string): number {
  return healthStatus !== "unhealthy" ? 100 : 0;
}

// ─── Composite Derivation ─────────────────────────────────────────────────────

/**
 * Derive all component health values from combined API response data.
 */
export function deriveComponentHealth(input: HealthDerivationInput): ComponentHealth {
  const { streamStatus, healthStatus } = input;

  const streamOk = streamStatus?.ok ?? false;
  const fps = streamStatus?.fps ?? 0;

  const healthOk = healthStatus?.ok ?? false;
  const database = healthStatus?.database ?? false;
  const status = healthStatus?.status ?? "unhealthy";

  return {
    camera: deriveCameraHealth(streamOk),
    aiEngine: deriveAiEngineHealth(streamOk, fps),
    backend: deriveBackendHealth(healthOk),
    database: deriveDatabaseHealth(healthOk, database),
    aws: deriveAwsHealth(),
    retention: deriveRetentionHealth(status),
  };
}

// ─── Status & Color Helpers ───────────────────────────────────────────────────

/** Health status classification based on percentage value */
export type HealthStatusLabel = "healthy" | "warning" | "critical" | "unreachable";

/**
 * Map a health percentage to a status label.
 * - > 90  → "healthy"
 * - 70–90 → "warning"
 * - > 0 and < 70 → "critical"
 * - 0     → "unreachable"
 */
export function getHealthStatus(value: number): HealthStatusLabel {
  if (value > 90) return "healthy";
  if (value >= 70) return "warning";
  if (value > 0) return "critical";
  return "unreachable";
}

/**
 * Map a health percentage to a Tailwind color class for progress bars.
 * - > 90  → green
 * - 70–90 → amber
 * - < 70  → red
 */
export function getHealthColor(value: number): string {
  if (value > 90) return "bg-green-500";
  if (value >= 70) return "bg-amber-500";
  return "bg-red-500";
}
