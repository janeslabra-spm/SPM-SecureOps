import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Response shape from the /stream/status endpoint.
 */
interface StreamStatus {
  people: number;
  phones: number;
  active_rule_matches: number;
  logged_this_frame: number;
  inference_ms: number;
  fps: number;
  message: string;
}

/**
 * LiveMonitor component — displays the live MJPEG video feed and
 * real-time detection metrics (people, phones, violations, latency, fps).
 *
 * Requirements: 7.2, 7.3, 7.7
 */
function LiveMonitor() {
  const [feedError, setFeedError] = useState(false);
  const [status, setStatus] = useState<StreamStatus | null>(null);
  const [statusError, setStatusError] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  // Reset feed error when component mounts or user retries
  const handleRetry = useCallback(() => {
    setFeedError(false);
    // Force the img to re-request by toggling the src
    if (imgRef.current) {
      imgRef.current.src = '';
      imgRef.current.src = '/stream/video.mjpg';
    }
  }, []);

  const handleFeedError = useCallback(() => {
    setFeedError(true);
  }, []);

  const handleFeedLoad = useCallback(() => {
    setFeedError(false);
  }, []);

  // Poll /stream/status every 2 seconds
  useEffect(() => {
    let active = true;

    const fetchStatus = async () => {
      try {
        const response = await fetch('/stream/status');
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data: StreamStatus = await response.json();
        if (active) {
          setStatus(data);
          setStatusError(false);
        }
      } catch {
        if (active) {
          setStatusError(true);
        }
      }
    };

    // Fetch immediately on mount
    fetchStatus();

    const interval = setInterval(fetchStatus, 2000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="live-monitor">
      <h1>Live Monitor</h1>

      <div className="live-monitor__content">
        {/* Video Feed */}
        <div className="live-monitor__feed-container">
          {feedError ? (
            <div className="live-monitor__error">
              <p className="live-monitor__error-message">Feed disconnected</p>
              <button onClick={handleRetry} className="live-monitor__retry-btn">
                Retry Connection
              </button>
            </div>
          ) : (
            <img
              ref={imgRef}
              src="/stream/video.mjpg"
              alt="Live security monitoring feed"
              className="live-monitor__video"
              onError={handleFeedError}
              onLoad={handleFeedLoad}
            />
          )}
        </div>

        {/* Metrics Panel */}
        <div className="live-monitor__metrics">
          <h2 className="live-monitor__metrics-title">Detection Metrics</h2>
          {statusError && (
            <p className="live-monitor__status-error">Unable to fetch metrics</p>
          )}
          {status ? (
            <div className="live-monitor__metrics-grid">
              <div className="live-monitor__metric">
                <span className="live-monitor__metric-label">People</span>
                <span className="live-monitor__metric-value">{status.people}</span>
              </div>
              <div className="live-monitor__metric">
                <span className="live-monitor__metric-label">Phones</span>
                <span className="live-monitor__metric-value">{status.phones}</span>
              </div>
              <div className="live-monitor__metric">
                <span className="live-monitor__metric-label">Active Violations</span>
                <span className="live-monitor__metric-value live-monitor__metric-value--violations">
                  {status.active_rule_matches}
                </span>
              </div>
              <div className="live-monitor__metric">
                <span className="live-monitor__metric-label">Inference Latency</span>
                <span className="live-monitor__metric-value">{status.inference_ms.toFixed(1)} ms</span>
              </div>
              <div className="live-monitor__metric">
                <span className="live-monitor__metric-label">FPS</span>
                <span className="live-monitor__metric-value">{status.fps.toFixed(1)}</span>
              </div>
              {status.message && (
                <div className="live-monitor__metric live-monitor__metric--message">
                  <span className="live-monitor__metric-label">Status</span>
                  <span className="live-monitor__metric-value">{status.message}</span>
                </div>
              )}
            </div>
          ) : (
            !statusError && <p className="live-monitor__loading">Loading metrics...</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default LiveMonitor;
