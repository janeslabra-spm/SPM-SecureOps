"use client";

import { ShieldCheck, Lock } from "lucide-react";
import { cn } from "@/lib/utils";

const controls = [
  "Human Review Required",
  "No Facial Recognition",
  "No Biometric Identification",
  "No Continuous Video Recording",
  "Only Event Evidence Stored",
  "Local Processing Supported",
  "Automatic 7 Day Evidence Retention",
  "Authorized Access Required",
  "Audit Logging Enabled",
];

export function GovernanceBadges({ className }: { className?: string }) {
  return (
    <section className={cn("glass rounded-2xl p-5", className)} data-testid="governance-badges">
      <div className="mb-4 flex items-center gap-2.5">
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

      <div className="flex flex-wrap gap-2">
        {controls.map((c) => (
          <span
            key={c}
            className="inline-flex items-center gap-1.5 rounded-full border border-success/25 bg-success/8 px-3 py-1.5 text-xs font-medium text-foreground"
            data-testid="governance-badge"
          >
            <ShieldCheck className="size-3.5 text-success" />
            {c}
          </span>
        ))}
      </div>
    </section>
  );
}

export default GovernanceBadges;
