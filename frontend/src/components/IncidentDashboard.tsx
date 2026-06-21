import { useState, useEffect, useCallback } from 'react';

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

const INCIDENT_TYPES = ['all', 'PHONE_ON_TABLE', 'PHONE_NEAR_PERSON', 'DOCUMENT_LEFT_ON_DESK'];
const STATUS_OPTIONS = ['all', 'Pending Review', 'Confirmed', 'False Alarm'];
const UPDATABLE_STATUSES = ['Pending Review', 'Confirmed', 'False Alarm'];

/**
 * IncidentDashboard component - displays incident history with filtering and status management.
 * Fetches the 50 most recent incidents sorted by timestamp DESC.
 * Provides filter controls for date range, incident type, and status.
 * Allows inline status updates via PATCH request per incident row.
 */
function IncidentDashboard() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [incidentTypeFilter, setIncidentTypeFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const fetchIncidents = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      if (incidentTypeFilter !== 'all') params.append('incident_type', incidentTypeFilter);
      if (statusFilter !== 'all') params.append('status', statusFilter);

      const queryString = params.toString();
      const url = `/incidents${queryString ? `?${queryString}` : ''}`;

      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to fetch incidents: ${response.status} ${response.statusText}`);
      }

      const data: Incident[] = await response.json();
      // Display up to 50 most recent incidents (API returns sorted DESC, max 100)
      setIncidents(data.slice(0, 50));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate, incidentTypeFilter, statusFilter]);

  useEffect(() => {
    fetchIncidents();
  }, [fetchIncidents]);

  const handleStatusUpdate = async (incidentId: number, newStatus: string) => {
    try {
      const response = await fetch(`/incidents/${incidentId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });

      if (!response.ok) {
        throw new Error(`Failed to update status: ${response.status} ${response.statusText}`);
      }

      // Refresh the incident list after successful update
      await fetchIncidents();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update incident status');
    }
  };

  const formatTimestamp = (timestamp: string): string => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const formatConfidence = (confidence: number): string => {
    return `${(confidence * 100).toFixed(1)}%`;
  };

  return (
    <div className="incident-dashboard">
      <h1>Incident Dashboard</h1>

      {/* Filter Controls */}
      <div className="incident-filters">
        <div className="filter-group">
          <label htmlFor="start-date">Start Date</label>
          <input
            id="start-date"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label htmlFor="end-date">End Date</label>
          <input
            id="end-date"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label htmlFor="incident-type-filter">Incident Type</label>
          <select
            id="incident-type-filter"
            value={incidentTypeFilter}
            onChange={(e) => setIncidentTypeFilter(e.target.value)}
          >
            {INCIDENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {type === 'all' ? 'All Types' : type.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="status-filter">Status</label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>
                {status === 'all' ? 'All Statuses' : status}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Loading State */}
      {loading && <div className="loading-indicator">Loading incidents...</div>}

      {/* Error State */}
      {error && <div className="error-message">{error}</div>}

      {/* Incident Table */}
      {!loading && !error && (
        <div className="incident-table-container">
          {incidents.length === 0 ? (
            <p className="no-incidents">No incidents found matching the current filters.</p>
          ) : (
            <table className="incident-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Incident Type</th>
                  <th>Confidence</th>
                  <th>Status</th>
                  <th>Update Status</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((incident) => (
                  <tr key={incident.incident_id}>
                    <td>{formatTimestamp(incident.timestamp)}</td>
                    <td>{incident.incident_type.replace(/_/g, ' ')}</td>
                    <td>{formatConfidence(incident.confidence)}</td>
                    <td>
                      <span className={`status-badge status-${incident.status.toLowerCase().replace(/\s+/g, '-')}`}>
                        {incident.status}
                      </span>
                    </td>
                    <td>
                      <select
                        value={incident.status}
                        onChange={(e) => handleStatusUpdate(incident.incident_id, e.target.value)}
                        aria-label={`Update status for incident ${incident.incident_id}`}
                      >
                        {UPDATABLE_STATUSES.map((status) => (
                          <option key={status} value={status}>
                            {status}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

export default IncidentDashboard;
