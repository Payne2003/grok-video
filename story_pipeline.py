"""
story_pipeline.py — Orchestrator 4 tầng:

  Layer 1: text_chunker     → chia text thành chunks theo thời lượng
  Layer 2: prompt_generator → sinh video prompt cho từng chunk
  Layer 3: batch_runner     → generate video song song (nhiều accounts)
  Layer 4: video_merger     → ghép tất cả thành 1 video truyện dài

Cách dùng (code):
    pipeline = StoryPipeline(config)
    pipeline.run(on_progress=my_callback)

Cách dùng (CLI):
    python story_pipeline.py --text story.txt --output out/ --duration 6
"""

from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from text_chunker     import chunk_text, ChunkPlan
from prompt_generator import generate_all_prompts, PromptResult
from video_merger     import merge_stream_copy, merge_crossfade, collect_video_files, MergeResult
from batch_runner     import BatchCallbacks, run_batch, load_accounts


# ════════════════════════════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════════════════════════════

@dataclass
class PipelineConfig:
    # INPUT
    text              : str = ""          # truyện dài (raw text)
    text_file         : str = ""          # hoặc đường dẫn file .txt

    # OUTPUT
    output_folder     : str = r"D:\grok-video-tool\story_output"
    final_video_name  : str = "story_final.mp4"

    # CHUNKING
    video_duration_s  : float = 6.0       # thời lượng mỗi video (giây)
    overlap_words     : int   = 5         # overlap words giữa chunks
    words_per_minute  : int   = 150       # tốc độ đọc narration

    # PROMPT ENGINE
    prompt_engine     : str   = "template"  # "template" | "claude"
    context_window    : int   = 1           # số chunk trước dùng làm context

    # VIDEO GENERATION
    accounts          : list | None = None  # None → tự load từ ACCOUNTS_FOLDER

    # MERGE
    merge_mode        : str   = "copy"      # "copy" | "crossfade"
    fade_duration     : float = 0.5         # giây (chỉ dùng khi crossfade)

    # CONTROL
    skip_generation   : bool  = False  # True → bỏ qua bước generate, chỉ merge
    skip_merge        : bool  = False  # True → generate xong, không merge

    @property
    def chunks_folder(self) -> str:
        return os.path.join(self.output_folder, "chunks")

    @property
    def videos_folder(self) -> str:
        return os.path.join(self.output_folder, "videos")

    @property
    def final_video_path(self) -> str:
        return os.path.join(self.output_folder, self.final_video_name)

    @property
    def plan_file(self) -> str:
        return os.path.join(self.output_folder, "pipeline_plan.json")

    @property
    def report_file(self) -> str:
        return os.path.join(self.output_folder, "pipeline_report.json")


# ════════════════════════════════════════════════════════════════
#  PROGRESS CALLBACKS
# ════════════════════════════════════════════════════════════════

@dataclass
class PipelineCallbacks:
    """Callbacks nhận sự kiện từ pipeline (thread-safe, gọi từ worker thread)."""
    on_log            : Callable[[str], None]              = field(default=print)
    on_stage          : Callable[[str, str], None]         = field(
        default=lambda stage, msg: print(f"[{stage}] {msg}")
    )
    on_chunk_progress : Callable[[int, int], None]         = field(
        default=lambda done, total: None
    )
    on_video_row      : Callable[[int, str], None]         = field(
        default=lambda row, status: None
    )
    on_stats          : Callable[[int,int,int,int], None]  = field(
        default=lambda t,r,d,e: None
    )
    on_done           : Callable[[dict], None]             = field(
        default=lambda report: None
    )
    is_cancelled      : Callable[[], bool]                 = field(
        default=lambda: False
    )


# ════════════════════════════════════════════════════════════════
#  PIPELINE
# ════════════════════════════════════════════════════════════════

