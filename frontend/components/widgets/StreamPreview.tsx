"use client";

import { useState, useCallback } from "react";
import { Video, VideoOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api-client";

export interface StreamPreviewProps {
  /** Allows parent to control visibility */
  isActive?: boolean;
}

/**
 * StreamPreview — Renders the MJPEG live video stream with a scan line overlay
 * indicating active monitoring. On stream error (503), shows a placeholder with
 * reduced opacity and hides the scan line.
 *
 * The img element's src is set to the MJPEG URL directly — the browser handles
 * MJPEG streaming natively via multipart/x-mixed-replace content type.
 *
 * Validates: Requirements 4.2, 4.3, 4.4, 13.7
 */
export function StreamPreview({ isActive = true }: StreamPreviewProps) {
  const [streamAvailable, setStreamAvailable] = useState(true);

  const streamUrl = apiClient.getStreamUrl();

  const handleError = useCallback(() => {
    setStreamAvailable(false);
  }, []);

  const handleLoad = useCallback(() => {
    setStreamAvailable(true);
  }, []);

  const isStreaming = isActive && streamAvailable;

  return (
    <div
      className={cn(
        "relative overflow-hidden",
        !isStreaming && "opacity-60"
      )}
      aria-label="Live stream preview"
    >
      {/* Stream content */}
      {isActive ? (
        <div className="relative w-full aspect-video">
          {/* MJPEG img element */}
          <img
            src={streamUrl}
            alt="Live monitoring feed"
            className="w-full h-full object-cover"
            onError={handleError}
            onLoad={handleLoad}
          />

          {/* Scan line overlay — only visible when stream is active */}
          {isStreaming && (
            <div
              className="absolute inset-0 pointer-events-none overflow-hidden"
              aria-hidden="true"
            >
              <div className="scan-line absolute left-0 right-0 h-[2px] bg-info/40 shadow-[0_0_8px_2px_hsla(var(--info),0.3)]" />
            </div>
          )}

          {/* Inactive placeholder overlay */}
          {!streamAvailable && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/60">
              <VideoOff
                className="w-12 h-12 text-muted-foreground mb-3"
                aria-hidden="true"
              />
              <p
                className="text-sm text-muted-foreground font-medium"
                aria-live="polite"
              >
                Monitoring is not active
              </p>
            </div>
          )}
        </div>
      ) : (
        /* Parent disabled the stream */
        <div className="relative w-full aspect-video flex flex-col items-center justify-center">
          <VideoOff
            className="w-12 h-12 text-muted-foreground mb-3"
            aria-hidden="true"
          />
          <p className="text-sm text-muted-foreground font-medium">
            Monitoring is not active
          </p>
        </div>
      )}

      {/* Status indicator in corner */}
      <div
        className="absolute top-3 left-3 flex items-center gap-2"
        role="status"
        aria-label={isStreaming ? "Stream status: live" : "Stream status: offline"}
      >
        {isStreaming ? (
          <>
            <span className="pulse-dot w-2.5 h-2.5 rounded-full bg-green-500" aria-hidden="true" />
            <span className="text-xs font-medium text-green-400">LIVE</span>
          </>
        ) : (
          <>
            <Video className="w-3.5 h-3.5 text-muted-foreground" aria-hidden="true" />
            <span className="text-xs font-medium text-muted-foreground">OFFLINE</span>
          </>
        )}
      </div>
    </div>
  );
}
