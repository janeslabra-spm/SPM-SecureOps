import { useEffect, useState, useCallback } from 'react';

interface Incident {
  incident_id: number;
  timestamp: string;
  incident_type: string;
  confidence: number;
  status: string;
}

interface Notification {
  id: number;
  incident: Incident;
  dismissedAt?: number;
}

const API_BASE = import.meta.env.VITE_API_BASE || '';

/**
 * AlertNotification component - polls for new incidents and displays toast notifications.
 * Notifications remain visible for 10 seconds or until the operator dismisses them.
 * Validates: Requirements 7.4
 */
function AlertNotification() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [lastSeenId, setLastSeenId] = useState<number>(0);

  const checkForNewIncidents = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/incidents?limit=1`);
      if (!response.ok) return;
      const data: Incident[] = await response.json();
      if (data.length > 0 && data[0].incident_id > lastSeenId) {
        const newIncident = data[0];
        setLastSeenId(newIncident.incident_id);
        if (lastSeenId > 0) {
          setNotifications((prev) => [
            ...prev,
            { id: newIncident.incident_id, incident: newIncident },
          ]);
        }
      }
    } catch {
      // Silently ignore — the global error banner handles connectivity issues
    }
  }, [lastSeenId]);

  useEffect(() => {
    const interval = setInterval(checkForNewIncidents, 5000);
    checkForNewIncidents();
    return () => clearInterval(interval);
  }, [checkForNewIncidents]);

  // Auto-dismiss notifications after 10 seconds
  useEffect(() => {
    if (notifications.length === 0) return;
    const timer = setTimeout(() => {
      setNotifications((prev) => prev.slice(1));
    }, 10000);
    return () => clearTimeout(timer);
  }, [notifications]);

  const dismiss = (id: number) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  };

  if (notifications.length === 0) return null;

  return (
    <div className="alert-notifications">
      {notifications.map((notification) => (
        <div key={notification.id} className="alert-toast">
          <div className="alert-toast-content">
            <span className="alert-toast-icon">⚠️</span>
            <div className="alert-toast-text">
              <strong>New Incident Detected</strong>
              <p>
                {notification.incident.incident_type.replace(/_/g, ' ')} —
                Confidence: {(notification.incident.confidence * 100).toFixed(0)}%
              </p>
            </div>
          </div>
          <button
            className="alert-toast-dismiss"
            onClick={() => dismiss(notification.id)}
            aria-label="Dismiss notification"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

export default AlertNotification;
