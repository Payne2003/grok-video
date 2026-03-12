"""
config/constants.py

All hard-coded values live here.
Nothing in this file should be user-configurable at runtime.
"""

import os

# ---------------------------------------------------------------------------
# Project root — every path is derived from here so the tool can run from
# any working directory.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Grok URLs
# ---------------------------------------------------------------------------
GROK_HOME_URL    = "https://grok.com"
GROK_IMAGINE_URL = "https://grok.com/imagine"

# ---------------------------------------------------------------------------
# Data directories
# ---------------------------------------------------------------------------
DATA_DIR    = os.path.join(PROJECT_ROOT, "data")
OUTPUT_DIR  = os.path.join(PROJECT_ROOT, "output")
LOG_DIR     = os.path.join(PROJECT_ROOT, "logs")

# ---------------------------------------------------------------------------
# Storage file paths
# ---------------------------------------------------------------------------
JOBS_FILE    = os.path.join(DATA_DIR, "jobs.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
SESSION_FILE = os.path.join(PROJECT_ROOT, "auth", "session_state.json")

# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------
BROWSER_NAVIGATION_TIMEOUT_MS = 30_000
BROWSER_PAGE_READY_TIMEOUT_MS = 20_000
BROWSER_VERIFICATION_TIMEOUT_S = 300

# ---------------------------------------------------------------------------
# Job lifecycle
# ---------------------------------------------------------------------------
JOB_POLL_INTERVAL_S   = 3.0    # seconds between poller ticks
JOB_GENERATE_TIMEOUT_S = 300   # max seconds to wait for Grok to produce a video
JOB_MAX_RETRIES        = 3     # automatic retries on transient failure

# ---------------------------------------------------------------------------
# Worker pool
# ---------------------------------------------------------------------------
WORKER_POOL_SIZE = 1   # Grok allows one generation at a time

# ---------------------------------------------------------------------------
# Downloader
# ---------------------------------------------------------------------------
DOWNLOAD_CHUNK_SIZE   = 8_192   # bytes
DOWNLOAD_MAX_RETRIES  = 3
DOWNLOAD_RETRY_DELAY_S = 2.0

# ---------------------------------------------------------------------------
# Video selectors  (update these if Grok changes its DOM)
# ---------------------------------------------------------------------------
SELECTOR_IMAGINE_INPUT   = "textarea"
SELECTOR_GENERATE_BUTTON = "button[type='submit'], button:has-text('Generate')"
SELECTOR_VIDEO_RESULT    = "video[src], a[download][href$='.mp4']"
SELECTOR_PROGRESS_BAR    = "[role='progressbar'], .progress"
SELECTOR_ERROR_MESSAGE   = "[data-testid='error-message'], .error-banner"

# ---------------------------------------------------------------------------
# Supported file types
# ---------------------------------------------------------------------------
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTENSION = ".mp4"

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
APP_TITLE   = "Grok Video Tool"
APP_VERSION = "1.0.0"
LOG_MAX_LINES = 500
# ---------------------------------------------------------------------------
# Job status
# ---------------------------------------------------------------------------

class JobStatus:

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"

    ALL = {
        PENDING,
        RUNNING,
        DONE,
        FAILED,
        CANCELLED,
    }

    TERMINAL = {
        DONE,
        FAILED,
        CANCELLED,
    }


# ---------------------------------------------------------------------------
# Queue limits
# ---------------------------------------------------------------------------

MAX_QUEUE_SIZE = 100
MAX_CONCURRENT_JOBS = 1
