"""
engine/job_poller.py

Watches a Grok generation page and polls until the video is ready,
an error appears, or a timeout is reached.

Intentionally pure logic — no browser management, no file I/O.
The caller (image_to_video / text_to_video) handles setup & teardown.
"""

import logging
import time
from typing import Callable, Optional

from playwright.sync_api import Page

from config.constants import (
    JOB_GENERATE_TIMEOUT_S,
    JOB_POLL_INTERVAL_S,
    SELECTOR_VIDEO_RESULT,
    SELECTOR_PROGRESS_BAR,
    SELECTOR_ERROR_MESSAGE,
)

logger = logging.getLogger(__name__)


class GenerationTimeoutError(Exception):
    """Raised when Grok does not produce a video within the allowed time."""


class GenerationError(Exception):
    """Raised when Grok returns an explicit error message."""


class JobPoller:
    """
    Polls a Grok page until generation succeeds, fails, or times out.

    Parameters
    ----------
    timeout:
        Maximum seconds to wait for the video to appear.
    poll_interval:
        Seconds between DOM checks.
    log_callback:
        Optional UI log function.
    """

    def __init__(
        self,
        timeout:       int   = JOB_GENERATE_TIMEOUT_S,
        poll_interval: float = JOB_POLL_INTERVAL_S,
        log_callback:  Optional[Callable[[str], None]] = None,
    ) -> None:
        self._timeout       = timeout
        self._poll_interval = poll_interval
        self._log           = log_callback or (lambda m: logger.info("[Poller] %s", m))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def wait_for_result(self, page: Page) -> None:
        """
        Block until a video element or an error appears on *page*.

        Raises
        ------
        GenerationTimeoutError
            If no result appears within *timeout* seconds.
        GenerationError
            If Grok shows an error message.
        """
        self._log("Waiting for Grok to generate video…")
        deadline = time.monotonic() + self._timeout

        while True:
            remaining = deadline - time.monotonic()

            if remaining <= 0:
                raise GenerationTimeoutError(
                    f"Generation timed out after {self._timeout}s."
                )

            # Check for explicit error
            error_msg = self._check_error(page)
            if error_msg:
                raise GenerationError(f"Grok returned error: {error_msg}")

            # Check for success
            if self._check_video_ready(page):
                self._log("Video ready ✓")
                return

            # Log progress if visible
            progress = self._read_progress(page)
            if progress:
                self._log(f"Generating… {progress} ({int(remaining)}s left)")
            else:
                self._log(f"Generating… ({int(remaining)}s left)")

            time.sleep(self._poll_interval)

    # ------------------------------------------------------------------
    # DOM probes
    # ------------------------------------------------------------------

    def _check_video_ready(self, page: Page) -> bool:
        """Return True if a video element or download link is present."""
        try:
            el = page.query_selector(SELECTOR_VIDEO_RESULT)
            return el is not None
        except Exception:
            return False

    def _check_error(self, page: Page) -> Optional[str]:
        """Return the error message text if present, else None."""
        try:
            el = page.query_selector(SELECTOR_ERROR_MESSAGE)
            if el:
                return (el.inner_text() or "Unknown error").strip()
        except Exception:
            pass
        return None

    def _read_progress(self, page: Page) -> Optional[str]:
        """Return a progress string (e.g. '42%') if a progress bar exists."""
        try:
            el = page.query_selector(SELECTOR_PROGRESS_BAR)
            if el:
                # Try aria-valuenow first
                val = el.get_attribute("aria-valuenow")
                if val:
                    return f"{val}%"
                # Fallback to inner text
                text = el.inner_text().strip()
                if text:
                    return text
        except Exception:
            pass
        return None