import type { ConnectionState } from "../hooks/useWebSocket";

interface SystemStatus {
  ai_engine: "online" | "offline";
  database: "connected" | "disconnected";
  websocket: "active" | "inactive";
}

interface SecurityStatusProps {
  status: SystemStatus | null;
  loading: boolean;
  wsConnectionState?: ConnectionState;
}

interface StatusItemProps {
  label: string;
  isHealthy: boolean;
  color: string;
}

function StatusItem({ label, isHealthy, color }: StatusItemProps) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full`} style={{ backgroundColor: color }} />
        <span className="text-sm text-text-secondary">{label}</span>
      </div>
      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
        isHealthy 
          ? 'bg-success/10 text-success' 
          : 'bg-danger/10 text-danger'
      }`}>
        {isHealthy ? "Online" : "Offline"}
      </span>
    </div>
  );
}

function DonutChart({ percentage }: { percentage: number }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className="relative w-28 h-28 mx-auto">
      <svg className="w-28 h-28 -rotate-90" viewBox="0 0 100 100">
        <circle
          cx="50" cy="50" r={radius}
          stroke="#E5E7EB"
          strokeWidth="8"
          fill="none"
        />
        <circle
          cx="50" cy="50" r={radius}
          stroke="#1B4332"
          strokeWidth="8"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-700"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-xl font-bold text-text-primary">{percentage}%</span>
      </div>
    </div>
  );
}

export default function SecurityStatus({
  status,
  loading,
  wsConnectionState,
}: SecurityStatusProps) {
  const wsConnected = wsConnectionState === "connected";

  // Calculate system health percentage
  let healthyCount = 0;
  let totalCount = 3;
  if (status) {
    if (status.ai_engine === "online") healthyCount++;
    if (status.database === "connected") healthyCount++;
    if (wsConnectionState !== undefined) {
      totalCount = 4;
      if (wsConnected) healthyCount++;
    }
    // Count websocket/third status
    healthyCount++; // backend is online since we got a response
  }
  const healthPercent = status ? Math.round((healthyCount / totalCount) * 100) : 0;

  return (
    <div className="bg-bg-card border border-border rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-text-primary">
          System Health
        </h3>
        <button className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-bg-hover transition-colors">
          <svg className="w-4 h-4 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="1" />
            <circle cx="19" cy="12" r="1" />
            <circle cx="5" cy="12" r="1" />
          </svg>
        </button>
      </div>

      {loading && !status ? (
        <div className="py-6 text-sm text-text-muted text-center">
          Loading...
        </div>
      ) : status ? (
        <>
          <DonutChart percentage={healthPercent} />
          <div className="mt-4 space-y-1 divide-y divide-border-light">
            <StatusItem
              label="AI Engine"
              isHealthy={status.ai_engine === "online"}
              color="#1B4332"
            />
            <StatusItem
              label="Database"
              isHealthy={status.database === "connected"}
              color="#22C55E"
            />
            <StatusItem
              label="Backend"
              isHealthy={status.ai_engine === "online"}
              color="#4ADE80"
            />
            {wsConnectionState !== undefined && (
              <StatusItem
                label="WebSocket"
                isHealthy={wsConnected}
                color="#FB923C"
              />
            )}
          </div>
        </>
      ) : (
        <div className="py-6 text-sm text-danger text-center">
          Unable to fetch status
        </div>
      )}
    </div>
  );
}
