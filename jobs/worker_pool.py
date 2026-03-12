"""
queue/worker_pool.py

Background worker pool that drains the JobQueue.

Design:
    - Single daemon thread per worker (Grok only allows 1 concurrent job).
    - Exponential back-off retry: failed jobs are re-queued up to max_retries.
    - Graceful shutdown: stop() drains current job before exiting.
    - Processor callable is injected — no direct engine import (testable).
    - All state transitions happen through JobQueue.update() so observers
      and the persistence layer stay in sync automatically.
"""

import logging
import threading
import time
from typing import Callable, Optional

from config.constants import JOB_POLL_INTERVAL_S, JOB_MAX_RETRIES
from jobs.job_model import Job, JobStatus      
from jobs.job_queue import JobQueue

logger = logging.getLogger(__name__)

# Signature: processor(job: Job) → str  (returns output_path on success)
JobProcessor = Callable[[Job], str]


class WorkerPool:
    """
    Manages one or more background worker threads that process jobs.

    Parameters
    ----------
    queue:
        The shared JobQueue to drain.
    processor:
        Callable that does the actual Grok interaction.
        Must return the absolute output path on success.
        Must raise on failure.
    num_workers:
        Number of parallel workers (keep at 1 for Grok).
    poll_interval:
        Seconds to sleep between queue polls when idle.
    max_retries:
        Failed jobs are retried this many times before permanent failure.
    log_callback:
        Optional UI log function.
    """

    def __init__(
        self,
        queue:        JobQueue,
        processor:    JobProcessor,
        num_workers:  int   = 1,
        poll_interval: float = JOB_POLL_INTERVAL_S,
        max_retries:  int   = JOB_MAX_RETRIES,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._queue         = queue
        self._processor     = processor
        self._num_workers   = num_workers
        self._poll_interval = poll_interval
        self._max_retries   = max_retries
        self._log           = log_callback or (lambda m: logger.info("[WorkerPool] %s", m))

        self._stop_event = threading.Event()
        self._threads:   list[threading.Thread] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start all worker threads. Safe to call only once."""
        if self._threads:
            raise RuntimeError("WorkerPool already started.")

        self._stop_event.clear()

        for i in range(self._num_workers):
            t = threading.Thread(
                target=self._worker_loop,
                args=(i,),
                name=f"Worker-{i}",
                daemon=True,
            )
            t.start()
            self._threads.append(t)

        self._log(f"WorkerPool started ({self._num_workers} worker(s)).")

    def stop(self, timeout: float = 30.0) -> None:
        """
        Signal all workers to stop and wait for them to finish.

        Parameters
        ----------
        timeout:
            Maximum seconds to wait for each thread to exit.
        """
        self._log("Stopping WorkerPool…")
        self._stop_event.set()

        for t in self._threads:
            t.join(timeout=timeout)
            if t.is_alive():
                logger.warning("[WorkerPool] Thread %s did not stop cleanly.", t.name)

        self._threads.clear()
        self._log("WorkerPool stopped.")

    @property
    def is_running(self) -> bool:
        return bool(self._threads) and not self._stop_event.is_set()

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    def _worker_loop(self, worker_id: int) -> None:
        self._log(f"Worker-{worker_id} started.")

        while not self._stop_event.is_set():
            job = self._queue.get_next()

            if job is None:
                self._stop_event.wait(timeout=self._poll_interval)
                continue

            self._process_job(job, worker_id)

        self._log(f"Worker-{worker_id} exiting.")

    def _process_job(self, job: Job, worker_id: int) -> None:
        self._log(f"[Worker-{worker_id}] Starting {job}")

        job.mark_running()
        try:
            self._queue.update(job)
        except KeyError:
            logger.warning("[WorkerPool] Job %s disappeared from queue.", job.job_id)
            return

        try:
            output_path = self._processor(job)
            job.mark_done(output_path)
            self._queue.update(job)
            self._log(f"[Worker-{worker_id}] ✓ Done: {output_path}")

        except Exception as exc:
            error_msg = str(exc)
            logger.exception("[WorkerPool] Job %s failed: %s", job.job_id, error_msg)

            if job.retries < self._max_retries:
                job.increment_retry()
                self._queue.update(job)
                delay = 2 ** job.retries
                self._log(
                    f"[Worker-{worker_id}] ↺ Retry {job.retries}/{self._max_retries} "
                    f"in {delay}s — {error_msg}"
                )
                time.sleep(delay)
            else:
                job.mark_failed(error_msg)
                self._queue.update(job)
                self._log(
                    f"[Worker-{worker_id}] ✗ Permanent failure after "
                    f"{job.retries} retries: {error_msg}"
                )