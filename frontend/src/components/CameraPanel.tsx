import { useState, useEffect, useRef } from "react";

// Use the full backend URL for the MJPEG stream so it works
// regardless of whether the frontend dev server is running
const BACKEND_URL = "http://localhost:8000";
const STREAM_URL = `${BACKEND_URL}/stream/video.mjpg`;

export default function CameraPanel() {
  const [disconnected, setDisconnected] = useState(false);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    // Only set the stream URL once the component is mounted
    // This prevents multiple simultaneous connections on re-renders
    setStreamUrl(STREAM_URL);

    const checkConnection = () => {
      const img = imgRef.current;
      if (img && img.complete && img.naturalWidth > 0) {
        if (mountedRef.current) setDisconnected(false);
      }
    };

    const initialTimer = setTimeout(() => {
      const img = imgRef.current;
      if (!img || !img.complete || img.naturalWidth === 0) {
        if (mountedRef.current) setDisconnected(true);
      }
    }, 10000);

    const interval = setInterval(checkConnection, 3000);

    return () => {
      mountedRef.current = false;
      clearTimeout(initialTimer);
      clearInterval(interval);
      // Clear the stream URL on unmount to close the MJPEG connection
      setStreamUrl(null);
    };
  }, []);

  const handleLoad = () => {
    setDisconnected(false);
  };

  const handleError = () => {
    setDisconnected(true);
  };

  return (
    <div className="relative w-full h-full bg-black rounded-lg overflow-hidden">
      {streamUrl && (
        <img
          ref={imgRef}
          src={streamUrl}
          alt="Live MJPEG Feed"
          className="w-full h-full object-cover"
          onLoad={handleLoad}
          onError={handleError}
        />
      )}
      {disconnected && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/80">
          <div className="flex flex-col items-center gap-2">
            <svg
              className="w-8 h-8 text-text-muted"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
              />
              <line x1="1" y1="1" x2="23" y2="23" strokeWidth={2} strokeLinecap="round" />
            </svg>
            <span className="text-white/70 font-medium text-xs">
              Feed Offline
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
