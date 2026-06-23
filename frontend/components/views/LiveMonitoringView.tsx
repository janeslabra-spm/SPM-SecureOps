"use client";

import { useState, useCallback } from "react";
import { Cctv, ScanLine, Camera } from "lucide-react";

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

  const isBrowserCamera = sourcePreset === "browser";

  return (
    <div data-testid="view-live" className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      {/* Live stream card */}
      <section className="glass overflow-hidden rounded-2xl xl:col-span-2">
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
          <div className="flex items-center gap-2 rounded-full bg-danger/15 px-2.5 py-1 ring-1 ring-danger/30">
            <span className="size-2 rounded-full bg-danger pulse-dot" />
            <span className="text-xs font-semibold tracking-wide text-danger">LIVE</span>
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

        <div className="flex items-center justify-between border-t border-border px-5 py-3">
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

      {/* Pipeline Source Controls + Event Feed (right column) */}
      <div className="flex flex-col gap-4">
        <PipelineControls onSourceChange={setSourcePreset} />
        <EventFeed
          events={events ?? []}
          loading={eventsLoading && !events}
          maxItems={30}
        />
      </div>
    </div>
  );
}

export default LiveMonitoringView;
