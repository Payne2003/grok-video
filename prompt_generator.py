"""
prompt_generator.py — Layer 2 + 3:
  - Sinh video prompt từ text chunk
  - Giữ mạch truyện qua context window (chunk trước → chunk hiện tại)

Hỗ trợ 2 engine:
  1. Template-based (offline, nhanh, không cần API)
  2. Claude API  (chất lượng cao, cần key)
"""

from __future__ import annotations

import re
import json
import time
from dataclasses import dataclass
from typing import Callable

from text_chunker import ChunkResult, ChunkPlan


# ════════════════════════════════════════════════════════════════
#  DATA
# ════════════════════════════════════════════════════════════════

@dataclass
class PromptResult:
    chunk_name : str
    chunk_text : str        # text gốc của chunk
    prompt     : str        # video prompt đã sinh
    engine     : str        # "template" | "claude"
    context_used: bool      # có dùng context của chunk trước không


# ════════════════════════════════════════════════════════════════
#  TEMPLATE ENGINE  (offline fallback)
# ════════════════════════════════════════════════════════════════

# Từ khóa cảm xúc / bối cảnh → style hint
_SCENE_HINTS: list[tuple[list[str], str]] = [
    (["đêm", "tối", "bóng tối", "trăng", "sao"],
     "night scene, moonlight, dark atmosphere, cinematic"),
    (["ngày", "sáng", "nắng", "bình minh", "hoàng hôn"],
     "daytime, golden hour lighting, natural light"),
    (["rừng", "cây", "núi", "suối", "thiên nhiên"],
     "forest, nature, lush greenery, scenic"),
    (["làng", "nhà", "phố", "đường", "chợ"],
     "village, traditional architecture, peaceful"),
    (["chiến đấu", "đánh", "tấn công", "bảo vệ", "nguy hiểm"],
     "action scene, dramatic lighting, intense"),
    (["tình yêu", "yêu", "hôn", "ôm", "nhớ"],
     "romantic, soft lighting, emotional"),
    (["buồn", "khóc", "nước mắt", "đau", "mất"],
     "melancholic, moody, emotional depth"),
    (["vui", "cười", "hạnh phúc", "mừng", "lễ"],
     "joyful, vibrant colors, celebratory"),
    (["rồng", "phượng", "tiên", "thần", "ma"],
     "fantasy, mythical, ethereal, magical"),
]

_STYLE_SUFFIX = (
    "cinematic video, 4K quality, smooth motion, "
    "professional lighting, story-driven composition"
)


def _extract_scene_hint(text: str) -> str:
    text_lower = text.lower()
    matched = []
    for keywords, hint in _SCENE_HINTS:
        if any(kw in text_lower for kw in keywords):
            matched.append(hint)
        if len(matched) >= 2:
            break
    return ", ".join(matched) if matched else "cinematic, atmospheric"


def _summarise_for_prompt(text: str, max_words: int = 25) -> str:
    """Rút gọn text thành mô tả ngắn dùng làm prompt."""
    # Lấy câu đầu tiên
    sentences = re.split(r"[.!?]+", text)
    first = sentences[0].strip() if sentences else text

    words = first.split()
    if len(words) > max_words:
        words = words[:max_words]
    return " ".join(words)


def generate_prompt_template(
    chunk: ChunkResult,
    prev_context: str = "",
) -> PromptResult:
    """
    Sinh prompt theo template (không cần API).
    prev_context: mô tả ngắn scene của chunk trước → giữ tính liên tục.
    """
    scene_desc = _summarise_for_prompt(chunk.text)
    hint       = _extract_scene_hint(chunk.text)

    # Prefix liên tục nếu có context chunk trước
    continuity = ""
    if prev_context:
        continuity = f"Continuing from: {prev_context[:60]}. "

    prompt = (
        f"{continuity}"
        f"Scene: {scene_desc}. "
        f"{hint}, {_STYLE_SUFFIX}"
    )

    return PromptResult(
        chunk_name    = chunk.name,
        chunk_text    = chunk.text,
        prompt        = prompt,
        engine        = "template",
        context_used  = bool(prev_context),
    )


# ════════════════════════════════════════════════════════════════
#  CLAUDE API ENGINE
# ════════════════════════════════════════════════════════════════

_CLAUDE_SYSTEM = """Bạn là chuyên gia viết video prompt cho AI video generator (Grok, Sora...).
Nhiệm vụ: nhận 1 đoạn văn truyện ngắn → viết 1 video prompt súc tích, mô tả cảnh quay.

Quy tắc CỨNG:
- Tối đa 40 words
- Bắt đầu bằng mô tả hành động/cảnh vật (không bắt đầu bằng "A video of...")
- Thêm style: cinematic, lighting type, mood, camera movement
- Nếu có [PREV_SCENE], hãy đảm bảo cảnh tiếp nối mượt mà
- Chỉ trả về prompt, KHÔNG giải thích"""

_CLAUDE_USER_TMPL = """[CHUNK_TEXT]
{chunk_text}

[PREV_SCENE]
{prev_scene}

Viết video prompt (tối đa 40 words, tiếng Anh):"""


