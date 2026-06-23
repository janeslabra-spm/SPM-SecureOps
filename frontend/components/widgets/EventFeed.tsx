"use client";

import { Smartphone, FileText, Radio } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PRIORITY_COLORS, STATUS_COLORS } from "@/lib/constants";
import type { ComplianceEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface EventFeedProps {
  events: ComplianceEvent[];
  loading: boolean;
  maxItems?: number;
  className?: string;
}

export function EventFeed({ events, loading, maxItems, className }: EventFeedProps) {
  const displayedEvents = maxItems ? events.slice(0, maxItems) : events;

  return (
    <section className={cn("glass flex flex-col rounded-2xl", className)}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div className="flex items-center gap-2.5">
          <div className="grid size-8 place-items-center rounded-lg bg-primary/12 text-primary">
            <Radio className="size-4" />
          </div>
          <h2 className="text-sm font-semibold">Live Compliance Event Feed</h2>
        </div>
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="size-1.5 rounded-full bg-success pulse-dot" />
          Live
        </span>
      </div>

      {/* Content */}
      <ScrollArea className="min-h-[300px] max-h-[520px] flex-1 px-3 py-3 xl:max-h-none xl:h-[calc(100%-65px)]">
        {loading ? (
          <div className="flex flex-col gap-2.5">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="animate-pulse rounded-xl border border-border bg-card/60 p-3.5">
                <div className="h-3 w-3/4 rounded bg-muted" />
                <div className="mt-2 h-4 w-full rounded bg-muted" />
                <div className="mt-2 flex gap-2">
                  <div className="h-5 w-20 rounded-full bg-muted" />
                  <div className="h-5 w-20 rounded-full bg-muted" />
                </div>
              </div>
            ))}
          </div>
        ) : displayedEvents.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No events to display.
          </p>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {displayedEvents.map((event, i) => (
              <EventFeedItem key={event.id} event={event} isNew={i === 0} />
            ))}
          </ul>
        )}
      </ScrollArea>
    </section>
  );
}

function EventFeedItem({ event, isNew }: { event: ComplianceEvent; isNew: boolean }) {
  const isPhoneEvent = event.eventType === "PHONE_ON_TABLE"
    || event.eventType === "PHONE_NEAR_PERSON"
    || event.eventType === "PHONE_HELD_OR_NEAR_PERSON";

  const Icon = isPhoneEvent ? Smartphone : FileText;

  const timeStr = (() => {
    try {
      const d = new Date(event.timestamp);
      if (isNaN(d.getTime())) return "";
      return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
    } catch { return ""; }
  })();

  const detail = isPhoneEvent
    ? "Mobile Device Detected in Restricted Area"
    : "Printed Material Detected in Monitoring Zone";

  return (
    <li className={cn(
      "rounded-xl border border-border bg-card/60 p-3.5",
      isNew && "animate-slide-in border-primary/30",
    )}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground">
          <Icon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Possible Compliance Event
          </p>
          <p className="mt-0.5 text-sm font-semibold leading-snug text-balance">
            {detail}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <PriorityBadge priority={event.priority} />
            <StatusBadge status={event.status} />
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
            <span className="font-mono">EVT-{String(event.id).padStart(5, "0")}</span>
            <span>{timeStr}</span>
          </div>
        </div>
      </div>
    </li>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const styles: Record<string, string> = {
    "Needs Review": "bg-warning/12 text-warning ring-warning/30",
    "High Review Priority": "bg-danger/12 text-danger ring-danger/30",
    Informational: "bg-info/12 text-info ring-info/30",
  };
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1",
      styles[priority] ?? "bg-muted text-muted-foreground ring-border",
    )}>
      <span className="size-1.5 rounded-full bg-current" />
      {priority}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    "Pending Review": "bg-muted text-muted-foreground ring-border",
    Confirmed: "bg-info/12 text-info ring-info/30",
    "False Positive": "bg-muted text-muted-foreground ring-border",
    "Warning Issued": "bg-warning/12 text-warning ring-warning/30",
    "Coaching Required": "bg-warning/12 text-warning ring-warning/30",
    Escalated: "bg-danger/12 text-danger ring-danger/30",
    Resolved: "bg-success/12 text-success ring-success/30",
  };
  return (
    <span className={cn(
      "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1",
      styles[status] ?? "bg-muted text-muted-foreground ring-border",
    )}>
      {status}
    </span>
  );
}

export default EventFeed;
