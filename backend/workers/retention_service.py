"""Retention Service for automated cleanup of expired incidents and screenshots.

Runs as a background asyncio task, deleting incident records older than 7 days
along with their associated screenshot files. Also removes orphan screenshot
files not referenced by any incident record.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.db.queries import delete_expired_incidents, query_incidents

logger = logging.getLogger(__name__)


@dataclass
class RetentionResult:
    """Result of a single retention cleanup execution."""

    deleted_records: int = 0
    deleted_files: int = 0
    orphan_files_deleted: int = 0
    errors: list[str] = field(default_factory=list)


class RetentionService:
    """Background service that enforces data retention policies.

    Deletes incident records older than RETENTION_DAYS and their associated
    screenshot files. Also removes orphan screenshots not referenced by any
    incident record and older than the retention period.
    """

    RETENTION_DAYS = 7

    def __init__(
        self,
        db_session_factory: async_sessionmaker[AsyncSession],
        screenshot_dir: Path,
        interval_hours: int = 24,
    ) -> None:
        """Initialize the retention service.

        Args:
            db_session_factory: Async session factory for database access.
            screenshot_dir: Path to the directory containing screenshot files.
            interval_hours: Hours between cleanup executions (default 24).
        """
        self._db_session_factory = db_session_factory
        self._screenshot_dir = screenshot_dir
        self._interval_hours = interval_hours
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background cleanup task.

        Creates an asyncio task that runs cleanup at the configured interval.
        """
        if self._task is not None and not self._task.done():
            logger.warning("Retention service is already running.")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Retention service started (interval=%dh, retention=%dd).",
            self._interval_hours,
            self.RETENTION_DAYS,
        )

    async def stop(self) -> None:
        """Stop the background cleanup task gracefully."""
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Retention service stopped.")

    async def _run_loop(self) -> None:
        """Internal loop that runs cleanup at the configured interval."""
        try:
            while self._running:
                try:
                    result = await self.run_cleanup()
                    logger.info(
                        "Retention cleanup complete: "
                        "deleted_records=%d, deleted_files=%d, orphan_files=%d, errors=%d",
                        result.deleted_records,
                        result.deleted_files,
                        result.orphan_files_deleted,
                        len(result.errors),
                    )
                except Exception as exc:
                    logger.error("Retention cleanup failed: %s", exc)

                # Sleep for the configured interval
                await asyncio.sleep(self._interval_hours * 3600)
        except asyncio.CancelledError:
            pass

    async def run_cleanup(self) -> RetentionResult:
        """Execute a single retention cleanup cycle.

        Performs three operations:
        1. Delete expired incident records from the database.
        2. Delete associated screenshot files for those records.
        3. Delete orphan screenshot files (unreferenced and older than 7 days).

        Returns:
            RetentionResult with counts of deleted records, files, orphans, and errors.
        """
        result = RetentionResult()

        # Step 1 & 2: Delete expired incidents and their screenshot files
        async with self._db_session_factory() as session:
            expired_incidents = await delete_expired_incidents(
                session, retention_days=self.RETENTION_DAYS
            )
            result.deleted_records = len(expired_incidents)

            # Delete associated screenshot files
            for incident in expired_incidents:
                if incident.screenshot_path:
                    self._delete_screenshot_file(
                        incident.screenshot_path, result
                    )

        # Step 3: Delete orphan screenshot files
        await self._delete_orphan_screenshots(result)

        # Log the results, even when all counts are zero (Requirement 4.6)
        logger.info(
            "Retention cleanup results: "
            "records_deleted=%d, files_deleted=%d, orphans_deleted=%d",
            result.deleted_records,
            result.deleted_files,
            result.orphan_files_deleted,
        )

        return result

    def _delete_screenshot_file(
        self, screenshot_path: str, result: RetentionResult
    ) -> None:
        """Attempt to delete a screenshot file from the filesystem.

        Handles missing files gracefully (Requirement 4.4) and permission
        errors without stopping (Requirement 4.5).

        Args:
            screenshot_path: Path to the screenshot file (relative or absolute).
            result: RetentionResult to update with counts and errors.
        """
        try:
            file_path = Path(screenshot_path)
            # If the path is relative, resolve it against the screenshot directory
            if not file_path.is_absolute():
                file_path = self._screenshot_dir / file_path

            if not file_path.exists():
                # File doesn't exist — skip without error (Requirement 4.4)
                return

            file_path.unlink()
            result.deleted_files += 1

        except PermissionError as exc:
            # Log permission error and continue (Requirement 4.5)
            error_msg = f"Permission denied deleting file '{screenshot_path}': {exc}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        except OSError as exc:
            # Handle other filesystem errors gracefully
            error_msg = f"Error deleting file '{screenshot_path}': {exc}"
            logger.error(error_msg)
            result.errors.append(error_msg)

    async def _delete_orphan_screenshots(self, result: RetentionResult) -> None:
        """Delete screenshot files not referenced by any incident and older than 7 days.

        Scans the screenshot directory for files, checks each against incident
        records in the database, and deletes unreferenced files that are older
        than the retention period based on file modification time.

        Args:
            result: RetentionResult to update with orphan deletion counts and errors.
        """
        import time

        if not self._screenshot_dir.exists():
            return

        # Gather all screenshot file paths in the directory
        try:
            screenshot_files = [
                f for f in self._screenshot_dir.iterdir() if f.is_file()
            ]
        except OSError as exc:
            error_msg = f"Error listing screenshot directory: {exc}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            return

        if not screenshot_files:
            return

        # Get all screenshot paths referenced by current incidents
        referenced_paths: set[str] = set()
        async with self._db_session_factory() as session:
            # Query all remaining incidents to get their screenshot paths
            all_incidents = await query_incidents(session, limit=100)
            for incident in all_incidents:
                if incident.screenshot_path:
                    referenced_paths.add(incident.screenshot_path)

            # Also do a full scan — query_incidents has a limit of 100,
            # so we need to get all screenshot paths from the DB
            from sqlalchemy import select
            from backend.db.models import Incident

            stmt = select(Incident.screenshot_path).where(
                Incident.screenshot_path != ""
            )
            db_result = await session.execute(stmt)
            for (path_value,) in db_result.all():
                referenced_paths.add(path_value)

        # Calculate the cutoff time for orphan files (7 days ago)
        cutoff_time = time.time() - (self.RETENTION_DAYS * 24 * 3600)

        # Check each file in the screenshot directory
        for file_path in screenshot_files:
            try:
                # Determine if the file is referenced by any incident
                # Check both the full path and the filename
                file_name = file_path.name
                file_str = str(file_path)

                is_referenced = (
                    file_name in referenced_paths
                    or file_str in referenced_paths
                    or any(
                        file_name == Path(ref).name
                        for ref in referenced_paths
                        if ref
                    )
                )

                if is_referenced:
                    continue

                # Check if the file is older than 7 days
                mod_time = os.path.getmtime(file_path)
                if mod_time > cutoff_time:
                    # File is recent — keep it
                    continue

                # File is orphaned and old — delete it
                file_path.unlink()
                result.orphan_files_deleted += 1

            except PermissionError as exc:
                error_msg = (
                    f"Permission denied deleting orphan file '{file_path}': {exc}"
                )
                logger.error(error_msg)
                result.errors.append(error_msg)

            except OSError as exc:
                error_msg = f"Error processing orphan file '{file_path}': {exc}"
                logger.error(error_msg)
                result.errors.append(error_msg)
