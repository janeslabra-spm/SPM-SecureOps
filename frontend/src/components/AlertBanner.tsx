import { useState, useEffect, useCallback } from "react";

export interface AlertItem {
  id: string;
  incidentType: string;
  confidence: number;
  timestamp: number;
}

interface AlertBannerProps {
  alerts: AlertItem[];
  onDismiss: (id: string) => void;
}

const MIN_DISPLAY_MS = 5000;

function formatIncidentType(type: string): string {
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function SingleAlert({
  alert,
  onDismiss,
}: {
  alert: AlertItem;
  onDismiss: (id: string) => void;
}) {
  const [canDismiss, setCanDismiss] = useState(false);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setCanDismiss(true);
    }, MIN_DISPLAY_MS);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      onDismiss(alert.id);
    }, MIN_DISPLAY_MS + 2000);
    return () => clearTimeout(timer);
  }, [alert.id, onDismiss]);

  const handleDismiss = useCallback(() => {
    if (canDismiss) {
      setVisible(false);
      onDismiss(alert.id);
    }
  }, [canDismiss, alert.id, onDismiss]);

  if (!visible) return null;

  return (
    <div
      role="alert"
      className="flex items-center justify-between gap-3 px-4 py-3 rounded-xl bg-bg-card border border-warning/30 shadow-lg animate-slide-in"
    >
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-warning/10 flex items-center justify-center">
          <svg className="w-4 h-4 text-warning" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        </div>
        <div>
          <span className="text-sm font-medium text-text-primary">
            {formatIncidentType(alert.incidentType)}
          </span>
          <span className="text-xs text-warning font-mono ml-2">
            {(alert.confidence * 100).toFixed(1)}%
          </span>
        </div>
      </div>
      <button
        onClick={handleDismiss}
        disabled={!canDismiss}
        aria-label="Dismiss alert"
        className={`text-xs px-2 py-1 rounded-lg transition-colors ${
          canDismiss
            ? "text-text-secondary hover:text-text-primary hover:bg-bg-hover cursor-pointer"
            : "text-text-muted cursor-not-allowed"
        }`}
      >
        ✕
      </button>
    </div>
  );
}

export default function AlertBanner({ alerts, onDismiss }: AlertBannerProps) {
  if (alerts.length === 0) return null;

  return (
    <div className="fixed top-20 right-6 z-50 flex flex-col gap-2 max-w-sm w-full">
      {alerts.map((alert) => (
        <SingleAlert key={alert.id} alert={alert} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
