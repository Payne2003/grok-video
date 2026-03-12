"""
downloader/file_manager.py

Utility for managing output file paths and directory creation.
Keeps all path-building logic in one place so engine / downloader
modules never construct paths manually.
"""

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from config.constants import OUTPUT_DIR, VIDEO_EXTENSION, SUPPORTED_IMAGE_EXTENSIONS

logger = logging.getLogger(__name__)


class FileManager:
    """
    Manages the output directory and constructs safe file paths.

    Parameters
    ----------
    output_dir:
        Root directory for all generated videos.
    """

    def __init__(self, output_dir: str = OUTPUT_DIR) -> None:
        self._output_dir = output_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ensure_output_dir(self) -> str:
        """Create the output directory if it doesn't exist. Returns the path."""
        os.makedirs(self._output_dir, exist_ok=True)
        return self._output_dir

    def build_output_path(
        self,
        job_id: str,
        prompt: str,
        extension: str = VIDEO_EXTENSION,
    ) -> str:
        """
        Build a unique, filesystem-safe output file path.

        Format: <output_dir>/<YYYYMMDD_HHMMSS>_<slug>_<short_id><ext>

        Parameters
        ----------
        job_id:
            UUID string used for uniqueness suffix.
        prompt:
            Source prompt; converted to a readable slug.
        extension:
            File extension including dot (default: .mp4).
        """
        self.ensure_output_dir()

        ts    = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        slug  = self._slugify(prompt, max_len=30)
        short = job_id[:8]

        filename = f"{ts}_{slug}_{short}{extension}"
        return os.path.join(self._output_dir, filename)

    def validate_image_path(self, path: str) -> str:
        """
        Validate that *path* points to an existing, supported image file.

        Returns the absolute path.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        ValueError
            If the extension is not in SUPPORTED_IMAGE_EXTENSIONS.
        """
        abs_path = os.path.abspath(path)

        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"Image not found: {abs_path}")

        ext = os.path.splitext(abs_path)[1].lower()
        if ext not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(
                f"Unsupported image type: {ext!r}. "
                f"Supported: {sorted(SUPPORTED_IMAGE_EXTENSIONS)}"
            )

        return abs_path

    def list_outputs(self) -> list[str]:
        """Return absolute paths of all files in the output directory."""
        if not os.path.isdir(self._output_dir):
            return []
        return sorted(
            os.path.join(self._output_dir, f)
            for f in os.listdir(self._output_dir)
            if os.path.isfile(os.path.join(self._output_dir, f))
        )

    def delete_output(self, path: str) -> bool:
        """
        Delete an output file.

        Returns True if deleted, False if the file did not exist.
        Only deletes files inside the output directory (safety check).
        """
        abs_path = os.path.abspath(path)
        abs_out  = os.path.abspath(self._output_dir)

        if not abs_path.startswith(abs_out):
            raise PermissionError(
                f"Refusing to delete file outside output dir: {abs_path}"
            )

        if not os.path.isfile(abs_path):
            return False

        os.remove(abs_path)
        logger.info("[FileManager] Deleted %s.", abs_path)
        return True

    @property
    def output_dir(self) -> str:
        return self._output_dir

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _slugify(text: str, max_len: int = 40) -> str:
        """
        Convert *text* to a lowercase, underscore-separated slug.
        Non-alphanumeric characters are replaced with underscores.
        Consecutive underscores are collapsed.
        """
        slug = text.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        slug = re.sub(r"_+", "_", slug).strip("_")
        return slug[:max_len] or "untitled"