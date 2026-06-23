"use client";

import { useState } from "react";
import type { ViewKey } from "@/lib/constants";
import { useConnectionStatus } from "@/hooks/useConnectionStatus";
import { Sidebar } from "@/components/shell/Sidebar";
import { Topbar } from "@/components/shell/Topbar";
import { DashboardView } from "@/components/views/DashboardView";
import { ComplianceEventsView } from "@/components/views/ComplianceEventsView";
import { ComplianceReviewView } from "@/components/views/ComplianceReviewView";
import { LiveMonitoringView } from "@/components/views/LiveMonitoringView";
import { AnalyticsView } from "@/components/views/AnalyticsView";
import { SettingsView } from "@/components/views/SettingsView";
import { AwsServicesView } from "@/components/views/AwsServicesView";
import { SystemStatusView } from "@/components/views/SystemStatusView";

const meta: Record<ViewKey, { title: string; subtitle: string }> = {
  dashboard: {
    title: "Compliance Monitoring Dashboard",
    subtitle: "Real-time visibility across monitored workspaces",
  },
  live: { title: "Live Monitoring", subtitle: "Active camera feed and AI detection overlay" },
  events: { title: "Compliance Events", subtitle: "Incoming events awaiting review" },
  review: { title: "Compliance Review", subtitle: "Structured review and resolution workflow" },
  analytics: { title: "Analytics", subtitle: "Compliance monitoring trends and distribution" },
  aws: { title: "AWS Services", subtitle: "Cloud service integration and health" },
  status: { title: "System Status", subtitle: "Component health across the platform" },
  settings: { title: "Settings", subtitle: "Configuration and governance controls" },
};

export function Shell() {
  const [view, setView] = useState<ViewKey>("dashboard");
  const [collapsed, setCollapsed] = useState(false);
  const { connected: backendConnected } = useConnectionStatus();

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar
        active={view}
        onSelect={setView}
        collapsed={collapsed}
        onToggle={() => setCollapsed((v) => !v)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          onMenu={() => setCollapsed((v) => !v)}
          connectionError={!backendConnected}
        />

        <main className="flex-1 overflow-auto p-4 md:p-6" id="main-content">
          <div className="mb-5">
            <h1 className="text-xl font-semibold tracking-tight text-balance md:text-2xl">
              {meta[view].title}
            </h1>
            <p className="mt-0.5 text-sm text-muted-foreground">{meta[view].subtitle}</p>
          </div>

          <ViewContent activeView={view} />
        </main>
      </div>
    </div>
  );
}

function ViewContent({ activeView }: { activeView: ViewKey }) {
  switch (activeView) {
    case "dashboard":
      return <DashboardView />;
    case "live":
      return <LiveMonitoringView />;
    case "events":
      return <ComplianceEventsView />;
    case "review":
      return <ComplianceReviewView />;
    case "analytics":
      return <AnalyticsView />;
    case "aws":
      return <AwsServicesView />;
    case "status":
      return <SystemStatusView />;
    case "settings":
      return <SettingsView />;
    default:
      return <DashboardView />;
  }
}

export default Shell;
