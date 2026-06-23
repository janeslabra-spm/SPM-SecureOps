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

from backend.config import AppConfig
from backend.db.session import configure, get_session_factory, init_db
from backend.db.audit_queries import insert_audit_log
from backend.routers.audit import router as audit_router
from backend.routers.health import router as health_router, set_detection_engine_active
from backend.routers.incidents import router as incidents_router
from backend.routers.pipeline import router as pipeline_router
from backend.routers.stream import router as stream_router
from backend.routers.zones import router as zones_router
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
        )
    )

    # Configure database engine and session factory
    configure(config)

    # Initialize database schema; terminate on failure
    try:
        await init_db()
    except Exception as exc:
        logger.error("Failed to connect to database: %s", exc)
        sys.exit(1)

    # Start detection worker
    screenshot_dir = Path(config.screenshots_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)

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

    return app


# Application instance used by uvicorn (e.g., `uvicorn backend.app:app`)
app = create_app()
