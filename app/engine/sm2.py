"""SM-2 间隔重复算法

基于 SuperMemo SM-2 算法实现:
- quality: 0~5  (0=完全忘记, 5=完美回忆)
- ease_factor: 难度系数 (>=1.3)
- interval: 复习间隔 (天)
"""

from dataclasses import dataclass


@dataclass
class ReviewResult:
    """一次复习的计算结果"""
    ease_factor: float      # 新的难度系数
    interval_days: int      # 下次复习间隔 (天)
    repetitions: int        # 连续正确次数
    next_review_at: str     # 下次复习日期 (ISO)


def sm2_review(quality: int, prev_ease: float = 2.5,
               prev_interval: int = 0, prev_reps: int = 0) -> ReviewResult:
    """SM-2 算法核心计算

    Args:
        quality:     本次复习质量 (0~5)
        prev_ease:   之前的难度系数 (默认 2.5)
        prev_interval: 上次间隔天数 (默认 0 = 新词)
        prev_reps:   之前的连续正确次数 (默认 0)

    Returns:
        ReviewResult: 新的学习参数

    Quality 说明:
        5 — 完美反应
        4 — 正确，但有犹豫
        3 — 正确，但回忆困难
        2 — 错误，但正确答案似乎很容易回忆
        1 — 错误，但正确答案能想起来
        0 — 完全忘记
    """
    # 容错
    if quality < 0:
        quality = 0
    if quality > 5:
        quality = 5

    # ── 质量低于 3: 忘记 → 重置 ──
    if quality < 3:
        return ReviewResult(
            ease_factor=prev_ease,
            interval_days=1,
            repetitions=0,
            next_review_at="",
        )

    # ── 计算新的 ease factor ──
    new_ease = prev_ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if new_ease < 1.3:
        new_ease = 1.3

    # ── 根据连续正确次数计算间隔 ──
    if prev_reps == 0:
        new_interval = 1          # 第1次正确 → 1天后
    elif prev_reps == 1:
        new_interval = 6          # 第2次正确 → 6天后
    else:
        new_interval = round(prev_interval * new_ease)   # 之后: 前间隔 × 难度系数
        new_interval = min(new_interval, 365)             # 最长不超过1年

    new_reps = prev_reps + 1

    return ReviewResult(
        ease_factor=round(new_ease, 2),
        interval_days=new_interval,
        repetitions=new_reps,
        next_review_at="",   # 调用方补日期
    )
