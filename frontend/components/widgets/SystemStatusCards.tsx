"use client";

import { Cctv, Cpu, Server, Database, Cloud, Trash2, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "success" | "info" | "warning";

const cards: { icon: LucideIcon; label: string; value: string; tone: Tone }[] = [
  { icon: Cctv, label: "Camera Feed", value: "Active", tone: "success" },
  { icon: Cpu, label: "AI Detection Engine", value: "YOLOv8 Online", tone: "success" },
  { icon: Server, label: "Backend API", value: "Connected", tone: "success" },
  { icon: Database, label: "Database", value: "PostgreSQL Active", tone: "info" },
  { icon: Cloud, label: "AWS Services", value: "Connected", tone: "success" },
  { icon: Trash2, label: "Retention Policy", value: "7 Day Auto Delete", tone: "warning" },
];

const toneMap: Record<Tone, { dot: string; icon: string; text: string }> = {
  success: { dot: "bg-success", icon: "text-success bg-success/12", text: "text-success" },
  info: { dot: "bg-info", icon: "text-info bg-info/12", text: "text-info" },
  warning: { dot: "bg-warning", icon: "text-warning bg-warning/12", text: "text-warning" },
};

export function SystemStatusCards() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      {cards.map(({ icon: Icon, label, value, tone }) => {
        const t = toneMap[tone];
        return (
          <div
            key={label}
            className="glass rounded-xl p-4 transition-colors hover:border-primary/30"
          >
            <div className="flex items-center justify-between">
              <div className={cn("grid size-9 place-items-center rounded-lg", t.icon)}>
                <Icon className="size-5" />
              </div>
              <span className={cn("size-2 rounded-full pulse-dot", t.dot)} />
            </div>
            <p className="mt-3 text-xs text-muted-foreground">{label}</p>
            <p className={cn("mt-0.5 text-sm font-semibold", t.text)}>{value}</p>
          </div>
        );
      })}
    </div>
  );
}

export default SystemStatusCards;