def generate_prompt_claude(
    chunk        : ChunkResult,
    prev_context : str = "",
    model        : str = "claude-sonnet-4-20250514",
    max_retries  : int = 3,
) -> PromptResult:
    """
    Sinh prompt bằng Claude API.
    Fallback về template nếu API lỗi.
    """
    import requests as req

    user_msg = _CLAUDE_USER_TMPL.format(
        chunk_text = chunk.text[:400],   # giới hạn token
        prev_scene = prev_context[:150] if prev_context else "None (first scene)",
    )

    payload = {
        "model":      model,
        "max_tokens": 120,
        "system":     _CLAUDE_SYSTEM,
        "messages":   [{"role": "user", "content": user_msg}],
    }

    for attempt in range(1, max_retries + 1):
        try:
            resp = req.post(
                "https://api.anthropic.com/v1/messages",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            prompt_text = data["content"][0]["text"].strip()

            return PromptResult(
                chunk_name   = chunk.name,
                chunk_text   = chunk.text,
                prompt       = prompt_text,
                engine       = "claude",
                context_used = bool(prev_context),
            )
        except Exception as e:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                # Fallback về template
                result = generate_prompt_template(chunk, prev_context)
                result.engine = f"template(fallback:{e})"
                return result

    # Không bao giờ tới đây nhưng để type-checker yên tâm
    return generate_prompt_template(chunk, prev_context)


# ════════════════════════════════════════════════════════════════
#  BATCH GENERATOR  (Layer 3: context window)
# ════════════════════════════════════════════════════════════════

def generate_all_prompts(
    plan         : ChunkPlan,
    engine       : str = "template",   # "template" | "claude"
    on_progress  : Callable[[int, int, PromptResult], None] | None = None,
    context_window: int = 1,           # số chunk trước dùng làm context
) -> list[PromptResult]:
    """
    Sinh prompt cho toàn bộ chunk trong plan.

    engine = "template" → offline, nhanh
    engine = "claude"   → gọi API, chất lượng cao

    context_window: số chunk trước đưa vào context để giữ mạch truyện.
                    1 = chỉ dùng chunk liền trước (đủ dùng thực tế).
    """
    results: list[PromptResult] = []
    total = len(plan.chunks)

    for i, chunk in enumerate(plan.chunks):
        # Xây context từ các prompt trước
        prev_context = ""
        if i > 0 and context_window > 0:
            prev_prompts = [
                results[j].prompt
                for j in range(max(0, i - context_window), i)
            ]
            prev_context = " | ".join(prev_prompts)

        if engine == "claude":
            result = generate_prompt_claude(chunk, prev_context)
        else:
            result = generate_prompt_template(chunk, prev_context)

        results.append(result)

        if on_progress:
            on_progress(i + 1, total, result)

    return results


# ════════════════════════════════════════════════════════════════
#  EXPORT TO SCENES FOLDER  (chuẩn bị cho batch_runner)
# ════════════════════════════════════════════════════════════════

def export_scenes(
    results      : list[PromptResult],
    scenes_folder: str,
    image_folder : str | None = None,   # None = text-only mode
) -> list[dict]:
    """
    Tạo cấu trúc thư mục scenes/ theo format batch_runner cần.

    Text mode  (image_folder=None):
        scenes/chunk_001/ prompt.txt
    Image mode (image_folder=str):
        scenes/chunk_001/ prompt.txt + image.jpg (symlink/copy)

    Trả về list[dict] sẵn để truyền thẳng vào batch_runner.run_batch().
    """
    import os, shutil
    os.makedirs(scenes_folder, exist_ok=True)

    scene_dicts = []

    for r in results:
        scene_dir = os.path.join(scenes_folder, r.chunk_name)
        os.makedirs(scene_dir, exist_ok=True)

        # Ghi prompt
        prompt_file = os.path.join(scene_dir, "prompt.txt")
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(r.prompt)

        # Ghi text gốc (debug / reference)
        text_file = os.path.join(scene_dir, "source_text.txt")
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(r.chunk_text)

        # Tìm ảnh nếu có image_folder
        image_path = None
        if image_folder:
            for ext in ("jpg", "jpeg", "png", "webp"):
                for fn in (f"{r.chunk_name}.{ext}", f"image.{ext}"):
                    p = os.path.join(image_folder, fn)
                    if os.path.exists(p):
                        dst = os.path.join(scene_dir, f"image.{ext}")
                        shutil.copy2(p, dst)
                        image_path = dst
                        break
                if image_path:
                    break

        # Build scene dict (format batch_runner)
        scene_dicts.append({
            "row":    r.chunk_name,    # dùng làm display name
            "name":   r.chunk_name,
            "prompt": r.prompt,
            "image":  image_path,
        })

    return scene_dicts


# ════════════════════════════════════════════════════════════════
#  CLI TEST
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from text_chunker import chunk_text

    sample = """
    Ngày xửa ngày xưa, trong một khu rừng rậm rạp ở phía đông dãy núi,
    có một ngôi làng nhỏ tên là Suối Ngọc. Dân làng sống hiền hòa, chăm chỉ
    làm ăn. Thế rồi một ngày, tin đồn về con rồng thức giấc lan khắp nơi.
    Người ta nói rằng mỗi khi rồng thở ra, lửa sẽ thiêu rụi cả cánh rừng.
    Dân làng lo lắng và bàn tán xôn xao. Chàng trai trẻ tên Minh quyết định
    một mình lên đường vào hang rồng để tìm hiểu sự thật.
    """.strip()

    plan    = chunk_text(sample, video_duration_s=6.0)
    results = generate_all_prompts(plan, engine="template",
                                   on_progress=lambda i, t, r:
                                       print(f"  [{i}/{t}] {r.chunk_name}: {r.prompt[:60]}"))
    print(f"\n✅ Sinh {len(results)} prompts xong")