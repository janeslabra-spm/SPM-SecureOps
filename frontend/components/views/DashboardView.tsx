"use client";

import { useState, useCallback } from "react";
import { Camera, Cctv, ScanLine } from "lucide-react";

import { usePolling } from "@/hooks/usePolling";
import { useApiClient } from "@/hooks/useApiClient";
import { POLLING_INTERVALS } from "@/lib/constants";
import { mapBackendIncidents, BackendIncident } from "@/lib/incident-mapper";
import type { ComplianceEvent } from "@/lib/types";

import { SystemStatusCards } from "@/components/widgets/SystemStatusCards";
import { StreamPreview } from "@/components/widgets/StreamPreview";
import { BrowserCamera } from "@/components/widgets/BrowserCamera";
import { EventFeed } from "@/components/widgets/EventFeed";
import { AiAssistant } from "@/components/widgets/AiAssistant";
import { ComplianceScore } from "@/components/widgets/ComplianceScore";
import { GovernanceBadges } from "@/components/widgets/GovernanceBadges";

export function DashboardView() {
  const api = useApiClient();
  const [sourceMode, setSourceMode] = useState<"browser" | "stream">("browser");

  const fetcher = useCallback(async (): Promise<ComplianceEvent[]> => {
    const raw = await api.getIncidents();
    return mapBackendIncidents(raw as BackendIncident[]);
  }, [api]);

  const { data: events, loading } = usePolling<ComplianceEvent[]>(
    fetcher,
    POLLING_INTERVALS.DASHBOARD
  );

  const allEvents = events ?? [];

  return (
    <div data-testid="view-dashboard" className="flex flex-col gap-4">
      <SystemStatusCards />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* Left column: Live monitoring + AI + Score */}
        <div className="flex flex-col gap-4 xl:col-span-2">
          {/* Live stream */}
          <LiveMonitoringCard sourceMode={sourceMode} onSourceChange={setSourceMode} />

          {/* AI + Score */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <AiAssistant events={allEvents} viewContext="dashboard" />
            <ComplianceScore events={allEvents} />
          </div>
        </div>

        {/* Right column: Scrollable Event Feed */}
        <div className="xl:col-span-1 xl:max-h-[calc(100vh-220px)] xl:sticky xl:top-4">
          <EventFeed
            events={allEvents}
            loading={loading && !events}
            maxItems={20}
            className="h-full max-h-[600px] xl:max-h-full"
          />
        </div>
      </div>

      <GovernanceBadges />
    </div>
  );
}

/** Inline live monitoring card for the dashboard — uses browser camera by default */
function LiveMonitoringCard({
  sourceMode,
  onSourceChange,
}: {
  sourceMode: "browser" | "stream";
  onSourceChange: (mode: "browser" | "stream") => void;
}) {
  const isBrowserCamera = sourceMode === "browser";

  return (
    <section className="glass overflow-hidden rounded-2xl">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div className="flex items-center gap-2.5">
          <div className="grid size-8 place-items-center rounded-lg bg-primary/12 text-primary">
            {isBrowserCamera ? <Camera className="size-4" /> : <Cctv className="size-4" />}
          </div>
          <div>
            <h2 className="text-sm font-semibold">Live Compliance Monitoring</h2>
            <p className="text-xs text-muted-foreground">
              {isBrowserCamera ? "Browser camera with AI detection" : "Real-time detection overlay"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Source toggle */}
          <div className="flex rounded-lg border border-border bg-muted/50 p-0.5">
            <button
              onClick={() => onSourceChange("browser")}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                isBrowserCamera
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Camera className="size-3" />
              Browser
            </button>
            <button
              onClick={() => onSourceChange("stream")}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                !isBrowserCamera
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Cctv className="size-3" />
              MJPEG
            </button>
          </div>

          <div className="flex items-center gap-2 rounded-full bg-danger/15 px-2.5 py-1 ring-1 ring-danger/30">
            <span className="size-2 rounded-full bg-danger pulse-dot" />
            <span className="text-xs font-semibold tracking-wide text-danger">LIVE</span>
          </div>
        </div>
      </div>

      {/* Conditionally render browser camera or MJPEG stream */}
      {isBrowserCamera ? (
        <div className="p-4">
          <BrowserCamera active={true} fps={2} />
        </div>
      ) : (
        <StreamPreview isActive={true} />
      )}

      <div className="flex items-center justify-between border-t border-border bg-gradient-to-t from-background/80 to-transparent px-5 py-3">
        <div>
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Camera Source</p>
          <p className="text-sm font-semibold">
            {isBrowserCamera ? "Browser Camera — User Device" : "BPO Operations Floor — Camera 01"}
          </p>
        </div>
        <div className="flex items-center gap-1.5 rounded-full bg-success/20 px-2.5 py-1 ring-1 ring-success/40">
          <ScanLine className="size-3.5 text-success" />
          <span className="text-xs font-medium text-success">AI Detection Active</span>
        </div>
      </div>
    </section>
  );
}

export default DashboardView;
