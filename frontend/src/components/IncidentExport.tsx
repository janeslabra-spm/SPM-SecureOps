/**
 * IncidentExport component - provides a CSV export button that downloads
 * filtered incident data from the backend export endpoint.
 */

interface IncidentExportProps {
  startDate?: string;
  endDate?: string;
  incidentType?: string;
  status?: string;
}

function IncidentExport({ startDate, endDate, incidentType, status }: IncidentExportProps) {
  const handleExport = () => {
    const params = new URLSearchParams();

    if (startDate) {
      params.append('start_date', startDate);
    }
    if (endDate) {
      params.append('end_date', endDate);
    }
    if (incidentType) {
      params.append('incident_type', incidentType);
    }
    if (status) {
      params.append('status', status);
    }

    const queryString = params.toString();
    const exportUrl = `http://localhost:8000/incidents/export${queryString ? `?${queryString}` : ''}`;

    const link = document.createElement('a');
    link.href = exportUrl;
    link.download = 'incidents_export.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <button
      className="flex items-center gap-2 px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-light transition-colors"
      onClick={handleExport}
      aria-label="Export incidents as CSV"
    >
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
        <polyline points="7 10 12 15 17 10" />
        <line x1="12" y1="15" x2="12" y2="3" />
      </svg>
      Export CSV
    </button>
  );
}

export default IncidentExport;
