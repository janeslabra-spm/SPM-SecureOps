import { describe, it, expect } from "vitest";
import {
  deriveCameraHealth,
  deriveAiEngineHealth,
  deriveBackendHealth,
  deriveDatabaseHealth,
  deriveAwsHealth,
  deriveRetentionHealth,
  deriveComponentHealth,
  getHealthStatus,
  getHealthColor,
} from "@/lib/health-derivation";
import type { HealthDerivationInput } from "@/lib/health-derivation";

describe("deriveCameraHealth", () => {
  it("returns 100 when stream endpoint is OK", () => {
    expect(deriveCameraHealth(true)).toBe(100);
  });

  it("returns 0 when stream endpoint is not OK", () => {
    expect(deriveCameraHealth(false)).toBe(0);
  });
});

describe("deriveAiEngineHealth", () => {
  it("returns 100 when stream is OK and fps > 0", () => {
    expect(deriveAiEngineHealth(true, 30)).toBe(100);
    expect(deriveAiEngineHealth(true, 0.1)).toBe(100);
  });

  it("returns 0 when stream is OK but fps is 0", () => {
    expect(deriveAiEngineHealth(true, 0)).toBe(0);
  });

  it("returns 0 when stream is not OK regardless of fps", () => {
    expect(deriveAiEngineHealth(false, 30)).toBe(0);
    expect(deriveAiEngineHealth(false, 0)).toBe(0);
  });
});

describe("deriveBackendHealth", () => {
  it("returns 100 when health endpoint is OK", () => {
    expect(deriveBackendHealth(true)).toBe(100);
  });

  it("returns 0 when health endpoint is not OK", () => {
    expect(deriveBackendHealth(false)).toBe(0);
  });
});

describe("deriveDatabaseHealth", () => {
  it("returns 100 when health is OK and database is true", () => {
    expect(deriveDatabaseHealth(true, true)).toBe(100);
  });

  it("returns 0 when health is OK but database is false", () => {
    expect(deriveDatabaseHealth(true, false)).toBe(0);
  });

  it("returns 0 when health is not OK regardless of database", () => {
    expect(deriveDatabaseHealth(false, true)).toBe(0);
    expect(deriveDatabaseHealth(false, false)).toBe(0);
  });
});

describe("deriveAwsHealth", () => {
  it("always returns 99.9", () => {
    expect(deriveAwsHealth()).toBe(99.9);
  });
});

describe("deriveRetentionHealth", () => {
  it("returns 100 when status is 'healthy'", () => {
    expect(deriveRetentionHealth("healthy")).toBe(100);
  });

  it("returns 100 when status is 'degraded'", () => {
    expect(deriveRetentionHealth("degraded")).toBe(100);
  });

  it("returns 0 when status is 'unhealthy'", () => {
    expect(deriveRetentionHealth("unhealthy")).toBe(0);
  });
});

describe("deriveComponentHealth", () => {
  it("derives all components healthy when all data is good", () => {
    const input: HealthDerivationInput = {
      streamStatus: { ok: true, fps: 30 },
      healthStatus: { ok: true, database: true, status: "healthy" },
    };
    const result = deriveComponentHealth(input);
    expect(result.camera).toBe(100);
    expect(result.aiEngine).toBe(100);
    expect(result.backend).toBe(100);
    expect(result.database).toBe(100);
    expect(result.aws).toBe(99.9);
    expect(result.retention).toBe(100);
  });

  it("derives all components unhealthy when endpoints are unreachable (null)", () => {
    const input: HealthDerivationInput = {
      streamStatus: null,
      healthStatus: null,
    };
    const result = deriveComponentHealth(input);
    expect(result.camera).toBe(0);
    expect(result.aiEngine).toBe(0);
    expect(result.backend).toBe(0);
    expect(result.database).toBe(0);
    expect(result.aws).toBe(99.9); // AWS is always static
    expect(result.retention).toBe(0);
  });

  it("handles stream OK but fps=0 (AI engine unhealthy)", () => {
    const input: HealthDerivationInput = {
      streamStatus: { ok: true, fps: 0 },
      healthStatus: { ok: true, database: true, status: "healthy" },
    };
    const result = deriveComponentHealth(input);
    expect(result.camera).toBe(100);
    expect(result.aiEngine).toBe(0);
  });

  it("handles health OK but database false", () => {
    const input: HealthDerivationInput = {
      streamStatus: { ok: true, fps: 15 },
      healthStatus: { ok: true, database: false, status: "healthy" },
    };
    const result = deriveComponentHealth(input);
    expect(result.backend).toBe(100);
    expect(result.database).toBe(0);
  });

  it("handles degraded health status (retention still healthy)", () => {
    const input: HealthDerivationInput = {
      streamStatus: { ok: true, fps: 25 },
      healthStatus: { ok: true, database: true, status: "degraded" },
    };
    const result = deriveComponentHealth(input);
    expect(result.retention).toBe(100);
  });

  it("handles unhealthy status (retention drops to 0)", () => {
    const input: HealthDerivationInput = {
      streamStatus: { ok: true, fps: 25 },
      healthStatus: { ok: true, database: true, status: "unhealthy" },
    };
    const result = deriveComponentHealth(input);
    expect(result.retention).toBe(0);
  });
});

describe("getHealthStatus", () => {
  it("returns 'healthy' for values above 90", () => {
    expect(getHealthStatus(91)).toBe("healthy");
    expect(getHealthStatus(100)).toBe("healthy");
    expect(getHealthStatus(99.9)).toBe("healthy");
  });

  it("returns 'warning' for values between 70 and 90 inclusive", () => {
    expect(getHealthStatus(70)).toBe("warning");
    expect(getHealthStatus(80)).toBe("warning");
    expect(getHealthStatus(90)).toBe("warning");
  });

  it("returns 'critical' for values above 0 and below 70", () => {
    expect(getHealthStatus(69)).toBe("critical");
    expect(getHealthStatus(1)).toBe("critical");
    expect(getHealthStatus(50)).toBe("critical");
  });

  it("returns 'unreachable' for value of 0", () => {
    expect(getHealthStatus(0)).toBe("unreachable");
  });
});

describe("getHealthColor", () => {
  it("returns green class for values above 90", () => {
    expect(getHealthColor(91)).toBe("bg-green-500");
    expect(getHealthColor(100)).toBe("bg-green-500");
  });

  it("returns amber class for values between 70 and 90 inclusive", () => {
    expect(getHealthColor(70)).toBe("bg-amber-500");
    expect(getHealthColor(80)).toBe("bg-amber-500");
    expect(getHealthColor(90)).toBe("bg-amber-500");
  });

  it("returns red class for values below 70", () => {
    expect(getHealthColor(69)).toBe("bg-red-500");
    expect(getHealthColor(0)).toBe("bg-red-500");
    expect(getHealthColor(50)).toBe("bg-red-500");
  });
});
