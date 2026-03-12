"""
queue/job_queue.py

Thread-safe job queue backed by a JSON file for persistence across restarts.

Design:
    - All mutations protected by threading.Lock.
    - Persistence is atomic (write to .tmp then os.replace).
    - Lock held for entire save to prevent concurrent writes (Windows-safe).
    - Observers can register callbacks for status-change events.
    - get_next() returns the oldest PENDING job (FIFO).
"""

import json
import logging
import os
import threading
from typing import Callable, Dict, List, Optional

from config.constants import JOBS_FILE
from jobs.job_model import Job, JobStatus  

logger = logging.getLogger(__name__)

# Callback signature:  fn(job: Job) -> None
StatusCallback = Callable[["Job"], None]


class JobQueue:
    """
    Thread-safe FIFO job queue with JSON persistence.

    Usage
    -----
    >>> q = JobQueue()
    >>> q.load()
    >>> job = Job(job_type=JobType.TEXT_TO_VIDEO, prompt="A cat flying")
    >>> q.add(job)
    >>> next_job = q.get_next()
    """

    def __init__(self, jobs_file: str = JOBS_FILE) -> None:
        self._file = jobs_file
        self._lock = threading.Lock()
        self._jobs: Dict[str, Job] = {}
        self._order: List[str] = []
        self._callbacks: List[StatusCallback] = []

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load jobs from disk. Call once at startup."""
        if not os.path.exists(self._file):
            logger.debug("[JobQueue] No jobs file at %s.", self._file)
            return

        try:
            with open(self._file, "r", encoding="utf-8") as fh:
                raw: List[dict] = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("[JobQueue] Could not load jobs file: %s", exc)
            return

        with self._lock:
            for item in raw:
                try:
                    job = Job.from_dict(item)
                    self._jobs[job.job_id] = job
                    if job.job_id not in self._order:
                        self._order.append(job.job_id)
                except (KeyError, ValueError) as exc:
                    logger.warning("[JobQueue] Skipping corrupt job entry: %s", exc)

        logger.info("[JobQueue] Loaded %d jobs.", len(self._jobs))

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add(self, job: Job) -> None:
        """Enqueue a new job and persist."""
        with self._lock:
            self._jobs[job.job_id] = job
            self._order.append(job.job_id)
        self._save_under_lock()
        logger.info("[JobQueue] Added %s.", job)

    def update(self, job: Job) -> None:
        """
        Persist a modified job back to the queue.

        Raises
        ------
        KeyError
            If the job is not in the queue.
        """
        with self._lock:
            if job.job_id not in self._jobs:
                raise KeyError(f"Job {job.job_id} not found in queue.")
            self._jobs[job.job_id] = job
        self._save_under_lock()
        self._notify(job)

    def cancel(self, job_id: str) -> bool:
        """
        Cancel a PENDING job.

        Returns
        -------
        bool
            True if cancelled, False if job not found or not cancellable.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != JobStatus.PENDING:
                return False
            job.mark_cancelled()
        self._save_under_lock()
        self._notify(job)
        return True

    def remove(self, job_id: str) -> bool:
        """Remove a job from queue and storage. Returns True if removed."""
        with self._lock:
            if job_id not in self._jobs:
                return False
            del self._jobs[job_id]
            self._order = [jid for jid in self._order if jid != job_id]
        self._save_under_lock()
        return True

    def clear_terminal(self) -> int:
        """
        Remove all completed/failed/cancelled jobs.

        Returns
        -------
        int
            Number of jobs removed.
        """
        with self._lock:
            terminal = [
                jid for jid, j in self._jobs.items() if j.is_terminal
            ]
            for jid in terminal:
                del self._jobs[jid]
            self._order = [jid for jid in self._order if jid not in terminal]
            modified = len(terminal) > 0
        if modified:
            self._save_under_lock()
        return len(terminal)

    def _save_under_lock(self) -> None:
        """
        Persist to disk. Must be called while NOT holding _lock.
        Acquires lock for full duration of file write to avoid
        concurrent os.replace on Windows.
        """
        dir_name = os.path.dirname(os.path.abspath(self._file))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        tmp_path = os.path.join(dir_name or ".", os.path.basename(self._file) + ".tmp")

        with self._lock:
            payload = [
                self._jobs[jid].to_dict()
                for jid in self._order
                if jid in self._jobs
            ]
            try:
                with open(tmp_path, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, indent=2)
                os.replace(tmp_path, self._file)
            except OSError as exc:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                logger.error("[JobQueue] Failed to save jobs: %s", exc)
                raise

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_next(self) -> Optional[Job]:
        """Return the oldest PENDING job, or None if queue is empty."""
        with self._lock:
            for jid in self._order:
                job = self._jobs.get(jid)
                if job and job.status == JobStatus.PENDING:
                    return job
        return None

    def get(self, job_id: str) -> Optional[Job]:
        """Return a specific job by ID, or None."""
        with self._lock:
            return self._jobs.get(job_id)

    def all_jobs(self) -> List[Job]:
        """Return a snapshot of all jobs in insertion order."""
        with self._lock:
            return [self._jobs[jid] for jid in self._order if jid in self._jobs]

    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status == JobStatus.PENDING)

    def running_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status == JobStatus.RUNNING)

    def __len__(self) -> int:
        with self._lock:
            return len(self._jobs)

    # ------------------------------------------------------------------
    # Observer pattern
    # ------------------------------------------------------------------

    def register_callback(self, fn: StatusCallback) -> None:
        """Register a callback invoked whenever a job's status changes."""
        self._callbacks.append(fn)

    def _notify(self, job: Job) -> None:
        for fn in self._callbacks:
            try:
                fn(job)
            except Exception as exc:
                logger.warning("[JobQueue] Callback error: %s", exc)
