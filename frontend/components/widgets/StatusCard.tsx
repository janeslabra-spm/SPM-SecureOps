"use client";

import { type LucideIcon, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StatusCardProps {
  title: string;
  value: number;
  icon: LucideIcon;
  trend?: "up" | "down" | "neutral";
}

/**
 * StatusCard — Glass-morphism metric card displaying a title, numeric value,
 * icon, and optional trend indicator.
 *
 * Used in the Dashboard, Compliance Events, and System Status views to show
 * metrics like "Total Events Today", "Pending Reviews", "Confirmed Violations",
 * and "False Positives".
 *
 * Validates: Requirements 3.2, 3.3, 12.3
 */
export function StatusCard({ title, value, icon: Icon, trend }: StatusCardProps) {
  // Clamp value to displayable range 0–99,999
  const displayValue = Math.min(Math.max(Math.round(value), 0), 99_999).toLocaleString();

  return (
    <div className="glass-card p-5 flex items-center gap-4 transition-colors">
      {/* Icon container */}
      <div className="flex-shrink-0 flex items-center justify-center w-11 h-11 rounded-full bg-muted/50 border border-border/50">
        <Icon className="w-5 h-5 text-muted-foreground" aria-hidden="true" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-2xl font-bold tracking-tight text-foreground">
          {displayValue}
        </p>
        <p className="text-sm text-muted-foreground truncate">{title}</p>
      </div>

      {/* Trend indicator */}
      {trend && (
        <div
          className={cn(
            "flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full",
            trend === "up" && "text-green-400 bg-green-500/10",
            trend === "down" && "text-red-400 bg-red-500/10",
            trend === "neutral" && "text-muted-foreground bg-muted/50"
          )}
          aria-label={`Trend: ${trend}`}
        >
          {trend === "up" && <TrendingUp className="w-4 h-4" />}
          {trend === "down" && <TrendingDown className="w-4 h-4" />}
          {trend === "neutral" && <Minus className="w-4 h-4" />}
        </div>
      )}
    </div>
  );
}
