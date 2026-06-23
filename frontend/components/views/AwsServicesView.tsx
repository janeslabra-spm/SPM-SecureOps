"use client";

import { Server, HardDrive, Sparkles, Activity, Cctv, Cpu, Database, Cloud, Trash2, type LucideIcon } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { GovernanceBadges } from "@/components/widgets/GovernanceBadges";

const icons: Record<string, LucideIcon> = {
  EC2: Server,
  S3: HardDrive,
  "Amazon Bedrock": Sparkles,
  CloudWatch: Activity,
};

const awsServices = [
  { name: "EC2", role: "Application Deployment", uptime: "99.98%", region: "us-east-1" },
  { name: "S3", role: "Evidence Storage", uptime: "99.99%", region: "us-east-1" },
  { name: "Amazon Bedrock", role: "AI Compliance Assistant", uptime: "99.95%", region: "us-east-1" },
  { name: "CloudWatch", role: "System Monitoring", uptime: "100%", region: "us-east-1" },
];

const systems = [
  { icon: Cctv, name: "Camera Feed", status: "Active", detail: "Production Camera 01 · 1080p · 30fps", health: 99 },
  { icon: Cpu, name: "AI Detection Engine", status: "YOLOv8 Online", detail: "Inference latency 42ms", health: 97 },
  { icon: Server, name: "Backend API", status: "Connected", detail: "Avg response 118ms", health: 99 },
  { icon: Database, name: "Database", status: "PostgreSQL Active", detail: "Connections 24 / 100", health: 96 },
  { icon: Cloud, name: "AWS Services", status: "Connected", detail: "4 services operational", health: 100 },
  { icon: Trash2, name: "Retention Policy", status: "7 Day Auto Delete", detail: "Next purge in 18h", health: 100 },
];

export function AwsServicesView() {
  return (
    <div data-testid="view-aws" className="flex flex-col gap-4">
      {/* AWS Cards */}
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
          {awsServices.map((s) => {
            const Icon = icons[s.name] ?? Server;
            return (
              <div key={s.name} className="flex items-center gap-3 rounded-xl border border-border bg-card/50 p-4 transition-colors hover:border-primary/30">
                <div className="grid size-10 place-items-center rounded-lg bg-primary/12 text-primary">
                  <Icon className="size-5" />
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
            );
          })}
        </div>
      </section>

      {/* System Status */}
      <section className="glass rounded-2xl p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold">System Status</h2>
            <p className="text-xs text-muted-foreground">Component health overview</p>
          </div>
          <span className="flex items-center gap-1.5 rounded-full bg-success/12 px-2.5 py-1 text-xs font-medium text-success ring-1 ring-success/25">
            <span className="size-1.5 rounded-full bg-success pulse-dot" />
            Operational
          </span>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {systems.map(({ icon: Icon, name, status, detail, health }) => (
            <div key={name} className="rounded-xl border border-border bg-card/50 p-4">
              <div className="flex items-center gap-3">
                <div className="grid size-9 place-items-center rounded-lg bg-primary/12 text-primary">
                  <Icon className="size-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold">{name}</p>
                  <p className="truncate text-xs text-muted-foreground">{detail}</p>
                </div>
                <span className="text-xs font-medium text-success">{status}</span>
              </div>
              <div className="mt-3 flex items-center gap-3">
                <div className="h-2 flex-1 rounded-full bg-muted overflow-hidden">
                  <div className="h-full rounded-full bg-success transition-all" style={{ width: `${health}%` }} />
                </div>
                <span className="w-9 text-right text-xs tabular-nums text-muted-foreground">{health}%</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <GovernanceBadges />
    </div>
  );
}

export default AwsServicesView;
