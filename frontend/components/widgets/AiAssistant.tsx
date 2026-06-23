"use client";

import { Sparkles, FileSearch, AlertCircle, ListChecks } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ComplianceEvent } from "@/lib/types";
import type { ViewKey } from "@/lib/constants";

export interface AiAssistantProps {
  events: ComplianceEvent[];
  viewContext: ViewKey;
  className?: string;
}

const rows = [
  {
    icon: FileSearch,
    label: "Event Summary",
    value: "Mobile device detected inside monitored restricted workspace",
  },
  {
    icon: AlertCircle,
    label: "Review Priority",
    value: "Needs Review",
    accent: true,
  },
  {
    icon: AlertCircle,
    label: "Possible Policy Concern",
    value: "Restricted-area mobile device presence may require supervisor verification",
  },
  {
    icon: ListChecks,
    label: "Suggested Follow-up",
    value: "Review captured evidence and confirm whether approved exception exists",
  },
];

/**
 * AiAssistant — Bedrock AI advisory panel showing structured compliance analysis.
 */
export function AiAssistant({ events, viewContext, className }: AiAssistantProps) {
  return (
    <section className={cn("glass flex flex-col rounded-2xl p-5", className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="grid size-9 place-items-center rounded-lg bg-primary/15 text-primary ring-1 ring-primary/30">
            <Sparkles className="size-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">AI Compliance Assistant</h2>
            <p className="text-xs text-muted-foreground">Advisory analysis only</p>
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-3">
        {rows.map(({ icon: Icon, label, value, accent }) => (
          <div
            key={label}
            className="rounded-xl border border-border bg-card/50 p-3.5"
          >
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <Icon className="size-3.5" />
              {label}
            </div>
            <p
              className={cn(
                "mt-1.5 text-sm leading-relaxed",
                accent ? "font-semibold text-warning" : "text-foreground",
              )}
            >
              {value}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-4 flex items-center gap-2 self-start rounded-full border border-border bg-card px-3 py-1.5">
        <span className="size-2 rounded-full bg-primary pulse-dot" />
        <span className="text-xs font-medium text-muted-foreground">
          Powered by Amazon Bedrock
        </span>
      </div>
    </section>
  );
}

export default AiAssistant;
