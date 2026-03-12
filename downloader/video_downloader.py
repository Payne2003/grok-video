"""
downloader/video_downloader.py

Downloads generated video files from Grok to the local output directory.

Design:
    - Works with both direct blob URLs and <a download> href links.
    - Retry with exponential back-off on transient HTTP errors.
    - Streams large files in chunks (no full-file memory load).
    - Uses FileManager to build the destination path.
    - Playwright Page is passed in — no browser management here.
"""

import logging
import os
import time
import urllib.request
import urllib.error
from typing import Callable, Optional

from playwright.sync_api import Page

from config.constants import (
    DOWNLOAD_CHUNK_SIZE,
    DOWNLOAD_MAX_RETRIES,
    DOWNLOAD_RETRY_DELAY_S,
    SELECTOR_VIDEO_RESULT,
)
from downloader.file_manager import FileManager
from jobs.job_model import Job

logger = logging.getLogger(__name__)


class VideoDownloader:
    """
    Extracts the video URL from the Grok page and downloads it.

    Parameters
    ----------
    file_manager:
        Builds destination paths and creates directories.
    max_retries:
        HTTP download retry attempts on transient failure.
    retry_delay:
        Base seconds between retries (doubles each attempt).
    log_callback:
        Optional UI log function.
    """

    def __init__(
        self,
        file_manager: Optional[FileManager] = None,
        max_retries:  int   = DOWNLOAD_MAX_RETRIES,
        retry_delay:  float = DOWNLOAD_RETRY_DELAY_S,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._fm          = file_manager or FileManager()
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._log         = log_callback or (lambda m: logger.info("[Downloader] %s", m))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download_for_job(self, page: Page, job: Job) -> str:
        """
        Extract the video URL from *page* and download the video.

        Parameters
        ----------
        page:
            The Playwright Page where Grok has finished generating.
        job:
            The source job (used for file naming).

        Returns
        -------
        str
            Absolute path to the saved video file.

        Raises
        ------
        RuntimeError
            If no video URL can be found on the page.
        OSError
            If the download fails after all retries.
        """
        video_url = self._extract_video_url(page)

        if not video_url:
            raise RuntimeError(
                "No video URL found on page. "
                "Grok may not have finished generating."
            )

        dest_path = self._fm.build_output_path(job.job_id, job.prompt)
        self._download(video_url, dest_path)
        return dest_path

    # ------------------------------------------------------------------
    # URL extraction
    # ------------------------------------------------------------------

    def _extract_video_url(self, page: Page) -> Optional[str]:
        """
        Try multiple strategies to find the video URL:
        1. <video src="…">
        2. <a download href="…">
        3. Blob URL via JS evaluation
        """
        try:
            # Strategy 1: <video> element
            el = page.query_selector("video[src]")
            if el:
                src = el.get_attribute("src")
                if src:
                    logger.debug("Found video src: %s", src[:80])
                    return src

            # Strategy 2: <a download> link
            el = page.query_selector("a[download][href]")
            if el:
                href = el.get_attribute("href")
                if href:
                    logger.debug("Found download href: %s", href[:80])
                    return href

            # Strategy 3: look for any mp4 link in DOM
            url = page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    const mp4 = links.find(a => a.href.includes('.mp4'));
                    return mp4 ? mp4.href : null;
                }
            """)
            if url:
                logger.debug("Found mp4 link via JS: %s", url[:80])
                return url

        except Exception as exc:
            logger.warning("[Downloader] URL extraction error: %s", exc)

        return None

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _download(self, url: str, dest_path: str) -> None:
        """
        Stream *url* to *dest_path* with retry + back-off.

        Raises
        ------
        OSError
            After all retries are exhausted.
        """
        self._log(f"Downloading → {os.path.basename(dest_path)}")

        for attempt in range(self._max_retries + 1):
            try:
                self._stream_to_file(url, dest_path)
                size_kb = os.path.getsize(dest_path) / 1024
                self._log(f"Download complete ({size_kb:.1f} KB).")
                return

            except (urllib.error.URLError, OSError) as exc:
                if attempt == self._max_retries:
                    raise OSError(
                        f"Download failed after {self._max_retries + 1} attempts: {exc}"
                    ) from exc

                delay = self._retry_delay * (2 ** attempt)
                self._log(
                    f"Download error (attempt {attempt + 1}): {exc}. "
                    f"Retrying in {delay:.1f}s…"
                )
                time.sleep(delay)

    def _stream_to_file(self, url: str, dest_path: str) -> None:
        """Open *url* and write response body to *dest_path* in chunks."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp, \
             open(dest_path, "wb") as out:
            while True:
                chunk = resp.read(DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                out.write(chunk)