import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind CSS classes with clsx support.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format an ISO 8601 timestamp to a locale date-time string.
 */
export function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    return date.toLocaleString();
  } catch {
    return isoString;
  }
}

/**
 * Format an incident_type value by replacing underscores with spaces.
 * Example: "PHONE_ON_TABLE" → "PHONE ON TABLE"
 */
export function formatIncidentType(incidentType: string): string {
  return incidentType.replace(/_/g, " ");
}

/**
 * Capitalize the first letter of each word in a string.
 * Example: "phone on table" → "Phone On Table"
 */
export function capitalize(str: string): string {
  if (!str) return str;
  return str
    .toLowerCase()
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * Format an incident_type into a human-readable title.
 * Replaces underscores with spaces and capitalizes each word.
 * Example: "PHONE_ON_TABLE" → "Phone On Table"
 */
export function formatIncidentTitle(incidentType: string): string {
  return capitalize(formatIncidentType(incidentType));
}

/**
 * Truncate a string to a maximum length, appending an ellipsis indicator if truncated.
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "…";
}

/**
 * Format seconds into a human-readable uptime string.
 * Example: 3661 → "1h 1m 1s"
 */
export function formatUptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  const parts: string[] = [];
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  parts.push(`${secs}s`);

  return parts.join(" ");
}

/**
 * Format a number as a percentage string.
 * Example: 0.856 → "85.6%"
 */
export function formatPercentage(value: number, decimals: number = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}
