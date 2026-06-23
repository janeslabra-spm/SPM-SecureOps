"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { GovernanceBadges } from "@/components/widgets/GovernanceBadges";

function Toggle({ defaultOn }: { defaultOn?: boolean }) {
  const [on, setOn] = useState(!!defaultOn);
  return (
    <button
      role="switch"
      aria-checked={on}
      onClick={() => setOn((v) => !v)}
      className={cn(
        "relative h-6 w-11 shrink-0 rounded-full transition-colors",
        on ? "bg-primary" : "bg-muted",
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 size-5 rounded-full bg-foreground transition-transform",
          on ? "translate-x-[22px]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

const monitoringSettings = [
  { label: "Real-time detection overlays", desc: "Show bounding boxes on live feed", on: true },
  { label: "Animated incoming events", desc: "Slide new events into the feed", on: true },
  { label: "AI Compliance Assistant", desc: "Amazon Bedrock advisory summaries", on: true },
  { label: "Email digest", desc: "Daily summary to compliance leads", on: false },
];

const governanceSettings = [
  { label: "Human review required", desc: "All events require manual confirmation", on: true },
  { label: "Local processing", desc: "Process detections on-premise", on: true },
  { label: "Audit logging", desc: "Record all reviewer actions", on: true },
];

export function SettingsView() {
  return (
    <div data-testid="view-settings" className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Monitored Area */}
        <section className="glass rounded-2xl p-5">
          <h2 className="text-sm font-semibold">Monitored Area</h2>
          <p className="mb-4 text-xs text-muted-foreground">General configuration</p>
          <div className="flex flex-col gap-3">
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-muted-foreground">Area name</span>
              <Input defaultValue="Production Floor A" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-muted-foreground">Camera source</span>
              <Input defaultValue="Production Camera 01" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-muted-foreground">Evidence retention (days)</span>
              <Input type="number" defaultValue={7} />
            </label>
          </div>
        </section>

        {/* Monitoring Preferences */}
        <section className="glass rounded-2xl p-5">
          <h2 className="text-sm font-semibold">Monitoring Preferences</h2>
          <p className="mb-4 text-xs text-muted-foreground">Detection and notifications</p>
          <ul className="flex flex-col gap-1">
            {monitoringSettings.map((s) => (
              <li key={s.label} className="flex items-center justify-between gap-3 rounded-lg px-1 py-2.5">
                <div>
                  <p className="text-sm font-medium">{s.label}</p>
                  <p className="text-xs text-muted-foreground">{s.desc}</p>
                </div>
                <Toggle defaultOn={s.on} />
              </li>
            ))}
          </ul>
        </section>

        {/* Governance Controls */}
        <section className="glass rounded-2xl p-5 lg:col-span-2">
          <h2 className="text-sm font-semibold">Governance Controls</h2>
          <p className="mb-4 text-xs text-muted-foreground">Privacy safeguards enforced across the platform</p>
          <ul className="grid grid-cols-1 gap-1 md:grid-cols-3">
            {governanceSettings.map((s) => (
              <li key={s.label} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card/50 px-3 py-2.5">
                <div>
                  <p className="text-sm font-medium">{s.label}</p>
                  <p className="text-xs text-muted-foreground">{s.desc}</p>
                </div>
                <Toggle defaultOn={s.on} />
              </li>
            ))}
          </ul>
        </section>
      </div>

      <GovernanceBadges />
    </div>
  );
}

export default SettingsView;
