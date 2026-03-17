"""
text_chunker.py — Layer 1: Chia text dài thành các chunk theo thời lượng video.

Thuật toán:
  - Tốc độ đọc narration: ~150 words/phút (có thể tuỉnh)
  - Overlap N words giữa các chunk liên tiếp → chuyển cảnh mượt
  - Ưu tiên cắt tại dấu câu (., !, ?) thay vì giữa câu

Output: list[ChunkResult]
"""

from dataclasses import dataclass, field
from typing import Iterator
import re


# ════════════════════════════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════════════════════════════

WORDS_PER_MINUTE  = 150     # tốc độ đọc narration thực tế
OVERLAP_WORDS     = 5       # số words overlap giữa 2 chunk liên tiếp
MIN_WORDS_CHUNK   = 8       # chunk tối thiểu (tránh quá ngắn)


# ════════════════════════════════════════════════════════════════
#  DATA CLASSES
# ════════════════════════════════════════════════════════════════

@dataclass
class ChunkResult:
    index       : int           # 0-based
    name        : str           # "chunk_001"
    text        : str           # nội dung chunk (có overlap)
    word_count  : int
    duration_s  : float         # thời lượng ước tính (giây)
    overlap_prev: int           # số words overlap với chunk trước
    overlap_next: int           # số words overlap với chunk sau


@dataclass
class ChunkPlan:
    chunks      : list[ChunkResult]
    total_words : int
    total_duration_s: float
    video_duration_s: float     # thời lượng 1 video (input)
    overlap_words: int

    @property
    def total_duration_min(self) -> float:
        return self.total_duration_s / 60

    def summary(self) -> str:
        lines = [
            f"📊 Text Chunking Plan",
            f"   Tổng words   : {self.total_words}",
            f"   Số chunk     : {len(self.chunks)}",
            f"   Duration/video: {self.video_duration_s}s",
            f"   Overlap       : {self.overlap_words} words",
            f"   Tổng thời gian ước tính: {self.total_duration_min:.1f} phút",
            f"",
        ]
        for c in self.chunks:
            lines.append(
                f"   [{c.name}] {c.word_count} words "
                f"≈ {c.duration_s:.1f}s | overlap_prev={c.overlap_prev}"
            )
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
#  TOKENISER
# ════════════════════════════════════════════════════════════════

def _tokenise(text: str) -> list[str]:
    """Tách text thành list words, giữ nguyên dấu câu liền word."""
    # Giữ dấu câu gắn với word để biết điểm cắt câu
    return [w for w in re.split(r"\s+", text.strip()) if w]


def _is_sentence_end(word: str) -> bool:
    """Trả True nếu word kết thúc câu (dấu . ! ?)."""
    return bool(re.search(r"[.!?][\"')\]]*$", word))


# ════════════════════════════════════════════════════════════════
#  CORE CHUNKER
# ════════════════════════════════════════════════════════════════

