"""Application configuration for the Security Monitoring System backend."""

from dataclasses import dataclass, field


@dataclass
class AppConfig:
    """Central configuration for the Security Monitoring System.

    Fields are grouped by subsystem: database, detection, video source,
    incident thresholds, streaming, retention, server, and desk zone.
    """

    # Database
    database_url: str  # PostgreSQL connection string

    # Detection
    model_path: str = "yolo11n.pt"
    device: str = "auto"
    confidence_threshold: float = 0.40
    image_size: int = 640

    # Video source
    source_mode: str = "webcam"  # "webcam" | "sample_video"
    camera_index: int = 0
    camera_width: int = 960
    camera_height: int = 540
    sample_video_path: str = ""
    loop_video: bool = True

    # Incident thresholds
    duration_threshold: float = 1.0  # seconds before logging
    cooldown_seconds: int = 10  # suppress duplicates within this window
    proximity_pixels: int = 80  # phone-to-person proximity

    # Streaming
    ui_fps: int = 2  # frames per second for MJPEG stream

    # Retention
    retention_days: int = 7
    retention_interval_hours: int = 24

    # Server
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173"])
    screenshots_dir: str = "screenshots"

    # Desk Zone defaults (percentage values 0-100)
    desk_zone_x1: int = 20
    desk_zone_y1: int = 35
    desk_zone_x2: int = 80
    desk_zone_y2: int = 75
