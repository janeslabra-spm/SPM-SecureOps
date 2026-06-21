import { Link } from "react-router-dom";

const MAX_ENTRIES = 10;

export interface DetectionEntry {
  id: string | number;
  timestamp: string;
  incident_type: string;
  confidence: number;
}

interface DetectionFeedProps {
  entries: DetectionEntry[];
}

function formatTimestamp(ts: string): string {
  try {
    const date = new Date(ts);
    return date.toLocaleDateString([], {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return ts;
  }
}

function formatTime(ts: string): string {
  try {
    const date = new Date(ts);
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

function formatIncidentType(type: string): string {
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function getConfidenceBadge(confidence: number) {
  const percent = confidence * 100;
  if (percent >= 80) {
    return { color: "bg-danger/10 text-danger", label: "High" };
  } else if (percent >= 50) {
    return { color: "bg-warning/10 text-warning", label: "Medium" };
  }
  return { color: "bg-success/10 text-success", label: "Low" };
}

export default function DetectionFeed({ entries }: DetectionFeedProps) {
  const displayEntries = entries.slice(0, MAX_ENTRIES);

  return (
    <div className="bg-bg-card border border-border rounded-xl shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border">
        <h3 className="text-sm font-semibold text-text-primary">
          Recent Detections
        </h3>
        <Link
          to="/incidents"
          className="text-xs font-medium text-primary-lighter hover:text-primary transition-colors"
        >
          View all
        </Link>
      </div>
      
      {/* Table header */}
      <div className="grid grid-cols-[auto_1fr_auto_auto_auto] gap-4 px-5 py-3 bg-bg-page/50 border-b border-border text-xs font-medium text-text-muted uppercase tracking-wide">
        <span className="w-6">#</span>
        <span>Type</span>
        <span>Date</span>
        <span>Confidence</span>
        <span>Status</span>
      </div>

      {/* Table body */}
      <div className="divide-y divide-border-light">
        {displayEntries.length === 0 ? (
          <div className="px-5 py-8 text-center text-text-muted text-sm">
            No detections recorded yet
          </div>
        ) : (
          displayEntries.map((entry, idx) => {
            const badge = getConfidenceBadge(entry.confidence);
            return (
              <div
                key={entry.id ?? idx}
                className="grid grid-cols-[auto_1fr_auto_auto_auto] gap-4 px-5 py-3 items-center hover:bg-bg-hover/50 transition-colors"
              >
                {/* Row number */}
                <span className="w-6 text-xs text-text-muted font-medium">
                  {idx + 1}
                </span>

                {/* Type */}
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <svg className="w-3.5 h-3.5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
                      <line x1="12" y1="18" x2="12.01" y2="18" />
                    </svg>
                  </div>
                  <span className="text-sm text-text-primary truncate">
                    {formatIncidentType(entry.incident_type)}
                  </span>
                </div>

                {/* Date */}
                <div className="text-right">
                  <div className="text-xs text-text-primary">{formatTimestamp(entry.timestamp)}</div>
                  <div className="text-xs text-text-muted">{formatTime(entry.timestamp)}</div>
                </div>

                {/* Confidence */}
                <span className="text-sm font-medium text-text-primary">
                  {(entry.confidence * 100).toFixed(0)}%
                </span>

                {/* Status badge */}
                <span className={`text-xs font-medium px-2 py-1 rounded-full ${badge.color}`}>
                  {badge.label}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
