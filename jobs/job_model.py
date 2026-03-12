"""
queue/job_model.py

Defines the Job dataclass — the single source of truth for every
generation task flowing through the system.

Design:
    - Immutable ID, mutable status/result fields.
    - Typed enum for status — no raw strings.
    - to_dict / from_dict for JSON persistence.
    - created_at / updated_at auto-managed.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class JobType(str, Enum):
    IMAGE_TO_VIDEO = "image_to_video"
    TEXT_TO_VIDEO  = "text_to_video"


class JobStatus(str, Enum):
    PENDING    = "pending"     # waiting in queue
    RUNNING    = "running"     # being processed by a worker
    DONE       = "done"        # completed successfully
    FAILED     = "failed"      # permanent failure (retries exhausted)
    CANCELLED  = "cancelled"   # cancelled by user


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    """
    Represents one video-generation task.

    Parameters
    ----------
    job_type:
        Whether this is image-to-video or text-to-video.
    prompt:
        Text prompt sent to Grok.
    image_path:
        Absolute path to the source image (IMAGE_TO_VIDEO only).
    output_path:
        Where the finished video will be saved (set by downloader).
    status:
        Current lifecycle stage.
    retries:
        Number of times this job has been retried after failure.
    error:
        Last error message, if any.
    job_id:
        UUID auto-generated on creation.
    created_at / updated_at:
        ISO-8601 UTC timestamps.
    """

    job_type:    JobType
    prompt:      str

    image_path:  Optional[str] = None
    output_path: Optional[str] = None
    status:      JobStatus     = JobStatus.PENDING
    retries:     int           = 0
    error:       Optional[str] = None

    job_id:      str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at:  str = field(default_factory=_utcnow)
    updated_at:  str = field(default_factory=_utcnow)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def mark_running(self) -> None:
        self.status     = JobStatus.RUNNING
        self.updated_at = _utcnow()

    def mark_done(self, output_path: str) -> None:
        self.status      = JobStatus.DONE
        self.output_path = output_path
        self.error       = None
        self.updated_at  = _utcnow()

    def mark_failed(self, reason: str) -> None:
        self.status     = JobStatus.FAILED
        self.error      = reason
        self.updated_at = _utcnow()

    def mark_cancelled(self) -> None:
        self.status     = JobStatus.CANCELLED
        self.updated_at = _utcnow()

    def increment_retry(self) -> None:
        self.retries   += 1
        self.status     = JobStatus.PENDING
        self.error      = None
        self.updated_at = _utcnow()

    @property
    def is_terminal(self) -> bool:
        """Return True when no further state transitions are possible."""
        return self.status in (
            JobStatus.DONE,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "job_id":      self.job_id,
            "job_type":    self.job_type.value,
            "prompt":      self.prompt,
            "image_path":  self.image_path,
            "output_path": self.output_path,
            "status":      self.status.value,
            "retries":     self.retries,
            "error":       self.error,
            "created_at":  self.created_at,
            "updated_at":  self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        return cls(
            job_id      = data["job_id"],
            job_type    = JobType(data["job_type"]),
            prompt      = data["prompt"],
            image_path  = data.get("image_path"),
            output_path = data.get("output_path"),
            status      = JobStatus(data.get("status", JobStatus.PENDING.value)),
            retries     = data.get("retries", 0),
            error       = data.get("error"),
            created_at  = data.get("created_at", _utcnow()),
            updated_at  = data.get("updated_at", _utcnow()),
        )

    def __repr__(self) -> str:
        return (
            f"Job(id={self.job_id[:8]}…, type={self.job_type.value}, "
            f"status={self.status.value}, retries={self.retries})"
        )