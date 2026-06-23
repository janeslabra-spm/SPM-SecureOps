"use client";

import { useState, useCallback, useEffect } from "react";
import { Play, Square, RefreshCw, Video, FileVideo, Wifi } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api-client";
import type { PipelineStatus } from "@/lib/types";

type SourcePreset = "demo" | "rtsp" | "file";

const PRESETS: { key: SourcePreset; label: string; icon: typeof Video }[] = [
  { key: "demo", label: "Demo Video", icon: FileVideo },
  { key: "rtsp", label: "Live Camera (RTSP/HTTP)", icon: Wifi },
  { key: "file", label: "Custom File", icon: Video },
];

export function PipelineControls() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [selectedPreset, setSelectedPreset] = useState<SourcePreset>("demo");
  const [customUrl, setCustomUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Poll pipeline status
  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      try {
        const s = await apiClient.getPipelineStatus();
        if (mounted) setStatus(s);
      } catch {
        // ignore
      }
    };
    poll();
    const interval = setInterval(poll, 3000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const handleStart = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
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
  }, [selectedPreset, customUrl]);

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

  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Pipeline Source</h3>
        <Badge variant={isRunning ? "default" : "secondary"}>
          {isRunning ? `Running · ${status?.current_fps.toFixed(1)} FPS` : "Stopped"}
        </Badge>
      </div>

      {/* Source preset buttons */}
      <div className="flex flex-wrap gap-2">
        {PRESETS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setSelectedPreset(key)}
            disabled={isRunning}
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

      {/* Action buttons */}
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

      {/* Status info */}
      {isRunning && status && (
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
