"use client";

import { cn } from "@/lib/utils";

export interface HealthProgressBarProps {
  label: string;
  value: number; // 0-100
  status: "healthy" | "warning" | "critical" | "unreachable";
}

/**
 * Returns the Tailwind color class for the progress bar fill based on the health value.
 *
 * - Green (bg-green-500): value > 90%
 * - Amber (bg-amber-500): 70% <= value <= 90%
 * - Red (bg-red-500): value < 70%
 */
export function getHealthColor(value: number): string {
  if (value > 90) return "bg-green-500";
  if (value >= 70) return "bg-amber-500";
  return "bg-red-500";
}

/**
 * HealthProgressBar — Color-coded health indicator for system components.
 *
 * Displays a labeled progress bar filled to the given percentage with
 * color thresholds: green (>90%), amber (70-90%), red (<70%).
 * Shows an "Unreachable" label when the component is at 0%.
 *
 * Validates: Requirements 9.2, 9.3
 */
export function HealthProgressBar({ label, value, status }: HealthProgressBarProps) {
  // Clamp value to 0-100
  const clampedValue = Math.min(Math.max(Math.round(value), 0), 100);
  const colorClass = getHealthColor(clampedValue);
  const isUnreachable = clampedValue === 0;

  return (
    <div className="glass-card p-4 flex flex-col gap-2">
      {/* Header: label + value/status */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{label}</span>
        <span
          className={cn(
            "text-xs font-medium",
            isUnreachable
              ? "text-red-400"
              : clampedValue > 90
                ? "text-green-400"
                : clampedValue >= 70
                  ? "text-amber-400"
                  : "text-red-400"
          )}
        >
          {isUnreachable ? "Unreachable" : `${clampedValue}%`}
        </span>
      </div>

      {/* Progress bar track */}
      <div
        className="h-2.5 w-full rounded-full bg-muted overflow-hidden"
        role="progressbar"
        aria-valuenow={clampedValue}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label} health: ${isUnreachable ? "Unreachable" : `${clampedValue}%`}`}
      >
        {/* Progress bar fill */}
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500 ease-out",
            colorClass
          )}
          style={{ width: `${clampedValue}%` }}
        />
      </div>

      {/* Unreachable indicator */}
      {isUnreachable && (
        <p className="text-xs text-red-400/80 mt-0.5">
          Component is not responding
        </p>
      )}
    </div>
  );
}
