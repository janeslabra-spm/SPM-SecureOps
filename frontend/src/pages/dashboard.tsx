import { useState, useEffect, useCallback, useRef } from "react";
import StatusCard from "../components/StatusCard";
import DetectionFeed, { DetectionEntry } from "../components/DetectionFeed";
import AnalyticsGraph from "../components/AnalyticsGraph";
import SecurityStatus from "../components/SecurityStatus";
import AlertBanner, { AlertItem } from "../components/AlertBanner";
import { usePolling } from "../hooks/usePolling";
import api from "../services/api";

interface HealthStatus {
  status: string;
  database: boolean;
  detection_engine_active: boolean;
  uptime_seconds: number;
}

interface SystemStatus {
  ai_engine: "online" | "offline";
  database: "connected" | "disconnected";
  websocket: "active" | "inactive";
}

interface StreamStatus {
  people: number;
  phones: number;
  active_rule_matches: number;
  logged_this_frame: number;
  inference_ms: number;
  fps: number;
}

interface Incident {
  incident_id: number;
  timestamp: string;
  incident_type: string;
  confidence: number;
  camera_name: string;
  location: string;
  status: string;
}

export default function DashboardPage() {
  const [detectionEntries, setDetectionEntries] = useState<DetectionEntry[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const lastSeenIdRef = useRef<number>(0);

  const handleDismissAlert = useCallback((id: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }, []);

  // Poll GET /health every 10 seconds
  const { data: systemStatus, loading: statusLoading } = usePolling<SystemStatus>({
    fetchFn: useCallback(async () => {
      const res = await api.get("/health");
      const health: HealthStatus = res.data;
      return {
        ai_engine: health.detection_engine_active ? "online" : "offline",
        database: health.database ? "connected" : "disconnected",
        websocket: "inactive" as const,
      };
    }, []),
    interval: 10000,
  });

  // Poll stream status
  const { data: streamStatus } = usePolling<StreamStatus>({
    fetchFn: useCallback(async () => {
      const res = await api.get("/stream/status");
      return res.data;
    }, []),
    interval: 5000,
  });

  // Fetch incidents
  useEffect(() => {
    const fetchIncidents = async () => {
      try {
        const res = await api.get("/incidents");
        const data: Incident[] = res.data;
        setIncidents(data);

        const entries: DetectionEntry[] = data.slice(0, 50).map((inc) => ({
          id: inc.incident_id,
          timestamp: inc.timestamp,
          incident_type: inc.incident_type,
          confidence: inc.confidence,
        }));
        setDetectionEntries(entries);

        if (data.length > 0) {
          const latestId = data[0].incident_id;
          if (lastSeenIdRef.current > 0 && latestId > lastSeenIdRef.current) {
            const newIncidents = data.filter((inc) => inc.incident_id > lastSeenIdRef.current);
            const newAlerts: AlertItem[] = newIncidents.map((inc) => ({
              id: `poll-${inc.incident_id}-${Date.now()}`,
              incidentType: inc.incident_type,
              confidence: inc.confidence,
              timestamp: Date.now(),
            }));
            setAlerts((prev) => [...prev, ...newAlerts]);
          }
          lastSeenIdRef.current = latestId;
        }
      } catch {
        // Keep existing data on error
      }
    };

    fetchIncidents();
    const timer = setInterval(fetchIncidents, 5000);
    return () => clearInterval(timer);
  }, []);

  // Compute values
  const activeViolations = streamStatus?.active_rule_matches ?? 0;
  const modelFps = streamStatus ? `${streamStatus.fps.toFixed(1)} FPS` : "N/A";
  const phonesDetected = streamStatus?.phones ?? 0;
  const peopleDetected = streamStatus?.people ?? 0;

  return (
    <div className="flex flex-col gap-6">
      {/* Alert Banner */}
      <AlertBanner alerts={alerts} onDismiss={handleDismissAlert} />

      {/* Stats Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatusCard
          title="Active Violations"
          value={activeViolations}
          highlight={activeViolations > 0}
          icon={
            <svg className={`w-5 h-5 ${activeViolations > 0 ? 'text-white' : 'text-danger'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
          }
          trend={{
            value: `${activeViolations}`,
            direction: activeViolations > 0 ? 'up' : 'neutral',
          }}
        />
        <StatusCard
          title="Phones Detected"
          value={phonesDetected}
          icon={
            <svg className="w-5 h-5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
              <line x1="12" y1="18" x2="12.01" y2="18" />
            </svg>
          }
          trend={{ value: `${phonesDetected} active`, direction: phonesDetected > 0 ? 'up' : 'neutral' }}
        />
        <StatusCard
          title="People in Frame"
          value={peopleDetected}
          icon={
            <svg className="w-5 h-5 text-info" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 00-3-3.87" />
              <path d="M16 3.13a4 4 0 010 7.75" />
            </svg>
          }
        />
        <StatusCard
          title="Model Performance"
          value={modelFps}
          icon={
            <svg className="w-5 h-5 text-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
          }
          trend={{ value: streamStatus ? `${streamStatus.inference_ms.toFixed(0)}ms` : 'N/A', direction: 'neutral' }}
        />
      </div>

      {/* Main Content: Chart + Security Status side panel */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
        {/* Left column */}
        <div className="flex flex-col gap-6">
          {/* Analytics Graph */}
          <AnalyticsGraph incidents={incidents} />

          {/* Recent Detections Table */}
          <DetectionFeed entries={detectionEntries} />
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-6">
          {/* System Health */}
          <SecurityStatus status={systemStatus} loading={statusLoading} />

          {/* Camera Status Card */}
          <div className="bg-bg-card border border-border rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-text-primary">
                Camera Status
              </h3>
              <button className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-bg-hover transition-colors">
                <svg className="w-4 h-4 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="1" />
                  <circle cx="19" cy="12" r="1" />
                  <circle cx="5" cy="12" r="1" />
                </svg>
              </button>
            </div>
            
            {/* Camera status indicator (no live stream to avoid blocking the API worker) */}
            <div className="relative rounded-lg overflow-hidden bg-black aspect-video mb-3 flex items-center justify-center">
              <div className="flex flex-col items-center gap-2">
                <svg className="w-10 h-10 text-white/30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M23 7l-7 5 7 5V7z" />
                  <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                </svg>
                <span className="text-white/50 text-xs">Live feed on Camera page</span>
              </div>
            </div>
            
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
                <span className="text-text-secondary">Camera 1 — Active</span>
              </div>
              <span className="text-text-muted">1/1 Online</span>
            </div>
          </div>

          {/* Recent Activity */}
          <div className="bg-bg-card border border-border rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-text-primary">
                Recent Activity
              </h3>
              <button className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-bg-hover transition-colors">
                <svg className="w-4 h-4 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="1" />
                  <circle cx="19" cy="12" r="1" />
                  <circle cx="5" cy="12" r="1" />
                </svg>
              </button>
            </div>
            <div className="space-y-3">
              {incidents.slice(0, 4).map((inc, i) => (
                <div key={inc.incident_id || i} className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-full bg-bg-page flex items-center justify-center flex-shrink-0 mt-0.5">
                    <div className={`w-2 h-2 rounded-full ${
                      inc.status === 'Confirmed' ? 'bg-danger' : inc.status === 'False Alarm' ? 'bg-text-muted' : 'bg-warning'
                    }`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-text-primary truncate">
                      {inc.incident_type.replace(/_/g, ' ')}
                    </p>
                    <p className="text-xs text-text-muted">
                      {new Date(inc.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                </div>
              ))}
              {incidents.length === 0 && (
                <p className="text-xs text-text-muted text-center py-2">No recent activity</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
