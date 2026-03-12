"""
engine/text_to_video.py

Drives the Grok Imagine page to convert a text prompt into a video.
Same pattern as image_to_video but without the upload step.
"""

import logging
import time
from typing import Callable, Optional

from playwright.sync_api import Page

from config.constants import (
    GROK_IMAGINE_URL,
    SELECTOR_IMAGINE_INPUT,
    SELECTOR_GENERATE_BUTTON,
)
from downloader.file_manager import FileManager
from downloader.video_downloader import VideoDownloader
from engine.job_poller import JobPoller
from jobs.job_model import Job, JobType

logger = logging.getLogger(__name__)


class TextToVideoEngine:
    """
    Automates the Grok text-to-video workflow.

    Parameters
    ----------
    file_manager:
        Builds output paths.
    downloader:
        Downloads the finished video.
    poller:
        Polls the page until generation finishes.
    log_callback:
        Optional UI log function.
    """

    def __init__(
        self,
        file_manager: Optional[FileManager]     = None,
        downloader:   Optional[VideoDownloader] = None,
        poller:       Optional[JobPoller]       = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._fm         = file_manager or FileManager()
        self._downloader = downloader   or VideoDownloader(log_callback=log_callback)
        self._poller     = poller       or JobPoller(log_callback=log_callback)
        self._log        = log_callback or (lambda m: logger.info("[TxtToVideo] %s", m))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, page: Page, job: Job) -> str:
        """
        Execute the full text-to-video flow for *job*.

        Parameters
        ----------
        page:
            Active Playwright Page pointed at grok.com/imagine.
        job:
            Must be of type TEXT_TO_VIDEO.

        Returns
        -------
        str
            Absolute path to the downloaded video file.
        """
        self._validate_job(job)

        self._log(f"Starting text-to-video")
        self._log(f"Prompt: {job.prompt[:80]}{'…' if len(job.prompt) > 80 else ''}")

        self._navigate_to_imagine(page)
        self._fill_prompt(page, job.prompt)
        self._click_generate(page)

        self._poller.wait_for_result(page)

        output_path = self._downloader.download_for_job(page, job)
        self._log(f"Saved → {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _validate_job(self, job: Job) -> None:
        if job.job_type != JobType.TEXT_TO_VIDEO:
            raise ValueError(
                f"TextToVideoEngine expects TEXT_TO_VIDEO, got {job.job_type.value}"
            )
        if not job.prompt.strip():
            raise ValueError(f"Job {job.job_id} has an empty prompt.")

    def _navigate_to_imagine(self, page: Page) -> None:
        if "imagine" not in page.url.lower():
            self._log("Navigating to Grok Imagine…")
            page.goto(GROK_IMAGINE_URL, wait_until="domcontentloaded")
            page.wait_for_selector(SELECTOR_IMAGINE_INPUT, timeout=20_000)

    def _fill_prompt(self, page: Page, prompt: str) -> None:
        self._log("Filling prompt…")
        try:
            textarea = page.wait_for_selector(SELECTOR_IMAGINE_INPUT, timeout=10_000)
            textarea.click()
            textarea.fill(prompt)
        except Exception as exc:
            raise RuntimeError(f"Failed to fill prompt: {exc}") from exc

    def _click_generate(self, page: Page) -> None:
        self._log("Clicking Generate…")
        try:
            btn = page.wait_for_selector(SELECTOR_GENERATE_BUTTON, timeout=10_000)
            btn.click()
        except Exception as exc:
            raise RuntimeError(f"Failed to click Generate: {exc}") from exc