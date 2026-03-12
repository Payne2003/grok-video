"""
storage/history_store.py

Append-only log of completed jobs, stored as a JSON array.

The history is intentionally separate from the live job queue so that:
    - Completed jobs can be pruned from the queue without losing records.
    - UI can show a full history without loading all queue state.
    - Future analytics / export features have a clean data source.
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import List, Optional

from config.constants import HISTORY_FILE
from jobs.job_model import Job, JobStatus  


logger = logging.getLogger(__name__)


class HistoryStore:
    """
    Append-only store for completed / failed / cancelled jobs.

    Usage
    -----
    >>> store = HistoryStore()
    >>> store.record(completed_job)
    >>> entries = store.load_all()
    """

    def __init__(self, history_file: str = HISTORY_FILE) -> None:
        self._file = history_file

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, job: Job) -> None:
        """
        Append a terminal job to the history file.

        Only DONE / FAILED / CANCELLED jobs are accepted.

        Raises
        ------
        ValueError
            If the job is not in a terminal state.
        """
        if not job.is_terminal:
            raise ValueError(
                f"Only terminal jobs can be recorded. "
                f"Job {job.job_id} has status={job.status.value}."
            )

        entry = job.to_dict()
        entry["recorded_at"] = datetime.now(timezone.utc).isoformat()

        entries = self._load_raw()
        entries.append(entry)
        self._atomic_write(entries)
        logger.info("[HistoryStore] Recorded job %s (%s).", job.job_id, job.status.value)

    def load_all(self) -> List[dict]:
        """
        Return all history entries (raw dicts) newest-first.
        """
        return list(reversed(self._load_raw()))

    def load_jobs(self) -> List[Job]:
        """
        Return all history entries as Job objects, newest-first.
        Corrupt entries are skipped with a warning.
        """
        jobs = []
        for raw in self.load_all():
            try:
                jobs.append(Job.from_dict(raw))
            except (KeyError, ValueError) as exc:
                logger.warning("[HistoryStore] Skipping corrupt entry: %s", exc)
        return jobs

    def count(self) -> int:
        """Return total number of history entries."""
        return len(self._load_raw())

    def clear(self) -> None:
        """Wipe the entire history file."""
        self._atomic_write([])
        logger.info("[HistoryStore] History cleared.")

    def exists(self) -> bool:
        return os.path.exists(self._file)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_raw(self) -> List[dict]:
        if not os.path.exists(self._file):
            return []
        try:
            with open(self._file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("[HistoryStore] Cannot read history: %s", exc)
            return []

    def _atomic_write(self, entries: List[dict]) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self._file)), exist_ok=True)
        dir_name = os.path.dirname(os.path.abspath(self._file))
        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8",
                dir=dir_name, delete=False, suffix=".tmp",
            ) as tmp:
                json.dump(entries, tmp, indent=2)
                tmp_path = tmp.name
            os.replace(tmp_path, self._file)
        except OSError as exc:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise