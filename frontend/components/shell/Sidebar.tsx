"use client";

import {
  LayoutDashboard,
  Cctv,
  ShieldAlert,
  ClipboardCheck,
  BarChart3,
  Cloud,
  Activity,
  Settings,
  ChevronLeft,
  ShieldCheck,
} from "lucide-react";
import type { ViewKey } from "@/lib/constants";
import { cn } from "@/lib/utils";

const nav: { key: ViewKey; label: string; icon: typeof LayoutDashboard }[] = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "live", label: "Live Monitoring", icon: Cctv },
  { key: "events", label: "Compliance Events", icon: ShieldAlert },
  { key: "review", label: "Compliance Review", icon: ClipboardCheck },
  { key: "analytics", label: "Analytics", icon: BarChart3 },
  { key: "aws", label: "AWS Services", icon: Cloud },
  { key: "status", label: "System Status", icon: Activity },
  { key: "settings", label: "Settings", icon: Settings },
];

export interface SidebarProps {
  active: ViewKey;
  onSelect: (k: ViewKey) => void;
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ active, onSelect, collapsed, onToggle }: SidebarProps) {
  return (
    <aside
      className={cn(
        "sticky top-0 z-30 hidden h-screen shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-all duration-300 md:flex",
        collapsed ? "w-[76px]" : "w-64",
      )}
    >
      {/* Branding */}
      <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-4">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/15 ring-1 ring-primary/30">
          <ShieldCheck className="size-5 text-primary" />
        </div>
        {!collapsed && (
          <div className="min-w-0 leading-tight">
            <p className="truncate text-sm font-semibold text-sidebar-foreground">
              SPM SecureOps
            </p>
            <p className="truncate text-xs text-muted-foreground">Monitoring</p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
        {nav.map(({ key, label, icon: Icon }) => {
          const isActive = active === key;
          return (
            <button
              key={key}
              onClick={() => onSelect(key)}
              title={collapsed ? label : undefined}
              className={cn(
                "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-sidebar-primary/15 text-sidebar-foreground ring-1 ring-sidebar-primary/30"
                  : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-foreground",
              )}
            >
              <Icon
                className={cn(
                  "size-5 shrink-0",
                  isActive ? "text-primary" : "text-muted-foreground group-hover:text-sidebar-foreground",
                )}
              />
              {!collapsed && <span className="truncate">{label}</span>}
              {isActive && !collapsed && (
                <span className="ml-auto size-1.5 rounded-full bg-primary" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Collapse */}
      <div className="border-t border-sidebar-border p-3">
        <button
          onClick={onToggle}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
        >
          <ChevronLeft
            className={cn("size-5 shrink-0 transition-transform", collapsed && "rotate-180")}
          />
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;
