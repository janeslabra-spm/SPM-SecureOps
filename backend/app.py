"""Main FastAPI application for the Security Monitoring System.

Entry point that initializes the application, registers routers, configures
CORS middleware, and manages startup/shutdown lifecycle for background services.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (one level above backend/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import AppConfig
from backend.db.session import configure, get_session_factory, init_db
from backend.db.audit_queries import insert_audit_log
from backend.routers.ai import router as ai_router
from backend.routers.audit import router as audit_router
from backend.routers.detect_frame import router as detect_frame_router
from backend.routers.health import router as health_router, set_detection_engine_active
from backend.routers.incidents import router as incidents_router
from backend.routers.pipeline import router as pipeline_router
from backend.routers.stream import router as stream_router
from backend.routers.zones import router as zones_router
from backend.core.bedrock_service import BedrockComplianceService, BedrockConfig
from backend.core.compliance_engine import ComplianceEventEngineImpl
from backend.core.event_dispatcher import ComplianceEventDispatcher
from backend.core.pipeline_manager import PipelineManager
from backend.workers.detection_worker import DetectionWorker
from backend.workers.retention_service import RetentionService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager handling startup and shutdown.

    Startup:
        - Load configuration from environment variables
        - Initialize database connection and schema
        - Start the DetectionWorker background thread
        - Start the RetentionService background scheduler

    Shutdown:
        - Stop the DetectionWorker
        - Stop the RetentionService
    """
    # --- Startup ---
    config = AppConfig(
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/security_monitoring",
        ),
        model_path=os.environ.get("MODEL_PATH", "yolo11s.pt"),
        device=os.environ.get("DEVICE", "auto"),
        confidence_threshold=float(os.environ.get("CONFIDENCE_THRESHOLD", "0.35")),
        image_size=int(os.environ.get("IMAGE_SIZE", "416")),
        source_mode=os.environ.get("SOURCE_MODE", "webcam"),
        camera_index=int(os.environ.get("CAMERA_INDEX", "0")),
        retention_days=int(os.environ.get("RETENTION_DAYS", "7")),
        ui_fps=int(os.environ.get("UI_FPS", "20")),
    )

    # Configure database engine and session factory
    configure(config)

    # Initialize database schema; terminate on failure
    try:
        await init_db()
    except Exception as exc:
        logger.error("Failed to connect to database: %s", exc)
        sys.exit(1)

    # Force-update desk zone to match config defaults (overrides stale DB values)
    try:
        from backend.db.desk_zone import upsert_desk_zone
        session_factory = get_session_factory()
        async with session_factory() as session:
            await upsert_desk_zone(
                session,
                x1_percent=config.desk_zone_x1,
                y1_percent=config.desk_zone_y1,
                x2_percent=config.desk_zone_x2,
                y2_percent=config.desk_zone_y2,
            )
        logger.info(
            "Desk zone set to: x1=%d%%, y1=%d%%, x2=%d%%, y2=%d%%",
            config.desk_zone_x1, config.desk_zone_y1,
            config.desk_zone_x2, config.desk_zone_y2,
        )
    except Exception as exc:
        logger.warning("Failed to update desk zone on startup: %s", exc)

    # Start detection worker
    screenshot_dir = Path(config.screenshots_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    # If DEMO_VIDEO_PATH is set, configure detection worker to use it
    demo_video_path = os.environ.get("DEMO_VIDEO_PATH")
    if demo_video_path:
        config.source_mode = "sample_video"
        config.sample_video_path = demo_video_path
        config.loop_video = True
        logger.info("Configured detection worker for demo video: %s", demo_video_path)

    detection_worker = DetectionWorker(
        config=config,
        db_session_factory=get_session_factory(),
        screenshot_dir=screenshot_dir,
    )
    detection_worker.start()
    app.state.detection_worker = detection_worker
    set_detection_engine_active(True)

    # Start retention service
    retention_service = RetentionService(
        db_session_factory=get_session_factory(),
        screenshot_dir=screenshot_dir,
        interval_hours=config.retention_interval_hours,
    )
    await retention_service.start()
    app.state.retention_service = retention_service

    # Initialize pipeline manager
    pipeline_manager = PipelineManager(
        config=config,
        db_session_factory=get_session_factory(),
    )
    app.state.pipeline_manager = pipeline_manager

    # Auto-start pipeline with demo video if DEMO_VIDEO_PATH is set
    demo_video_path = os.environ.get("DEMO_VIDEO_PATH")
    if demo_video_path:
        try:
            pipeline_manager.start(source_type="file", source_id=demo_video_path)
            logger.info("Pipeline auto-started with demo video: %s", demo_video_path)
        except Exception as exc:
            logger.warning("Failed to auto-start pipeline with demo video: %s", exc)

    # Initialize compliance event engine
    compliance_engine = ComplianceEventEngineImpl(
        session_factory=get_session_factory(),
        screenshots_dir=config.screenshots_dir,
        config=config,
    )
    await compliance_engine.start()
    app.state.compliance_engine = compliance_engine

    # Initialize compliance event dispatcher
    compliance_dispatcher = ComplianceEventDispatcher(event_engine=compliance_engine)
    await compliance_dispatcher.start()
    app.state.compliance_dispatcher = compliance_dispatcher

    # Initialize Bedrock AI compliance service (optional — disabled if no credentials)
    bedrock_config = BedrockConfig(
        enabled=bool(os.environ.get("AWS_BEDROCK_ENABLED", "").lower() in ("1", "true", "yes")),
        region=os.environ.get("AWS_BEDROCK_REGION", "us-east-1"),
        model_id=os.environ.get("AWS_BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0"),
        max_tokens=int(os.environ.get("AWS_BEDROCK_MAX_TOKENS", "300")),
        temperature=float(os.environ.get("AWS_BEDROCK_TEMPERATURE", "0.3")),
        cache_ttl_seconds=int(os.environ.get("AWS_BEDROCK_CACHE_TTL", "120")),
    )
    bedrock_service = BedrockComplianceService(bedrock_config)
    app.state.bedrock_service = bedrock_service
    if bedrock_service.available:
        logger.info("Bedrock AI compliance service is ACTIVE (model=%s)", bedrock_config.model_id)
    else:
        logger.info("Bedrock AI compliance service is INACTIVE (fallback mode)")

    logger.info("Security Monitoring System started successfully.")

    # Log system startup to audit trail
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            await insert_audit_log(
                session=session,
                event_type="system_start",
                description="Security Monitoring System started successfully",
                actor="system",
            )
    except Exception as exc:
        logger.warning("Failed to log startup to audit trail: %s", exc)

    yield

    # --- Shutdown ---
    detection_worker.stop()
    set_detection_engine_active(False)

    await retention_service.stop()

    await compliance_dispatcher.stop()
    await compliance_engine.stop()

    logger.info("Security Monitoring System shut down.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Returns:
        Configured FastAPI application with all routers and middleware.
    """
    # Load CORS origins from environment or use defaults
    cors_origins_env = os.environ.get("CORS_ORIGINS", "")
    if cors_origins_env:
        cors_origins = [origin.strip() for origin in cors_origins_env.split(",")]
    else:
        cors_origins = ["http://localhost:5173"]

    # Always allow requests from the frontend Docker container (Next.js rewrites)
    internal_origins = ["http://frontend:3000", "http://localhost:3000"]
    for origin in internal_origins:
        if origin not in cors_origins:
            cors_origins.append(origin)

    app = FastAPI(
        title="Security Monitoring System",
        description="Computer vision security monitoring API for detecting policy violations.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(stream_router)
    app.include_router(incidents_router)
    app.include_router(zones_router)
    app.include_router(audit_router)
    app.include_router(pipeline_router)
    app.include_router(detect_frame_router)
    app.include_router(ai_router)

    # Serve screenshot files as static assets
    # Use absolute path resolution to ensure it works in Docker (WORKDIR=/app)
    screenshots_path = Path(__file__).resolve().parent.parent / "screenshots"
    screenshots_path.mkdir(parents=True, exist_ok=True)
    app.mount("/screenshots", StaticFiles(directory=str(screenshots_path)), name="screenshots")

    return app


# Application instance used by uvicorn (e.g., `uvicorn backend.app:app`)
app = create_app()
