"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";
import type { ComplianceEvent } from "@/lib/types";

export interface ComplianceScoreProps {
  events: ComplianceEvent[];
  className?: string;
}

export function calculateComplianceScore(events: ComplianceEvent[]): number {
  if (events.length === 0) return 0;
  const nonPendingCount = events.filter((e) => e.status !== "Pending Review").length;
  return (nonPendingCount / events.length) * 100;
}

export function ComplianceScore({ events, className }: ComplianceScoreProps) {
  const score = Math.round(calculateComplianceScore(events));

  const stats = useMemo(() => {
    const now = new Date();
    const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const todayEvents = events.filter((e) => new Date(e.timestamp) >= startOfDay);
    return {
      today: todayEvents.length,
      pending: events.filter((e) => e.status === "Pending Review").length,
      reviewed: events.filter((e) => e.status !== "Pending Review").length,
      falsePositives: events.filter((e) => e.status === "False Positive").length,
    };
  }, [events]);

  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const metrics = [
    { label: "Today Compliance Events", value: String(stats.today), tone: "text-foreground" },
    { label: "Pending Reviews", value: String(stats.pending), tone: "text-warning" },
    { label: "Reviewed Events", value: String(stats.reviewed), tone: "text-success" },
    { label: "False Positives", value: String(stats.falsePositives), tone: "text-muted-foreground" },
  ];

  return (
    <section className={cn("glass flex flex-col rounded-2xl p-5", className)}>
      <h2 className="text-sm font-semibold">Compliance Monitoring Score</h2>

      <div className="mt-3 flex items-center justify-center">
        <div className="relative grid place-items-center">
          <svg width="148" height="148" className="-rotate-90">
            <circle
              cx="74"
              cy="74"
              r={radius}
              fill="none"
              strokeWidth="12"
              className="stroke-muted"
            />
            <circle
              cx="74"
              cy="74"
              r={radius}
              fill="none"
              strokeWidth="12"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              className="stroke-success transition-all"
            />
          </svg>
          <div className="absolute flex flex-col items-center">
            <span className="text-3xl font-bold tabular-nums">{score}%</span>
            <span className="text-[11px] text-muted-foreground">Score</span>
          </div>
        </div>
      </div>

      <div className="mt-2 flex items-center justify-center gap-2 rounded-full bg-success/12 px-3 py-1.5 ring-1 ring-success/25">
        <span className="size-2 rounded-full bg-success" />
        <span className="text-xs font-medium text-success">Within Monitoring Threshold</span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2.5">
        {metrics.map((m) => (
          <div key={m.label} className="rounded-xl border border-border bg-card/50 p-3">
            <p className={cn("text-2xl font-bold tabular-nums", m.tone)}>{m.value}</p>
            <p className="mt-0.5 text-[11px] leading-tight text-muted-foreground">{m.label}</p>
          </div>
        ))}
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
        Reflects monitoring compliance trends, not employee performance.
      </p>
    </section>
  );
}

export default ComplianceScore;
