"""
video_merger.py — Layer 4: Ghép các video chunk thành 1 video truyện dài.

Features:
  - Ghép bằng FFmpeg (stream copy, không re-encode → nhanh, không mất chất)
  - Crossfade transition giữa các clip (optional, cần re-encode)
  - Tự detect codec để chọn đúng output container
  - Progress callback
  - Validate từng file trước khi ghép
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import json
import time
from dataclasses import dataclass
from typing import Callable


# ════════════════════════════════════════════════════════════════
#  DATA
# ════════════════════════════════════════════════════════════════

@dataclass
class MergeResult:
    success      : bool
    output_path  : str
    total_clips  : int
    merged_clips : int
    skipped_clips: list[str]    # files bị skip (không tồn tại / quá nhỏ)
    duration_s   : float        # tổng thời lượng output (giây)
    file_size_mb : float
    elapsed_s    : float
    error        : str = ""

    def summary(self) -> str:
        if not self.success:
            return f"❌ Merge thất bại: {self.error}"
        return (
            f"✅ Merge xong: {self.merged_clips}/{self.total_clips} clips\n"
            f"   Output  : {self.output_path}\n"
            f"   Duration: {self.duration_s:.1f}s "
            f"({self.duration_s/60:.1f} phút)\n"
            f"   Size    : {self.file_size_mb:.1f} MB\n"
            f"   Elapsed : {self.elapsed_s:.1f}s\n"
            + (f"   Skipped : {self.skipped_clips}" if self.skipped_clips else "")
        )


# ════════════════════════════════════════════════════════════════
#  FFMPEG UTILS
# ════════════════════════════════════════════════════════════════

def _find_ffmpeg() -> str:
    """Tìm ffmpeg trong PATH hoặc thư mục phổ biến trên Windows."""
    import shutil
    found = shutil.which("ffmpeg")
    if found:
        return found
    candidates = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\tools\ffmpeg\bin\ffmpeg.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError(
        "Không tìm thấy ffmpeg. "
        "Tải tại https://ffmpeg.org/download.html và thêm vào PATH."
    )


def _probe_duration(path: str, ffprobe: str = "ffprobe") -> float:
    """Dùng ffprobe để lấy duration (giây) của video."""
    try:
        result = subprocess.run(
            [
                ffprobe, "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                path,
            ],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:
        return 0.0


def _probe_video_codec(path: str, ffprobe: str = "ffprobe") -> str:
    try:
        result = subprocess.run(
            [
                ffprobe, "-v", "quiet",
                "-select_streams", "v:0",
                "-print_format", "json",
                "-show_streams",
                path,
            ],
            capture_output=True, text=True, timeout=15
        )
        data    = json.loads(result.stdout)
        streams = data.get("streams", [])
        return streams[0].get("codec_name", "h264") if streams else "h264"
    except Exception:
        return "h264"


def _validate_video(path: str, min_size_bytes: int = 10_000) -> bool:
    """Kiểm tra file video có hợp lệ không."""
    if not os.path.exists(path):
        return False
    if os.path.getsize(path) < min_size_bytes:
        return False
    return True


# ════════════════════════════════════════════════════════════════
#  MERGE: STREAM COPY (nhanh, không re-encode)
# ════════════════════════════════════════════════════════════════

def merge_stream_copy(
    video_files   : list[str],
    output_path   : str,
    on_progress   : Callable[[str], None] | None = None,
    ffmpeg_path   : str | None = None,
) -> MergeResult:
    """
    Ghép nhanh bằng concat demuxer (stream copy, không re-encode).
    Yêu cầu: tất cả clips phải cùng codec, resolution, fps.
    → Phù hợp với output từ Grok (thường đều là mp4/h264).
    """
    ffmpeg  = ffmpeg_path or _find_ffmpeg()
    start   = time.time()
    skipped = []

    log = on_progress or print

    # Validate & lọc
    valid_files = []
    for f in video_files:
        if _validate_video(f):
            valid_files.append(f)
        else:
            skipped.append(os.path.basename(f))
            log(f"⚠️  Skip (không hợp lệ): {f}")

    if not valid_files:
        return MergeResult(False, output_path, len(video_files), 0,
                           skipped, 0.0, 0.0, 0.0,
                           "Không có video hợp lệ nào để ghép")

    log(f"🎬 Bắt đầu ghép {len(valid_files)} clips → {output_path}")

    # Tạo file list tạm
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                     delete=False, encoding="utf-8") as tmp:
        for f in valid_files:
            # FFmpeg concat cần path tuyệt đối với dấu ' escape
            abs_path = os.path.abspath(f).replace("'", r"\'")
            tmp.write(f"file '{abs_path}'\n")
        list_path = tmp.name

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [
        ffmpeg, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-c", "copy",          # stream copy: nhanh, không mất chất
        output_path,
    ]

    log(f"▶ FFmpeg: {' '.join(cmd[-4:])}")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,   # 10 phút max
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-500:])
    except Exception as e:
        os.unlink(list_path)
        return MergeResult(False, output_path, len(video_files), 0,
                           skipped, 0.0, 0.0, time.time() - start, str(e))
    finally:
        try: os.unlink(list_path)
        except: pass

    # Đo kết quả
    duration  = _probe_duration(output_path)
    size_mb   = os.path.getsize(output_path) / (1024 * 1024)
    elapsed   = time.time() - start

    log(f"✅ Ghép xong | {duration:.1f}s | {size_mb:.1f} MB | {elapsed:.1f}s")

    return MergeResult(
        success       = True,
        output_path   = output_path,
        total_clips   = len(video_files),
        merged_clips  = len(valid_files),
        skipped_clips = skipped,
        duration_s    = round(duration, 2),
        file_size_mb  = round(size_mb, 2),
        elapsed_s     = round(elapsed, 2),
    )


# ════════════════════════════════════════════════════════════════
#  MERGE: CROSSFADE  (re-encode, mượt hơn nhưng chậm hơn)
# ════════════════════════════════════════════════════════════════

def merge_crossfade(
    video_files     : list[str],
    output_path     : str,
    fade_duration   : float = 0.5,      # giây
    on_progress     : Callable[[str], None] | None = None,
    ffmpeg_path     : str | None = None,
) -> MergeResult:
    """
    Ghép với crossfade transition giữa các clip.
    Chậm hơn stream copy do cần re-encode.
    fade_duration: thời lượng fade (giây).
    """
    ffmpeg = ffmpeg_path or _find_ffmpeg()
    start  = time.time()
    log    = on_progress or print
    skipped = []

    valid_files = []
    for f in video_files:
        if _validate_video(f):
            valid_files.append(f)
        else:
            skipped.append(os.path.basename(f))

    if len(valid_files) < 2:
        # Ít hơn 2 clip → dùng stream copy thay
        log("⚠️  Ít hơn 2 clips hợp lệ — fallback về stream copy")
        return merge_stream_copy(valid_files, output_path, on_progress, ffmpeg_path)

    log(f"🎬 Crossfade merge: {len(valid_files)} clips | fade={fade_duration}s")

    # Lấy duration từng clip để tính offset
    durations = [_probe_duration(f) for f in valid_files]

    # Xây ffmpeg filter_complex cho xfade
    # Ref: https://ffmpeg.org/ffmpeg-filters.html#xfade
    inputs = []
    for f in valid_files:
        inputs += ["-i", f]

    filter_parts = []
    offset      = 0.0
    prev_label  = "[0:v]"

    for i in range(1, len(valid_files)):
        offset += durations[i - 1] - fade_duration
        out_label = f"[v{i}]" if i < len(valid_files) - 1 else "[vout]"
        cur_label = f"[{i}:v]"
        filter_parts.append(
            f"{prev_label}{cur_label}xfade=transition=fade:"
            f"duration={fade_duration}:offset={offset:.3f}{out_label}"
        )
        prev_label = out_label

    filter_complex = "; ".join(filter_parts)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = (
        [ffmpeg, "-y"]
        + inputs
        + [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            output_path,
        ]
    )

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-500:])
    except Exception as e:
        log(f"❌ Crossfade lỗi: {e} — fallback stream copy")
        return merge_stream_copy(valid_files, output_path, on_progress, ffmpeg_path)

    duration = _probe_duration(output_path)
    size_mb  = os.path.getsize(output_path) / (1024 * 1024)
    elapsed  = time.time() - start

    log(f"✅ Crossfade xong | {duration:.1f}s | {size_mb:.1f} MB | {elapsed:.1f}s")

    return MergeResult(
        success       = True,
        output_path   = output_path,
        total_clips   = len(video_files),
        merged_clips  = len(valid_files),
        skipped_clips = skipped,
        duration_s    = round(duration, 2),
        file_size_mb  = round(size_mb, 2),
        elapsed_s     = round(elapsed, 2),
    )


# ════════════════════════════════════════════════════════════════
#  AUTO COLLECT VIDEO FILES  (từ output folder của batch_runner)
# ════════════════════════════════════════════════════════════════

def collect_video_files(
    output_folder : str,
    prefix        : str = "chunk_",
    extensions    : tuple = (".mp4", ".webm", ".mov"),
) -> list[str]:
    """
    Thu thập và sắp xếp video files từ output_folder.
    Chỉ lấy files có prefix (vd chunk_001.mp4, chunk_002.mp4...).
    """
    files = []
    if not os.path.exists(output_folder):
        return files

    for fn in sorted(os.listdir(output_folder)):
        if fn.startswith(prefix):
            ext = os.path.splitext(fn)[1].lower()
            if ext in extensions:
                files.append(os.path.join(output_folder, fn))

    return files


# ════════════════════════════════════════════════════════════════
#  CLI TEST
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python video_merger.py <output_folder> <output.mp4> [crossfade]")
        sys.exit(1)

    folder  = sys.argv[1]
    out     = sys.argv[2]
    mode    = sys.argv[3] if len(sys.argv) > 3 else "copy"

    files = collect_video_files(folder)
    print(f"Tìm thấy {len(files)} video files:")
    for f in files:
        print(f"  {f}")

    if not files:
        print("Không có file nào!"); sys.exit(1)

    if mode == "crossfade":
        result = merge_crossfade(files, out, fade_duration=0.5)
    else:
        result = merge_stream_copy(files, out)

    print(result.summary())