"use client";

import { useState, useCallback } from "react";
import { Cctv, ScanLine, Camera, Activity, Eye, Zap } from "lucide-react";

import { usePolling } from "@/hooks/usePolling";
import { useApiClient } from "@/hooks/useApiClient";
import { POLLING_INTERVALS } from "@/lib/constants";
import { mapBackendIncidents, BackendIncident } from "@/lib/incident-mapper";
import type { ComplianceEvent } from "@/lib/types";

import { StreamPreview } from "@/components/widgets/StreamPreview";
import { BrowserCamera } from "@/components/widgets/BrowserCamera";
import { EventFeed } from "@/components/widgets/EventFeed";
import { PipelineControls } from "@/components/widgets/PipelineControls";
import type { SourcePreset } from "@/components/widgets/PipelineControls";

export function LiveMonitoringView() {
  const api = useApiClient();
  const [sourcePreset, setSourcePreset] = useState<SourcePreset>("browser");

  const eventsFetcher = useCallback(async (): Promise<ComplianceEvent[]> => {
    const raw = await api.getIncidents();
    return mapBackendIncidents(raw as BackendIncident[]);
  }, [api]);

  const { data: events, loading: eventsLoading } = usePolling<ComplianceEvent[]>(
    eventsFetcher,
    POLLING_INTERVALS.DASHBOARD
  );

  const allEvents = events ?? [];
  const isBrowserCamera = sourcePreset === "browser";

  // For non-browser sources (demo, rtsp, file), show the MJPEG stream
  // which carries the annotated detection output from the pipeline
  const showMjpegStream = !isBrowserCamera;

  // Compute live stats
  const todayEvents = allEvents.filter((e) => {
    const d = new Date(e.timestamp);
    const now = new Date();
    return d.toDateString() === now.toDateString();
  });
  const pendingCount = allEvents.filter((e) => e.status === "Pending Review").length;
  const phoneEvents = allEvents.filter(
    (e) => e.eventType === "PHONE_ON_TABLE" || e.eventType === "PHONE_NEAR_PERSON" || e.eventType === "PHONE_HELD_OR_NEAR_PERSON"
  ).length;

  return (
    <div data-testid="view-live" className="flex flex-col gap-4">
      {/* Live stats bar */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard icon={Activity} label="Active Detections" value={String(todayEvents.length)} tone="info" />
        <StatCard icon={Eye} label="Pending Review" value={String(pendingCount)} tone="warning" />
        <StatCard icon={Zap} label="Phone Events" value={String(phoneEvents)} tone="danger" />
        <StatCard icon={Camera} label="Source" value={sourcePreset === "browser" ? "Browser Cam" : sourcePreset === "demo" ? "Demo Video" : "Pipeline"} tone="success" />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        {/* Left: Live video feed — takes more space */}
        <section className="glass flex flex-col overflow-hidden rounded-2xl xl:col-span-7">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div className="flex items-center gap-2.5">
              <div className="grid size-8 place-items-center rounded-lg bg-primary/12 text-primary">
                {isBrowserCamera ? <Camera className="size-4" /> : <Cctv className="size-4" />}
              </div>
              <div>
                <h2 className="text-sm font-semibold">Live Compliance Monitoring</h2>
                <p className="text-xs text-muted-foreground">
                  {isBrowserCamera
                    ? "Browser camera with AI detection"
                    : sourcePreset === "demo"
                      ? "Demo video with AI detection overlay"
                      : "Real-time detection overlay"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-full bg-danger/15 px-2.5 py-1 ring-1 ring-danger/30">
              <span className="size-2 rounded-full bg-danger pulse-dot" />
              <span className="text-xs font-semibold tracking-wide text-danger">LIVE</span>
            </div>
          </div>

          {/* Video area — flexible height */}
          <div className="flex-1">
            {showMjpegStream ? (
              <StreamPreview isActive={true} />
            ) : (
              <div className="p-4 h-full">
                <BrowserCamera active={true} fps={2} />
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between border-t border-border bg-gradient-to-t from-background/80 to-transparent px-5 py-3">
            <div>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Camera Source</p>
              <p className="text-sm font-semibold">
                {isBrowserCamera
                  ? "Browser Camera — User Device"
                  : sourcePreset === "demo"
                    ? "Demo Video — /app/backend/demo1.mp4"
                    : sourcePreset === "rtsp"
                      ? "Live Camera (RTSP/HTTP)"
                      : "Custom File Source"}
              </p>
            </div>
            <div className="flex items-center gap-1.5 rounded-full bg-success/20 px-2.5 py-1 ring-1 ring-success/40">
              <ScanLine className="size-3.5 text-success" />
              <span className="text-xs font-medium text-success">AI Detection Active</span>
            </div>
          </div>
        </section>

        {/* Right column: Pipeline controls + Event Feed — scrollable */}
        <div className="flex flex-col gap-4 xl:col-span-5 xl:max-h-[calc(100vh-240px)]">
          <PipelineControls onSourceChange={setSourcePreset} />
          <EventFeed
            events={allEvents}
            loading={eventsLoading && !events}
            maxItems={30}
            className="flex-1 min-h-0"
          />
        </div>
      </div>
    </div>
  );
}

/** Small stat card for the live monitoring header */
function StatCard({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  tone: "success" | "warning" | "danger" | "info";
}) {
  const toneStyles = {
    success: { icon: "text-success bg-success/12", value: "text-success" },
    warning: { icon: "text-warning bg-warning/12", value: "text-warning" },
    danger: { icon: "text-danger bg-danger/12", value: "text-danger" },
    info: { icon: "text-info bg-info/12", value: "text-info" },
  } as const;

  const t = toneStyles[tone];

  return (
    <div className="glass rounded-xl p-3.5 transition-colors hover:border-primary/30">
      <div className="flex items-center gap-2.5">
        <div className={`grid size-8 place-items-center rounded-lg ${t.icon}`}>
          <Icon className="size-4" />
        </div>
        <div className="min-w-0">
          <p className="text-[11px] text-muted-foreground truncate">{label}</p>
          <p className={`text-base font-bold tabular-nums ${t.value}`}>{value}</p>
        </div>
      </div>
    </div>
  );
}

export default LiveMonitoringView;
