"use client";

import { useCallback } from "react";

import { usePolling } from "@/hooks/usePolling";
import { useApiClient } from "@/hooks/useApiClient";
import { POLLING_INTERVALS } from "@/lib/constants";
import { mapBackendIncidents, BackendIncident } from "@/lib/incident-mapper";
import type { ComplianceEvent } from "@/lib/types";

import { SystemStatusCards } from "@/components/widgets/SystemStatusCards";
import { StreamPreview } from "@/components/widgets/StreamPreview";
import { EventFeed } from "@/components/widgets/EventFeed";
import { AiAssistant } from "@/components/widgets/AiAssistant";
import { ComplianceScore } from "@/components/widgets/ComplianceScore";
import { GovernanceBadges } from "@/components/widgets/GovernanceBadges";
import { AwsServicesView } from "@/components/views/AwsServicesView";

export function DashboardView() {
  const api = useApiClient();

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
        <div className="flex flex-col gap-4 xl:col-span-2">
          {/* Live stream */}
          <LiveMonitoringCard />

          {/* AI + Score */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <AiAssistant events={allEvents} viewContext="dashboard" />
            <ComplianceScore events={allEvents} />
          </div>
        </div>

        <EventFeed
          events={allEvents}
          loading={loading && !events}
          maxItems={20}
          className="xl:col-span-1"
        />
      </div>

      <AwsServicesSection />
      <GovernanceBadges />
    </div>
  );
}

/** Inline live monitoring card for the dashboard */
function LiveMonitoringCard() {
  return (
    <section className="glass overflow-hidden rounded-2xl">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div className="flex items-center gap-2.5">
          <div className="grid size-8 place-items-center rounded-lg bg-primary/12 text-primary">
            <svg className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-semibold">Live Compliance Monitoring</h2>
            <p className="text-xs text-muted-foreground">Real-time detection overlay</p>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-full bg-danger/15 px-2.5 py-1 ring-1 ring-danger/30">
          <span className="size-2 rounded-full bg-danger pulse-dot" />
          <span className="text-xs font-semibold tracking-wide text-danger">LIVE</span>
        </div>
      </div>

      <StreamPreview isActive={true} />

      <div className="flex items-center justify-between border-t border-border bg-gradient-to-t from-background/80 to-transparent px-5 py-3">
        <div>
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Camera Source</p>
          <p className="text-sm font-semibold">BPO Operations Floor — Camera 01</p>
        </div>
        <div className="flex items-center gap-1.5 rounded-full bg-success/20 px-2.5 py-1 ring-1 ring-success/40">
          <span className="size-3.5 text-success">🤖</span>
          <span className="text-xs font-medium text-success">AI Detection Active</span>
        </div>
      </div>
    </section>
  );
}

/** AWS services section for the dashboard */
function AwsServicesSection() {
  return (
    <section className="glass rounded-2xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold">Cloud Service Integration</h2>
          <p className="text-xs text-muted-foreground">Active AWS services</p>
        </div>
        <span className="flex items-center gap-1.5 rounded-full bg-success/12 px-2.5 py-1 text-xs font-medium text-success ring-1 ring-success/25">
          <span className="size-1.5 rounded-full bg-success pulse-dot" />
          All Operational
        </span>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {[
          { name: "EC2", role: "Application Deployment", uptime: "99.98%", region: "us-east-1" },
          { name: "S3", role: "Evidence Storage", uptime: "99.99%", region: "us-east-1" },
          { name: "Amazon Bedrock", role: "AI Compliance Assistant", uptime: "99.95%", region: "us-east-1" },
          { name: "CloudWatch", role: "System Monitoring", uptime: "100%", region: "us-east-1" },
        ].map((s) => (
          <div key={s.name} className="flex items-center gap-3 rounded-xl border border-border bg-card/50 p-4 transition-colors hover:border-primary/30">
            <div className="grid size-10 place-items-center rounded-lg bg-primary/12 text-primary">
              <svg className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 14.25h13.5m-13.5 0a3 3 0 01-3-3m3 3a3 3 0 100 6h13.5a3 3 0 100-6m-16.5-3a3 3 0 013-3h13.5a3 3 0 013 3m-19.5 0a4.5 4.5 0 01.9-2.7L5.737 5.1a3.375 3.375 0 012.7-1.35h7.126c1.062 0 2.062.5 2.7 1.35l2.587 3.45a4.5 4.5 0 01.9 2.7" />
              </svg>
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold">{s.name}</p>
                <span className="size-1.5 rounded-full bg-success" />
              </div>
              <p className="truncate text-xs text-muted-foreground">{s.role}</p>
            </div>
            <div className="text-right">
              <p className="text-xs font-medium text-success">{s.uptime}</p>
              <p className="text-[10px] text-muted-foreground">{s.region}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default DashboardView;
