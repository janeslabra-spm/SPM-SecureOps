import { useState, useEffect, useMemo, useCallback } from "react";
import api from "../services/api";
import IncidentExport from "../components/IncidentExport";

interface Incident {
  incident_id: number;
  timestamp: string;
  incident_type: string;
  confidence: number;
  camera_name: string;
  location: string;
  screenshot_path: string;
  status: string;
  notes: string;
}

const INCIDENT_TYPES = ["PHONE_ON_TABLE", "PHONE_NEAR_PERSON", "DOCUMENT_LEFT_ON_DESK"];
const STATUS_VALUES = ["Pending Review", "Confirmed", "False Alarm"];
const PAGE_SIZE = 20;

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [filterType, setFilterType] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  const fetchIncidents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      if (filterType) params.incident_type = filterType;
      if (filterStatus) params.status = filterStatus;

      const response = await api.get<Incident[]>("/incidents", { params });
      setIncidents(response.data);
      setCurrentPage(1);
    } catch (err) {
      setError("Failed to fetch incidents. Please try again.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate, filterType, filterStatus]);

  useEffect(() => {
    fetchIncidents();
  }, [fetchIncidents]);

  const totalPages = Math.max(1, Math.ceil(incidents.length / PAGE_SIZE));
  const paginatedIncidents = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return incidents.slice(start, start + PAGE_SIZE);
  }, [incidents, currentPage]);

  const handleStatusUpdate = async (incidentId: number, newStatus: string) => {
    setUpdatingId(incidentId);
    try {
      const response = await api.patch<Incident>(`/incidents/${incidentId}/status`, {
        status: newStatus,
      });
      setIncidents((prev) =>
        prev.map((inc) =>
          inc.incident_id === incidentId ? { ...inc, ...response.data } : inc
        )
      );
    } catch (err) {
      console.error("Failed to update status:", err);
    } finally {
      setUpdatingId(null);
    }
  };

  const formatTimestamp = (ts: string) => {
    const date = new Date(ts);
    return date.toLocaleString();
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "Confirmed":
        return "bg-danger/10 text-danger";
      case "False Alarm":
        return "bg-text-muted/10 text-text-muted";
      default:
        return "bg-warning/10 text-warning";
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-text-primary">Incident Review</h2>
          <p className="text-sm text-text-muted mt-0.5">{incidents.length} total incidents</p>
        </div>
        <IncidentExport
          startDate={startDate}
          endDate={endDate}
          incidentType={filterType}
          status={filterStatus}
        />
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
          <label className="text-xs font-medium text-text-secondary">Incident Type</label>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-3 py-2 bg-bg-page border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-primary-lighter focus:ring-1 focus:ring-primary-lighter/20"
          >
            <option value="">All Types</option>
            {INCIDENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {type.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-text-secondary">Status</label>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-3 py-2 bg-bg-page border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-primary-lighter focus:ring-1 focus:ring-primary-lighter/20"
          >
            <option value="">All Statuses</option>
            {STATUS_VALUES.map((s) => (
              <option key={s} value={s}>
                {s}
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
            Loading incidents...
          </div>
        </div>
      )}

      {/* Table */}
      {!loading && (
        <div className="bg-bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-bg-page/50">
                <th className="px-5 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wide">
                  Time
                </th>
                <th className="px-5 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wide">
                  Type
                </th>
                <th className="px-5 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wide">
                  Confidence
                </th>
                <th className="px-5 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wide">
                  Status
                </th>
                <th className="px-5 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wide">
                  Action
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-light">
              {paginatedIncidents.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-12 text-center text-text-muted">
                    No incidents found.
                  </td>
                </tr>
              ) : (
                paginatedIncidents.map((incident) => (
                  <tr
                    key={incident.incident_id}
                    className="hover:bg-bg-hover/50 transition-colors"
                  >
                    <td className="px-5 py-4 text-text-primary whitespace-nowrap">
                      {formatTimestamp(incident.timestamp)}
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-md bg-primary/10 flex items-center justify-center">
                          <svg className="w-3 h-3 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
                            <line x1="12" y1="18" x2="12.01" y2="18" />
                          </svg>
                        </div>
                        <span className="text-text-primary">
                          {incident.incident_type.replace(/_/g, " ")}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-4 text-text-primary font-medium">
                      {(incident.confidence * 100).toFixed(1)}%
                    </td>
                    <td className="px-5 py-4">
                      <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${getStatusBadge(incident.status)}`}>
                        {incident.status}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <select
                        value={incident.status}
                        onChange={(e) =>
                          handleStatusUpdate(incident.incident_id, e.target.value)
                        }
                        disabled={updatingId === incident.incident_id}
                        className="px-2 py-1.5 bg-bg-page border border-border rounded-lg text-text-primary text-xs focus:outline-none focus:border-primary-lighter disabled:opacity-50"
                      >
                        {STATUS_VALUES.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {!loading && incidents.length > 0 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-muted">
            Showing {(currentPage - 1) * PAGE_SIZE + 1}–
            {Math.min(currentPage * PAGE_SIZE, incidents.length)} of{" "}
            {incidents.length}
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