class StoryPipeline:

    def __init__(self, config: PipelineConfig):
        self.cfg = config
        self._report = {}

    # ─────────────────────────────────────────────────────────────
    def run(self, cb: PipelineCallbacks | None = None) -> dict:
        """
        Chạy toàn bộ pipeline. Trả về report dict.
        Thường được gọi trong worker thread.
        """
        cb    = cb or PipelineCallbacks()
        cfg   = self.cfg
        start = time.time()

        os.makedirs(cfg.output_folder, exist_ok=True)
        os.makedirs(cfg.chunks_folder, exist_ok=True)
        os.makedirs(cfg.videos_folder, exist_ok=True)

        report = {
            "started_at"   : datetime.now().isoformat(),
            "config"       : {
                "video_duration_s": cfg.video_duration_s,
                "prompt_engine"   : cfg.prompt_engine,
                "merge_mode"      : cfg.merge_mode,
            },
            "stages"       : {},
        }

        try:
            # ══ STAGE 1: LOAD TEXT ════════════════════════════════
            cb.on_stage("1/4", "Đọc text...")
            text = self._load_text()
            cb.on_log(f"📖 Text: {len(text.split())} words")
            if cb.is_cancelled(): return self._abort(report, "cancelled")

            # ══ STAGE 2: CHUNK TEXT ═══════════════════════════════
            cb.on_stage("1/4", "Chia text thành chunks...")
            plan = chunk_text(
                text,
                video_duration_s = cfg.video_duration_s,
                overlap_words    = cfg.overlap_words,
                words_per_minute = cfg.words_per_minute,
            )
            cb.on_log(f"✂️  {len(plan.chunks)} chunks | "
                      f"~{plan.total_duration_min:.1f} phút tổng")
            report["stages"]["chunking"] = {
                "total_chunks"   : len(plan.chunks),
                "total_words"    : plan.total_words,
                "total_duration" : plan.total_duration_s,
            }
            self._save_plan(plan)
            if cb.is_cancelled(): return self._abort(report, "cancelled")

            # ══ STAGE 3: GENERATE PROMPTS ═════════════════════════
            cb.on_stage("2/4", f"Sinh prompts ({cfg.prompt_engine})...")

            def _prompt_progress(done, total, result):
                cb.on_log(f"  [{done}/{total}] {result.chunk_name}: "
                          f"{result.prompt[:55]}...")
                cb.on_chunk_progress(done, total)

            prompt_results = generate_all_prompts(
                plan,
                engine         = cfg.prompt_engine,
                on_progress    = _prompt_progress,
                context_window = cfg.context_window,
            )
            report["stages"]["prompts"] = {
                "count" : len(prompt_results),
                "engine": cfg.prompt_engine,
            }
            self._save_prompts(prompt_results)
            if cb.is_cancelled(): return self._abort(report, "cancelled")

            # ══ STAGE 4: GENERATE VIDEOS ══════════════════════════
            if not cfg.skip_generation:
                cb.on_stage("3/4", "Generate videos...")

                # Xây scene dicts cho batch_runner
                scenes = self._build_scenes(prompt_results)
                cb.on_log(f"🎬 {len(scenes)} scenes → {cfg.videos_folder}")

                batch_cb = BatchCallbacks(
                    on_row_update = cb.on_video_row,
                    on_log        = cb.on_log,
                    on_stats      = cb.on_stats,
                    on_status_bar = lambda ic, msg: cb.on_stage("3/4", msg),
                    on_done       = lambda: None,   # handled below
                    is_cancelled  = cb.is_cancelled,
                )

                run_batch(
                    scenes        = scenes,
                    output_folder = cfg.videos_folder,
                    cb            = batch_cb,
                    accounts      = cfg.accounts,
                )

                report["stages"]["generation"] = {
                    "scenes": len(scenes),
                    "output": cfg.videos_folder,
                }
            else:
                cb.on_log("⏩ Bỏ qua bước generate (skip_generation=True)")

            if cb.is_cancelled(): return self._abort(report, "cancelled")

            # ══ STAGE 5: MERGE ════════════════════════════════════
            if not cfg.skip_merge:
                cb.on_stage("4/4", "Ghép video...")

                video_files = collect_video_files(
                    cfg.videos_folder, prefix="chunk_"
                )
                cb.on_log(f"📁 Tìm thấy {len(video_files)} video files")

                if not video_files:
                    cb.on_log("⚠️  Không có video để ghép!")
                    report["stages"]["merge"] = {"error": "no_videos"}
                else:
                    if cfg.merge_mode == "crossfade":
                        merge_result = merge_crossfade(
                            video_files,
                            cfg.final_video_path,
                            fade_duration = cfg.fade_duration,
                            on_progress   = cb.on_log,
                        )
                    else:
                        merge_result = merge_stream_copy(
                            video_files,
                            cfg.final_video_path,
                            on_progress = cb.on_log,
                        )

                    cb.on_log(merge_result.summary())
                    report["stages"]["merge"] = {
                        "success"      : merge_result.success,
                        "output"       : merge_result.output_path,
                        "duration_s"   : merge_result.duration_s,
                        "duration_min" : round(merge_result.duration_s / 60, 2),
                        "size_mb"      : merge_result.file_size_mb,
                        "merged_clips" : merge_result.merged_clips,
                        "skipped"      : merge_result.skipped_clips,
                    }
            else:
                cb.on_log("⏩ Bỏ qua bước merge (skip_merge=True)")

        except Exception as e:
            report["error"] = str(e)
            cb.on_log(f"❌ Pipeline lỗi: {e}")
            import traceback
            cb.on_log(traceback.format_exc())

        # ══ FINALIZE ══════════════════════════════════════════════
        elapsed = time.time() - start
        report["elapsed_s"]    = round(elapsed, 2)
        report["elapsed_min"]  = round(elapsed / 60, 2)
        report["finished_at"]  = datetime.now().isoformat()

        self._save_report(report)
        cb.on_stage("✅", f"Pipeline hoàn thành | {elapsed:.0f}s")
        cb.on_done(report)

        return report

    # ─────────────────────────────────────────────────────────────
    #  PRIVATE HELPERS
    # ─────────────────────────────────────────────────────────────

    def _load_text(self) -> str:
        if self.cfg.text_file:
            return open(self.cfg.text_file, encoding="utf-8").read()
        return self.cfg.text

    def _build_scenes(self, prompts: list[PromptResult]) -> list[dict]:
        """Chuyển PromptResult → scene dicts cho batch_runner."""
        scenes = []
        for i, r in enumerate(prompts):
            scenes.append({
                "row"   : i,
                "name"  : r.chunk_name,
                "prompt": r.prompt,
                "image" : None,    # text→video mode
            })
        return scenes

    def _save_plan(self, plan: ChunkPlan):
        path = self.cfg.plan_file
        data = {
            "total_words"    : plan.total_words,
            "total_chunks"   : len(plan.chunks),
            "total_duration" : plan.total_duration_s,
            "chunks": [
                {
                    "name"        : c.name,
                    "text"        : c.text,
                    "word_count"  : c.word_count,
                    "duration_s"  : c.duration_s,
                    "overlap_prev": c.overlap_prev,
                }
                for c in plan.chunks
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_prompts(self, results: list[PromptResult]):
        """Lưu prompts vào chunks_folder (1 subfolder per chunk)."""
        import shutil
        for r in results:
            d = os.path.join(self.cfg.chunks_folder, r.chunk_name)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "prompt.txt"), "w", encoding="utf-8") as f:
                f.write(r.prompt)
            with open(os.path.join(d, "source_text.txt"), "w", encoding="utf-8") as f:
                f.write(r.chunk_text)

    def _save_report(self, report: dict):
        with open(self.cfg.report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _abort(report: dict, reason: str) -> dict:
        report["aborted"] = reason
        return report


# ════════════════════════════════════════════════════════════════
#  CLI
# ════════════════════════════════════════════════════════════════

def _cli():
    import argparse

    parser = argparse.ArgumentParser(
        description="Story Pipeline: long text → video chunks → merged video"
    )
    parser.add_argument("--text",     help="File .txt chứa truyện dài")
    parser.add_argument("--output",   default=r"D:\grok-video-tool\story_output",
                        help="Thư mục output")
    parser.add_argument("--duration", type=float, default=6.0,
                        help="Thời lượng mỗi video (giây), default=6")
    parser.add_argument("--overlap",  type=int, default=5,
                        help="Overlap words, default=5")
    parser.add_argument("--engine",   default="template",
                        choices=["template", "claude"],
                        help="Prompt engine")
    parser.add_argument("--merge",    default="copy",
                        choices=["copy", "crossfade"],
                        help="Merge mode")
    parser.add_argument("--plan-only", action="store_true",
                        help="Chỉ hiển thị plan, không generate")
    parser.add_argument("--merge-only", action="store_true",
                        help="Chỉ merge (bỏ qua generate)")
    args = parser.parse_args()

    if not args.text:
        parser.print_help(); return

    cfg = PipelineConfig(
        text_file         = args.text,
        output_folder     = args.output,
        video_duration_s  = args.duration,
        overlap_words     = args.overlap,
        prompt_engine     = args.engine,
        merge_mode        = args.merge,
        skip_generation   = args.plan_only or args.merge_only,
        skip_merge        = args.plan_only,
    )

    if args.plan_only:
        # Chỉ preview plan
        from text_chunker     import chunk_text
        from prompt_generator import generate_all_prompts
        text = open(args.text, encoding="utf-8").read()
        plan = chunk_text(text, video_duration_s=args.duration,
                          overlap_words=args.overlap)
        print(plan.summary())
        print("\n--- PROMPTS PREVIEW ---")
        results = generate_all_prompts(plan, engine=args.engine)
        for r in results:
            print(f"\n[{r.chunk_name}] ({r.engine})")
            print(f"  TEXT  : {r.chunk_text[:80]}...")
            print(f"  PROMPT: {r.prompt}")
        return

    pipeline = StoryPipeline(cfg)
    report   = pipeline.run()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()