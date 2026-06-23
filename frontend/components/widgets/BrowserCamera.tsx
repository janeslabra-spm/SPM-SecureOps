"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Camera, CameraOff, AlertTriangle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api-client";
import type { BrowserDetection } from "@/lib/types";

interface BrowserCameraProps {
  /** Whether to actively capture and send frames for detection */
  active?: boolean;
  /** Frames per second to send to backend (default: 2) */
  fps?: number;
  /** Callback when detections are received */
  onDetections?: (detections: BrowserDetection[], inferenceMs: number) => void;
}

type CameraState = "idle" | "requesting" | "active" | "denied" | "error";

/**
 * BrowserCamera — Uses the browser's getUserMedia API to access the user's
 * webcam, displays a live preview, captures frames at a configurable rate,
 * sends them to the backend for YOLO inference, and draws detection
 * bounding boxes as an overlay on the video.
 */
export function BrowserCamera({ active = true, fps = 2, onDetections }: BrowserCameraProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [cameraState, setCameraState] = useState<CameraState>("idle");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [detections, setDetections] = useState<BrowserDetection[]>([]);
  const [inferenceMs, setInferenceMs] = useState(0);
  const [detecting, setDetecting] = useState(false);

  // Start camera
  const startCamera = useCallback(async () => {
    setCameraState("requesting");
    setErrorMessage("");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 960 },
          height: { ideal: 540 },
          facingMode: "environment",
        },
        audio: false,
      });

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      setCameraState("active");
    } catch (err) {
      if (err instanceof DOMException) {
        if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
          setCameraState("denied");
          setErrorMessage("Camera permission was denied. Please allow camera access in your browser settings.");
        } else if (err.name === "NotFoundError") {
          setCameraState("error");
          setErrorMessage("No camera found on this device.");
        } else {
          setCameraState("error");
          setErrorMessage(`Camera error: ${err.message}`);
        }
      } else {
        setCameraState("error");
        setErrorMessage("Failed to access camera.");
      }
    }
  }, []);

  // Stop camera
  const stopCamera = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setDetections([]);
    setCameraState("idle");
  }, []);

  // Capture a frame and send it to backend
  const captureAndDetect = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current || detecting) return;
    if (videoRef.current.readyState < 2) return; // not enough data

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas to match video dimensions
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    // Draw current frame to canvas
    ctx.drawImage(video, 0, 0);

    // Convert to JPEG blob
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/jpeg", 0.85);
    });

    if (!blob) return;

    setDetecting(true);
    try {
      const response = await apiClient.detectFrame(blob);
      setDetections(response.detections);
      setInferenceMs(response.inference_ms);
      onDetections?.(response.detections, response.inference_ms);
      drawOverlay(response.detections, video.videoWidth, video.videoHeight);
    } catch {
      // Silently ignore detection errors to not disrupt the feed
    } finally {
      setDetecting(false);
    }
  }, [detecting, onDetections]);

  // Draw bounding box overlay
  const drawOverlay = useCallback(
    (dets: BrowserDetection[], width: number, height: number) => {
      const overlay = overlayCanvasRef.current;
      if (!overlay) return;

      overlay.width = width;
      overlay.height = height;
      const ctx = overlay.getContext("2d");
      if (!ctx) return;

      ctx.clearRect(0, 0, width, height);

      for (const det of dets) {
        const { x1, y1, x2, y2 } = det.bbox;
        const bw = x2 - x1;
        const bh = y2 - y1;

        // Color by label
        let color: string;
        if (det.label === "person") {
          color = "#3b82f6"; // blue
        } else if (det.label === "cell phone") {
          color = "#ef4444"; // red
        } else {
          color = "#22c55e"; // green
        }

        // Draw box
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.strokeRect(x1, y1, bw, bh);

        // Draw label background
        const label = `${det.label} ${(det.confidence * 100).toFixed(0)}%`;
        ctx.font = "bold 13px sans-serif";
        const textMetrics = ctx.measureText(label);
        const textHeight = 16;
        ctx.fillStyle = color;
        ctx.fillRect(x1, y1 - textHeight - 4, textMetrics.width + 8, textHeight + 4);

        // Draw label text
        ctx.fillStyle = "#ffffff";
        ctx.fillText(label, x1 + 4, y1 - 4);
      }
    },
    []
  );

  // Start/stop detection loop based on active prop
  useEffect(() => {
    if (cameraState === "active" && active) {
      const interval = 1000 / fps;
      intervalRef.current = setInterval(() => {
        captureAndDetect();
      }, interval);

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      };
    }
    return undefined;
  }, [cameraState, active, fps, captureAndDetect]);

  // Auto-start camera when component mounts and active is true
  useEffect(() => {
    if (active && cameraState === "idle") {
      startCamera();
    }

    return () => {
      stopCamera();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Count detections by type
  const phoneCount = detections.filter((d) => d.label === "cell phone").length;
  const personCount = detections.filter((d) => d.label === "person").length;

  return (
    <div className="relative w-full">
      {/* Video + overlay container */}
      <div className="relative w-full aspect-video bg-black rounded-lg overflow-hidden">
        {/* Live video element */}
        <video
          ref={videoRef}
          className={cn(
            "w-full h-full object-cover",
            cameraState !== "active" && "hidden"
          )}
          playsInline
          muted
          autoPlay
        />

        {/* Detection overlay canvas (positioned over video) */}
        <canvas
          ref={overlayCanvasRef}
          className={cn(
            "absolute inset-0 w-full h-full pointer-events-none",
            cameraState !== "active" && "hidden"
          )}
        />

        {/* Hidden canvas for frame capture */}
        <canvas ref={canvasRef} className="hidden" />

        {/* Status overlays */}
        {cameraState === "requesting" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <Loader2 className="w-10 h-10 text-muted-foreground animate-spin mb-3" />
            <p className="text-sm text-muted-foreground font-medium">
              Requesting camera permission...
            </p>
          </div>
        )}

        {cameraState === "denied" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center px-4">
            <CameraOff className="w-10 h-10 text-destructive mb-3" />
            <p className="text-sm text-destructive font-medium text-center">
              Camera Access Denied
            </p>
            <p className="text-xs text-muted-foreground mt-1 text-center max-w-xs">
              {errorMessage}
            </p>
          </div>
        )}

        {cameraState === "error" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center px-4">
            <AlertTriangle className="w-10 h-10 text-warning mb-3" />
            <p className="text-sm text-warning font-medium text-center">
              Camera Error
            </p>
            <p className="text-xs text-muted-foreground mt-1 text-center max-w-xs">
              {errorMessage}
            </p>
          </div>
        )}

        {cameraState === "idle" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <Camera className="w-10 h-10 text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground font-medium">
              Browser camera inactive
            </p>
          </div>
        )}

        {/* Live indicator */}
        {cameraState === "active" && (
          <div className="absolute top-3 left-3 flex items-center gap-2">
            <span className="pulse-dot w-2.5 h-2.5 rounded-full bg-green-500" />
            <span className="text-xs font-medium text-green-400">BROWSER CAM</span>
          </div>
        )}

        {/* Inference indicator */}
        {cameraState === "active" && detecting && (
          <div className="absolute top-3 right-3">
            <Loader2 className="w-4 h-4 text-info animate-spin" />
          </div>
        )}
      </div>

      {/* Detection stats bar */}
      {cameraState === "active" && (
        <div className="flex items-center justify-between px-3 py-2 mt-2 rounded-lg bg-muted/50 text-xs">
          <div className="flex items-center gap-4">
            <span className="text-muted-foreground">
              People: <span className="font-semibold text-foreground">{personCount}</span>
            </span>
            <span className="text-muted-foreground">
              Phones:{" "}
              <span className={cn("font-semibold", phoneCount > 0 ? "text-destructive" : "text-foreground")}>
                {phoneCount}
              </span>
            </span>
          </div>
          <span className="text-muted-foreground">
            Inference: <span className="font-semibold text-foreground">{inferenceMs.toFixed(0)}ms</span>
          </span>
        </div>
      )}
    </div>
  );
}
