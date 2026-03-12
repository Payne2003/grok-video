"""
storage/job_store.py

Thin persistence layer for the JobQueue's backing store.
Wraps raw JSON read/write with schema validation and migration support.

This is intentionally separate from JobQueue so the queue can be
tested without touching the filesystem, and so migrations can be
applied independently of queue logic.
"""

import json
import logging
import os
import tempfile
from typing import List, Optional

from config.constants import JOBS_FILE
from jobs.job_model import Job  

logger = logging.getLogger(__name__)

_STORE_VERSION = 1


class JobStore:
    """
    Read / write / migrate the jobs JSON file.

    Usage
    -----
    >>> store = JobStore()
    >>> jobs  = store.load_all()
    >>> store.save_all(jobs)
    """

    def __init__(self, jobs_file: str = JOBS_FILE) -> None:
        self._file = jobs_file

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_all(self) -> List[Job]:
        """
        Load all jobs from disk.

        Returns an empty list if the file is missing.
        Logs a warning and returns an empty list if corrupt.
        """
        if not os.path.exists(self._file):
            return []

        try:
            with open(self._file, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("[JobStore] Cannot read %s: %s", self._file, exc)
            return []

        # Support both bare list and versioned dict format
        if isinstance(raw, dict) and "jobs" in raw:
            raw = raw["jobs"]
        if not isinstance(raw, list):
            logger.warning("[JobStore] Unexpected format in %s; expected list.", self._file)
            return []

        jobs: List[Job] = []
        for idx, item in enumerate(raw):
            try:
                jobs.append(Job.from_dict(item))
            except (KeyError, ValueError) as exc:
                logger.warning("[JobStore] Skipping job[%d]: %s", idx, exc)

        logger.info("[JobStore] Loaded %d jobs.", len(jobs))
        return jobs

    def save_all(self, jobs: List[Job]) -> None:
        """
        Atomically overwrite the jobs file with the given job list.

        Raises
        ------
        OSError
            If the file cannot be written.
        """
        os.makedirs(os.path.dirname(os.path.abspath(self._file)), exist_ok=True)

        payload = {
            "version": _STORE_VERSION,
            "jobs": [j.to_dict() for j in jobs],
        }

        self._atomic_write(payload)
        logger.info("[JobStore] Saved %d jobs.", len(jobs))

    def delete(self, job_id: str) -> bool:
        """
        Remove a single job by ID.

        Returns
        -------
        bool
            True if removed, False if not found.
        """
        jobs = self.load_all()
        original_len = len(jobs)
        jobs = [j for j in jobs if j.job_id != job_id]

        if len(jobs) == original_len:
            return False

        self.save_all(jobs)
        return True

    def exists(self) -> bool:
        """Return True if the backing store file exists."""
        return os.path.exists(self._file)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _atomic_write(self, payload: dict) -> None:
        dir_name = os.path.dirname(os.path.abspath(self._file))
        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8",
                dir=dir_name, delete=False, suffix=".tmp",
            ) as tmp:
                json.dump(payload, tmp, indent=2)
                tmp_path = tmp.name
            os.replace(tmp_path, self._file)
        except OSError as exc:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise OSError(f"Failed to write {self._file}: {exc}") from exc