"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Play, Square, RefreshCw, Video, FileVideo, Wifi, Camera } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api-client";
import type { PipelineStatus } from "@/lib/types";

export type SourcePreset = "demo" | "rtsp" | "file" | "browser";

interface PipelineControlsProps {
  /** Callback when the user selects a different source preset */
  onSourceChange?: (source: SourcePreset) => void;
}

const PRESETS: { key: SourcePreset; label: string; icon: typeof Video }[] = [
  { key: "browser", label: "Browser Camera", icon: Camera },
  { key: "demo", label: "Demo Video", icon: FileVideo },
  { key: "rtsp", label: "Live Camera (RTSP/HTTP)", icon: Wifi },
  { key: "file", label: "Custom File", icon: Video },
];

export function PipelineControls({ onSourceChange }: PipelineControlsProps) {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [streamActive, setStreamActive] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState<SourcePreset>("browser");
  const [customUrl, setCustomUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initialCheckDone = useRef(false);

  // Poll pipeline status and stream availability
  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      try {
        const s = await apiClient.getPipelineStatus();
        if (mounted) setStatus(s);
      } catch {
        // ignore
      }

      // Also check if the MJPEG stream is active (detection worker running)
      try {
        await apiClient.getStreamStatus();
        if (mounted) setStreamActive(true);
      } catch {
        if (mounted) setStreamActive(false);
      }
    };
    poll();
    const interval = setInterval(poll, 3000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  // On initial load, if the backend stream is already active (demo video running),
  // auto-switch to demo mode
  useEffect(() => {
    if (!initialCheckDone.current && streamActive && selectedPreset === "browser") {
      initialCheckDone.current = true;
      setSelectedPreset("demo");
      onSourceChange?.("demo");
    }
  }, [streamActive, selectedPreset, onSourceChange]);

  const startPipeline = useCallback(async (sourceType: string, sourceId: string | number) => {
    setLoading(true);
    setError(null);
    try {
      // Stop existing pipeline if running
      if (status?.running) {
        try {
          await apiClient.stopPipeline();
        } catch {
          // ignore stop errors
        }
      }
      await apiClient.startPipeline(sourceType, sourceId);
      const s = await apiClient.getPipelineStatus();
      setStatus(s);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to start pipeline";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [status?.running]);

  const handlePresetChange = useCallback(async (preset: SourcePreset) => {
    setSelectedPreset(preset);
    setError(null);
    onSourceChange?.(preset);

    // For demo video: if the stream is already active (detection worker running
    // with demo video), just switch the view. If not, try to start the pipeline.
    if (preset === "demo" && !streamActive) {
      await startPipeline("file", "/app/backend/demo.mp4");
    }

    // If switching back to browser, we don't stop the backend pipeline —
    // just switch the frontend view to browser camera mode
  }, [onSourceChange, startPipeline, streamActive]);

  const handleStart = useCallback(async () => {
    if (selectedPreset === "browser") return;

    let sourceType: string;
    let sourceId: string | number;

    switch (selectedPreset) {
      case "demo":
        sourceType = "file";
        sourceId = "/app/backend/demo.mp4";
        break;
      case "rtsp":
        sourceType = "cctv";
        sourceId = customUrl;
        break;
      case "file":
        sourceType = "file";
        sourceId = customUrl;
        break;
      default:
        return;
    }

    await startPipeline(sourceType, sourceId);
  }, [selectedPreset, customUrl, startPipeline]);

  const handleStop = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await apiClient.stopPipeline();
      const s = await apiClient.getPipelineStatus();
      setStatus(s);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to stop pipeline";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const isRunning = status?.running ?? false;
  const isStreamOrPipelineActive = streamActive || isRunning;

  return (
    <div className="glass rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Pipeline Source</h3>
        <Badge variant={isStreamOrPipelineActive ? "default" : "secondary"}>
          {isStreamOrPipelineActive
            ? `Running · ${status?.current_fps?.toFixed(1) ?? "—"} FPS`
            : "Stopped"}
        </Badge>
      </div>

      {/* Source preset buttons */}
      <div className="flex flex-wrap gap-2">
        {PRESETS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => handlePresetChange(key)}
            disabled={loading}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors
              ${selectedPreset === key
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
              } disabled:opacity-50`}
          >
            <Icon className="size-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Source-specific info */}
      {selectedPreset === "browser" && (
        <p className="text-xs text-muted-foreground">
          Your browser camera will be used as the video source. Detection runs via the backend API.
        </p>
      )}

      {selectedPreset === "demo" && (
        <div className="text-xs text-muted-foreground space-y-1">
          <p>
            Demo video source: <code className="rounded bg-muted px-1 py-0.5 text-[11px]">/app/backend/demo.mp4</code>
          </p>
          {streamActive && (
            <p className="text-success font-medium">✓ Stream is active — video feed is live below</p>
          )}
        </div>
      )}

      {/* URL/path input for rtsp and custom file */}
      {(selectedPreset === "rtsp" || selectedPreset === "file") && (
        <Input
          placeholder={
            selectedPreset === "rtsp"
              ? "rtsp://192.168.1.100:8080/h264 or http://..."
              : "/app/backend/your-video.mp4"
          }
          value={customUrl}
          onChange={(e) => setCustomUrl(e.target.value)}
          disabled={isRunning}
          className="text-xs"
        />
      )}

      {/* Action buttons for non-browser sources */}
      {selectedPreset !== "browser" && !streamActive && (
        <div className="flex gap-2">
          {!isRunning ? (
            <Button
              size="sm"
              onClick={handleStart}
              disabled={loading || ((selectedPreset === "rtsp" || selectedPreset === "file") && !customUrl)}
              className="gap-1.5"
            >
              {loading ? <RefreshCw className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
              Start Pipeline
            </Button>
          ) : (
            <Button
              size="sm"
              variant="destructive"
              onClick={handleStop}
              disabled={loading}
              className="gap-1.5"
            >
              {loading ? <RefreshCw className="size-3.5 animate-spin" /> : <Square className="size-3.5" />}
              Stop Pipeline
            </Button>
          )}
        </div>
      )}

      {/* Stop button when stream is active */}
      {selectedPreset !== "browser" && streamActive && isRunning && (
        <Button
          size="sm"
          variant="destructive"
          onClick={handleStop}
          disabled={loading}
          className="gap-1.5"
        >
          {loading ? <RefreshCw className="size-3.5 animate-spin" /> : <Square className="size-3.5" />}
          Stop Pipeline
        </Button>
      )}

      {/* Status info */}
      {isStreamOrPipelineActive && status && (
        <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
          <div>Frames: <span className="font-medium text-foreground">{status.frames_processed}</span></div>
          <div>Inference: <span className="font-medium text-foreground">{status.last_inference_ms.toFixed(0)}ms</span></div>
          <div>
            Detections:{" "}
            <span className="font-medium text-foreground">
              {Object.values(status.per_class_counts).reduce((a, b) => a + b, 0)}
            </span>
          </div>
        </div>
      )}

      {/* Error display */}
      {(error || status?.error) && (
        <p className="text-xs text-destructive">{error || status?.error}</p>
      )}
    </div>
  );
}
