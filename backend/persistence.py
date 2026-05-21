"""
Data persistence layer for RTI4All.

Handles saving and loading data to/from JSON files with proper error handling,
atomic writes, and backup management.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)


class PersistenceError(Exception):
    """Raised when data persistence operations fail."""

    pass


class DataStore:
    """
    Manages persistent storage of application data with atomic writes and backups.

    Features:
    - Atomic writes (write to temp file, then rename)
    - Automatic backups before overwriting
    - Error recovery
    - Configurable auto-save
    """

    def __init__(
        self,
        data_file: Path,
        backup_dir: Optional[Path] = None,
        auto_backup: bool = True,
        max_backups: int = 5,
    ):
        """
        Initialize the data store.

        Args:
            data_file: Path to the main data file
            backup_dir: Directory for backups (defaults to data_file.parent / "backups")
            auto_backup: Whether to create backups automatically before saves
            max_backups: Maximum number of backup files to keep
        """
        self.data_file = data_file
        self.backup_dir = backup_dir or (data_file.parent / "backups")
        self.auto_backup = auto_backup
        self.max_backups = max_backups

        # Ensure directories exist
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if self.auto_backup:
            self.backup_dir.mkdir(parents=True, exist_ok=True)

        log.info(
            f"DataStore initialized: file={self.data_file}, "
            f"backups={'enabled' if self.auto_backup else 'disabled'}"
        )

    def load(self) -> dict[str, Any]:
        """
        Load data from the data file.

        Returns:
            The loaded data dictionary

        Raises:
            PersistenceError: If loading fails and no backup is available
        """
        if not self.data_file.exists():
            log.warning(f"Data file not found: {self.data_file}")
            raise PersistenceError(f"Data file not found: {self.data_file}")

        try:
            with open(self.data_file, encoding="utf-8") as fh:
                data = json.load(fh)
            log.info(
                f"Data loaded successfully: {len(data.get('requests', []))} requests, "
                f"{len(data.get('departments', []))} departments"
            )
            return data
        except json.JSONDecodeError as e:
            log.error(f"JSON decode error in {self.data_file}: {e}")
            # Try to recover from backup
            backup_data = self._try_recover_from_backup()
            if backup_data is not None:
                log.warning("Recovered data from backup after JSON decode error")
                return backup_data
            raise PersistenceError(f"Failed to parse data file: {e}") from e
        except Exception as e:
            log.error(f"Unexpected error loading data: {e}")
            raise PersistenceError(f"Failed to load data: {e}") from e

    def save(self, data: dict[str, Any]) -> None:
        """
        Save data to the data file atomically with optional backup.

        Args:
            data: The data dictionary to save

        Raises:
            PersistenceError: If saving fails
        """
        try:
            # Create backup before overwriting
            if self.auto_backup and self.data_file.exists():
                self._create_backup()

            # Write to temporary file first (atomic write)
            temp_file = self.data_file.with_suffix(".tmp")
            try:
                with open(temp_file, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=2, ensure_ascii=False)

                # Atomic rename (on most filesystems)
                temp_file.replace(self.data_file)

                log.info(
                    f"Data saved successfully: {len(data.get('requests', []))} requests, "
                    f"{len(data.get('departments', []))} departments"
                )
            finally:
                # Clean up temp file if it still exists
                if temp_file.exists():
                    temp_file.unlink()

        except Exception as e:
            log.error(f"Failed to save data: {e}")
            raise PersistenceError(f"Failed to save data: {e}") from e

    def _create_backup(self) -> None:
        """Create a timestamped backup of the current data file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"sample_data_{timestamp}.json"

            shutil.copy2(self.data_file, backup_file)
            log.info(f"Backup created: {backup_file}")

            # Clean up old backups
            self._cleanup_old_backups()

        except Exception as e:
            log.warning(f"Failed to create backup: {e}")
            # Don't fail the save operation if backup fails

    def _cleanup_old_backups(self) -> None:
        """Remove old backup files keeping only max_backups most recent."""
        try:
            backup_files = sorted(
                self.backup_dir.glob("sample_data_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            for old_backup in backup_files[self.max_backups :]:
                old_backup.unlink()
                log.debug(f"Removed old backup: {old_backup}")

        except Exception as e:
            log.warning(f"Failed to cleanup old backups: {e}")

    def _try_recover_from_backup(self) -> Optional[dict[str, Any]]:
        """
        Try to recover data from the most recent backup.

        Returns:
            The recovered data or None if no valid backup exists
        """
        if not self.backup_dir.exists():
            return None

        backup_files = sorted(
            self.backup_dir.glob("sample_data_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for backup_file in backup_files:
            try:
                with open(backup_file, encoding="utf-8") as fh:
                    data = json.load(fh)
                log.info(f"Successfully recovered data from backup: {backup_file}")
                return data
            except Exception as e:
                log.warning(f"Failed to recover from backup {backup_file}: {e}")
                continue

        return None

    def create_checkpoint(self, name: str) -> None:
        """
        Create a named checkpoint (manual backup).

        Args:
            name: Name for the checkpoint (will be sanitized)
        """
        try:
            # Sanitize checkpoint name
            safe_name = "".join(c for c in name if c.isalnum() or c in "._- ")
            safe_name = safe_name.strip().replace(" ", "_")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            checkpoint_file = (
                self.backup_dir / f"checkpoint_{safe_name}_{timestamp}.json"
            )

            shutil.copy2(self.data_file, checkpoint_file)
            log.info(f"Checkpoint created: {checkpoint_file}")

        except Exception as e:
            log.error(f"Failed to create checkpoint '{name}': {e}")
            raise PersistenceError(f"Failed to create checkpoint: {e}") from e


def get_data_store(
    data_file: Path,
    enable_persistence: bool = True,
) -> Optional[DataStore]:
    """
    Factory function to create a DataStore instance.

    Args:
        data_file: Path to the main data file
        enable_persistence: Whether to enable persistence (can be disabled via env var)

    Returns:
        DataStore instance or None if persistence is disabled
    """
    # Allow disabling persistence via environment variable
    env_enabled = os.environ.get("ENABLE_DATA_PERSISTENCE", "true").lower()
    if env_enabled in ("false", "0", "no"):
        log.info("Data persistence disabled via environment variable")
        return None

    if not enable_persistence:
        log.info("Data persistence disabled")
        return None

    try:
        return DataStore(
            data_file=data_file,
            auto_backup=True,
            max_backups=int(os.environ.get("MAX_BACKUPS", "10")),
        )
    except Exception as e:
        log.error(f"Failed to initialize data store: {e}")
        return None
