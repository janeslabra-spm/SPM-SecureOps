import { useState, useEffect, useCallback, useMemo } from "react";
import api from "../services/api";

interface AuditLog {
  log_id: number;
  timestamp: string;
  event_type: string;
  description: string;
  actor: string;
  metadata_json: string;
}

const EVENT_TYPES = ["status_change", "system_start", "detection", "config_change"];
const PAGE_SIZE = 20;

function getEventIcon(eventType: string) {
  switch (eventType) {
    case "status_change":
      return (
        <div className="w-8 h-8 rounded-full bg-info/10 flex items-center justify-center">
          <svg className="w-4 h-4 text-info" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="9 11 12 14 22 4" />
            <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
          </svg>
        </div>
      );
    case "system_start":
      return (
        <div className="w-8 h-8 rounded-full bg-success/10 flex items-center justify-center">
          <svg className="w-4 h-4 text-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18.36 6.64a9 9 0 11-12.73 0" />
            <line x1="12" y1="2" x2="12" y2="12" />
          </svg>
        </div>
      );
    case "detection":
      return (
        <div className="w-8 h-8 rounded-full bg-warning/10 flex items-center justify-center">
          <svg className="w-4 h-4 text-warning" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        </div>
      );
    case "config_change":
      return (
        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
          <svg className="w-4 h-4 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68 1.65 1.65 0 0010 3.17V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
          </svg>
        </div>
      );
    default:
      return (
        <div className="w-8 h-8 rounded-full bg-bg-page flex items-center justify-center">
          <svg className="w-4 h-4 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
        </div>
      );
  }
}

function getEventBadgeColor(eventType: string) {
  switch (eventType) {
    case "status_change": return "bg-info/10 text-info";
    case "system_start": return "bg-success/10 text-success";
    case "detection": return "bg-warning/10 text-warning";
    case "config_change": return "bg-primary/10 text-primary";
    default: return "bg-text-muted/10 text-text-muted";
  }
}

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [filterType, setFilterType] = useState("");
  const [currentPage, setCurrentPage] = useState(1);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      if (filterType) params.event_type = filterType;

      const response = await api.get<AuditLog[]>("/audit", { params });
      setLogs(response.data);
      setCurrentPage(1);
    } catch (err) {
      setError("Failed to fetch audit logs. Make sure the backend is running.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate, filterType]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const totalPages = Math.max(1, Math.ceil(logs.length / PAGE_SIZE));
  const paginatedLogs = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return logs.slice(start, start + PAGE_SIZE);
  }, [logs, currentPage]);

  const formatTimestamp = (ts: string) => {
    const date = new Date(ts);
    return date.toLocaleString();
  };

  const formatRelativeTime = (ts: string) => {
    const now = new Date();
    const date = new Date(ts);
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffMin < 1) return "Just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHour < 24) return `${diffHour}h ago`;
    return `${diffDay}d ago`;
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-text-primary">Audit Logs</h2>
          <p className="text-sm text-text-muted mt-0.5">
            System event history and compliance audit trail
          </p>
        </div>
        <button
          onClick={fetchLogs}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-light transition-colors"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="23 4 23 10 17 10" />
            <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10" />
          </svg>
          Refresh
        </button>
      </div>

      {/* Filter Controls */}
      <div className="flex flex-wrap gap-4 items-end bg-bg-card p-5 rounded-xl border border-border shadow-sm">
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-text-secondary">Start Date</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="px-3 py-2 bg-bg-page border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-primary-lighter focus:ring-1 focus:ring-primary-lighter/20"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-text-secondary">End Date</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="px-3 py-2 bg-bg-page border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-primary-lighter focus:ring-1 focus:ring-primary-lighter/20"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-text-secondary">Event Type</label>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-3 py-2 bg-bg-page border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-primary-lighter focus:ring-1 focus:ring-primary-lighter/20"
          >
            <option value="">All Events</option>
            {EVENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {type.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-danger/5 border border-danger/20 rounded-xl text-danger text-sm flex items-center gap-2">
          <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="text-center py-12 text-text-muted">
          <div className="inline-flex items-center gap-2">
            <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Loading audit logs...
          </div>
        </div>
      )}

      {/* Audit log entries */}
      {!loading && !error && (
        <div className="bg-bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          {paginatedLogs.length === 0 ? (
            <div className="p-12 text-center">
              <div className="w-16 h-16 rounded-full bg-bg-page flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2" />
                  <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
                </svg>
              </div>
              <p className="text-text-muted text-sm">No audit logs found for the selected filters.</p>
            </div>
          ) : (
            <div className="divide-y divide-border-light">
              {paginatedLogs.map((log) => (
                <div
                  key={log.log_id}
                  className="flex items-start gap-4 px-5 py-4 hover:bg-bg-hover/50 transition-colors"
                >
                  {/* Event icon */}
                  {getEventIcon(log.event_type)}

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${getEventBadgeColor(log.event_type)}`}>
                        {log.event_type.replace(/_/g, " ")}
                      </span>
                      <span className="text-xs text-text-muted">
                        by {log.actor}
                      </span>
                    </div>
                    <p className="text-sm text-text-primary">{log.description}</p>
                    {log.metadata_json && log.metadata_json !== "{}" && (
                      <p className="text-xs text-text-muted mt-1 font-mono">
                        {log.metadata_json.length > 100
                          ? log.metadata_json.substring(0, 100) + "..."
                          : log.metadata_json}
                      </p>
                    )}
                  </div>

                  {/* Timestamp */}
                  <div className="text-right flex-shrink-0">
                    <div className="text-xs text-text-muted">{formatRelativeTime(log.timestamp)}</div>
                    <div className="text-xs text-text-muted mt-0.5">{formatTimestamp(log.timestamp)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Pagination */}
      {!loading && logs.length > PAGE_SIZE && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-muted">
            Showing {(currentPage - 1) * PAGE_SIZE + 1}–
            {Math.min(currentPage * PAGE_SIZE, logs.length)} of {logs.length}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-3 py-1.5 bg-bg-card border border-border rounded-lg text-text-primary text-sm hover:bg-bg-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Previous
            </button>
            <span className="text-sm text-text-secondary px-2">
              {currentPage} / {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-3 py-1.5 bg-bg-card border border-border rounded-lg text-text-primary text-sm hover:bg-bg-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
