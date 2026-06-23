"use client";

import { ShieldCheck, Lock, Eye, Fingerprint, Video, HardDrive, MapPin, Clock, KeyRound, FileText, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface GovernanceControl {
  label: string;
  icon: LucideIcon;
  category: "privacy" | "data" | "access";
}

const controls: GovernanceControl[] = [
  { label: "Human Review Required", icon: Eye, category: "access" },
  { label: "No Facial Recognition", icon: Fingerprint, category: "privacy" },
  { label: "No Biometric Identification", icon: Fingerprint, category: "privacy" },
  { label: "No Continuous Video Recording", icon: Video, category: "privacy" },
  { label: "Only Event Evidence Stored", icon: HardDrive, category: "data" },
  { label: "Local Processing Supported", icon: MapPin, category: "data" },
  { label: "Automatic 7 Day Evidence Retention", icon: Clock, category: "data" },
  { label: "Authorized Access Required", icon: KeyRound, category: "access" },
  { label: "Audit Logging Enabled", icon: FileText, category: "access" },
];

const categoryStyles = {
  privacy: { border: "border-info/25", bg: "bg-info/8", iconColor: "text-info" },
  data: { border: "border-warning/25", bg: "bg-warning/8", iconColor: "text-warning" },
  access: { border: "border-success/25", bg: "bg-success/8", iconColor: "text-success" },
} as const satisfies Record<GovernanceControl["category"], { border: string; bg: string; iconColor: string }>;

export function GovernanceBadges({ className }: { className?: string }) {
  return (
    <section className={cn("glass rounded-2xl p-5", className)} data-testid="governance-badges">
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="grid size-9 place-items-center rounded-lg bg-success/12 text-success ring-1 ring-success/25">
            <Lock className="size-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">Data Governance and Privacy Controls</h2>
            <p className="text-xs text-muted-foreground">
              Compliance-first monitoring safeguards
            </p>
          </div>
        </div>
        <span className="flex items-center gap-1.5 rounded-full bg-success/12 px-2.5 py-1 text-xs font-medium text-success ring-1 ring-success/25">
          <ShieldCheck className="size-3.5" />
          All Active
        </span>
      </div>

      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
        {controls.map((c) => {
          const Icon = c.icon;
          const style = categoryStyles[c.category];
          return (
            <div
              key={c.label}
              className={cn(
                "flex items-center gap-3 rounded-xl border p-3 transition-colors hover:border-primary/20",
                style.border,
                style.bg,
              )}
              data-testid="governance-badge"
            >
              <div className={cn("grid size-8 shrink-0 place-items-center rounded-lg bg-background/60", style.iconColor)}>
                <Icon className="size-4" />
              </div>
              <span className="text-xs font-medium leading-tight text-foreground">
                {c.label}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default GovernanceBadges;