def chunk_text(
    text              : str,
    video_duration_s  : float = 6.0,
    words_per_minute  : int   = WORDS_PER_MINUTE,
    overlap_words     : int   = OVERLAP_WORDS,
    min_words         : int   = MIN_WORDS_CHUNK,
) -> ChunkPlan:
    """
    Chia text thành các chunk sao cho mỗi chunk vừa với 1 video
    có thời lượng `video_duration_s` giây.

    Cắt ưu tiên tại cuối câu (dấu . ! ?) trong vùng ±20% target_words.

    Args:
        text              : Nội dung truyện dài
        video_duration_s  : Thời lượng 1 video (giây), vd 6
        words_per_minute  : Tốc độ đọc narration (default 150)
        overlap_words     : Số words overlap giữa 2 chunk liên tiếp
        min_words         : Số words tối thiểu mỗi chunk

    Returns:
        ChunkPlan
    """
    words = _tokenise(text)
    if not words:
        return ChunkPlan([], 0, 0.0, video_duration_s, overlap_words)

    # Số words target cho 1 chunk
    words_per_second = words_per_minute / 60.0
    target_words     = max(min_words, int(words_per_second * video_duration_s))

    # Vùng tìm điểm cắt câu: target ± 20%
    search_range = max(3, int(target_words * 0.20))

    chunks: list[ChunkResult] = []
    pos    = 0
    total  = len(words)

    while pos < total:
        # Điểm kết thúc lý tưởng
        ideal_end = pos + target_words

        if ideal_end >= total:
            # Chunk cuối — lấy hết
            end = total
        else:
            # Tìm điểm cắt câu gần nhất quanh ideal_end
            end = _find_sentence_break(words, ideal_end, search_range, total)

        chunk_words = words[pos:end]
        if len(chunk_words) < min_words and chunks:
            # Chunk quá ngắn → nhập vào chunk trước
            prev       = chunks[-1]
            merged_w   = _tokenise(prev.text) + chunk_words
            merged_txt = " ".join(merged_w)
            dur        = len(merged_w) / words_per_second
            chunks[-1] = ChunkResult(
                index        = prev.index,
                name         = prev.name,
                text         = merged_txt,
                word_count   = len(merged_w),
                duration_s   = round(dur, 2),
                overlap_prev = prev.overlap_prev,
                overlap_next = 0,
            )
            break

        text_chunk  = " ".join(chunk_words)
        duration_s  = len(chunk_words) / words_per_second
        overlap_prev = min(overlap_words, pos) if chunks else 0

        idx = len(chunks)
        chunks.append(ChunkResult(
            index        = idx,
            name         = f"chunk_{idx+1:03d}",
            text         = text_chunk,
            word_count   = len(chunk_words),
            duration_s   = round(duration_s, 2),
            overlap_prev = overlap_prev,
            overlap_next = 0,   # fill below
        ))

        # Bước tiến: lùi lại overlap_words để tạo overlap với chunk tiếp theo
        pos = end - overlap_words
        if pos <= (end - target_words // 2):
            # Tránh vòng lặp vô hạn nếu overlap quá lớn
            pos = end

    # Điền overlap_next
    for i in range(len(chunks) - 1):
        chunks[i].overlap_next = chunks[i+1].overlap_prev

    total_dur = sum(c.duration_s for c in chunks)

    return ChunkPlan(
        chunks           = chunks,
        total_words      = total,
        total_duration_s = round(total_dur, 2),
        video_duration_s = video_duration_s,
        overlap_words    = overlap_words,
    )


def _find_sentence_break(words: list[str], ideal: int,
                          search: int, total: int) -> int:
    """
    Tìm điểm kết thúc câu tốt nhất gần `ideal`.
    Ưu tiên: ngay tại ideal, mở rộng dần ra ngoài trong vùng ±search.
    Fallback: trả về ideal nếu không tìm thấy.
    """
    # Tìm về phía sau ideal trước (không để câu quá ngắn)
    for delta in range(0, search + 1):
        for sign in (1, -1):
            idx = ideal + sign * delta
            if 0 < idx <= total:
                if _is_sentence_end(words[idx - 1]):
                    return idx
    return min(ideal, total)


# ════════════════════════════════════════════════════════════════
#  CONVENIENCE
# ════════════════════════════════════════════════════════════════

def chunk_text_from_file(
    filepath         : str,
    video_duration_s : float = 6.0,
    **kwargs,
) -> ChunkPlan:
    text = open(filepath, encoding="utf-8").read()
    return chunk_text(text, video_duration_s=video_duration_s, **kwargs)


# ════════════════════════════════════════════════════════════════
#  CLI TEST
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    sample = """
    Ngày xửa ngày xưa, trong một khu rừng rậm rạp ở phía đông dãy núi,
    có một ngôi làng nhỏ tên là Suối Ngọc. Dân làng sống hiền hòa, chăm chỉ
    làm ăn, trồng lúa và hái thuốc. Mỗi buổi sáng sớm, tiếng gà gáy vang lên
    báo hiệu một ngày mới bắt đầu. Trẻ em chạy ra đồng chơi đùa, còn người lớn
    thì cặm cụi với công việc của mình. Cuộc sống tuy đơn giản nhưng đầy ắp
    niềm vui và tình thân ái. Thế rồi một ngày, có tin đồn rằng một con rồng
    khổng lồ đã thức giấc sau ngàn năm ngủ say trong hang động sâu nhất của
    dãy núi. Người ta nói rằng mỗi khi rồng thở ra, lửa sẽ thiêu rụi cả cánh
    rừng. Dân làng lo lắng và bàn tán xôn xao. Hội đồng trưởng lão quyết định
    triệu tập một cuộc họp khẩn cấp để tìm cách đối phó với mối hiểm họa này.
    Trong số những người tham dự, có một chàng trai trẻ tên là Minh. Cậu chỉ
    mới mười tám tuổi nhưng đã nổi tiếng khắp vùng vì lòng dũng cảm và trí thông minh.
    """.strip()

    plan = chunk_text(sample, video_duration_s=6.0)
    print(plan.summary())