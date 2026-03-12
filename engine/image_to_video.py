"""
engine/image_to_video.py

Drives the Grok Imagine page to convert an image + prompt into a video.

Responsibilities:
    - Upload the source image
    - Fill in the prompt
    - Click Generate
    - Delegate polling to JobPoller
    - Delegate download to VideoDownloader
    - Return the absolute path of the saved video

No browser lifecycle management here — caller (WorkerPool processor)
provides a ready GrokClient.
"""

import logging
import os
import time
from typing import Callable, Optional

from playwright.sync_api import Page

from config.constants import (
    GROK_IMAGINE_URL,
    SELECTOR_IMAGINE_INPUT,
    SELECTOR_GENERATE_BUTTON,
    JOB_GENERATE_TIMEOUT_S,
    JOB_POLL_INTERVAL_S,
)
from downloader.file_manager import FileManager
from downloader.video_downloader import VideoDownloader
from engine.job_poller import JobPoller
from jobs.job_model import Job, JobType

logger = logging.getLogger(__name__)

# Selector for the file-upload input (hidden by default in most browsers)
_UPLOAD_INPUT_SELECTOR = "input[type='file'][accept*='image']"
# Fallback: any visible upload button
_UPLOAD_BUTTON_SELECTOR = "button:has-text('Upload'), label:has-text('Upload image')"


class ImageToVideoEngine:
    """
    Automates the Grok image-to-video workflow.

    Parameters
    ----------
    file_manager:
        Validates image paths and builds output paths.
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
        self._log        = log_callback or (lambda m: logger.info("[ImgToVideo] %s", m))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, page: Page, job: Job) -> str:
        """
        Execute the full image-to-video flow for *job*.

        Parameters
        ----------
        page:
            Active Playwright Page pointed at grok.com/imagine.
        job:
            Must be of type IMAGE_TO_VIDEO with a valid image_path.

        Returns
        -------
        str
            Absolute path to the downloaded video file.

        Raises
        ------
        ValueError
            If the job is the wrong type or image_path is missing.
        FileNotFoundError
            If the image file does not exist.
        RuntimeError
            If Grok interaction fails at any step.
        """
        self._validate_job(job)

        image_path = self._fm.validate_image_path(job.image_path)

        self._log(f"Starting image-to-video: {os.path.basename(image_path)}")
        self._log(f"Prompt: {job.prompt[:80]}{'…' if len(job.prompt) > 80 else ''}")

        self._navigate_to_imagine(page)
        self._upload_image(page, image_path)
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
        if job.job_type != JobType.IMAGE_TO_VIDEO:
            raise ValueError(
                f"ImageToVideoEngine expects IMAGE_TO_VIDEO, got {job.job_type.value}"
            )
        if not job.image_path:
            raise ValueError(f"Job {job.job_id} has no image_path.")

    def _navigate_to_imagine(self, page: Page) -> None:
        """Navigate to Imagine page if not already there."""
        if "imagine" not in page.url.lower():
            self._log("Navigating to Grok Imagine…")
            page.goto(GROK_IMAGINE_URL, wait_until="domcontentloaded")
            page.wait_for_selector(SELECTOR_IMAGINE_INPUT, timeout=20_000)

    def _upload_image(self, page: Page, image_path: str) -> None:
        """Set the file input to the image path."""
        self._log(f"Uploading image: {os.path.basename(image_path)}")
        try:
            # Direct file-input approach (most reliable)
            upload_input = page.wait_for_selector(
                _UPLOAD_INPUT_SELECTOR, timeout=10_000, state="attached"
            )
            upload_input.set_input_files(image_path)
            time.sleep(0.5)   # let Grok process the upload
        except Exception as exc:
            raise RuntimeError(f"Failed to upload image: {exc}") from exc

    def _fill_prompt(self, page: Page, prompt: str) -> None:
        """Type the prompt into the textarea."""
        self._log("Filling prompt…")
        try:
            textarea = page.wait_for_selector(SELECTOR_IMAGINE_INPUT, timeout=10_000)
            textarea.click()
            textarea.fill(prompt)
        except Exception as exc:
            raise RuntimeError(f"Failed to fill prompt: {exc}") from exc

    def _click_generate(self, page: Page) -> None:
        """Click the Generate button."""
        self._log("Clicking Generate…")
        try:
            btn = page.wait_for_selector(SELECTOR_GENERATE_BUTTON, timeout=10_000)
            btn.click()
        except Exception as exc:
            raise RuntimeError(f"Failed to click Generate: {exc}") from exc