"""单词和学习记录的 CRUD 操作"""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
import sqlite3

from loguru import logger


class WordRepository:
    """单词库数据访问层"""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ── 单词 CRUD ──────────────────────────────────────────

    def add_word(self, word: str, translation: str = "",
                 phonetic_uk: str = "", phonetic_us: str = "",
                 pos: str = "", level: str = "") -> int:
        """新增单词，返回 word_id"""
        sql = """INSERT OR IGNORE INTO words (word, translation, phonetic_uk, phonetic_us, pos, level)
                 VALUES (?, ?, ?, ?, ?, ?)"""
        with self._connect() as conn:
            cur = conn.execute(sql, (word, translation, phonetic_uk, phonetic_us, pos, level))
            conn.commit()
            if cur.rowcount == 0:
                row = conn.execute("SELECT id FROM words WHERE word = ?", (word,)).fetchone()
                return row["id"]
            return cur.lastrowid

    def update_word(self, word_id: int, **kwargs) -> None:
        """更新单词字段，仅更新传入的键"""
        allowed = {"translation", "phonetic_uk", "phonetic_us", "pos", "level"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return
        updates["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [word_id]
        sql = f"UPDATE words SET {sets} WHERE id = ?"
        with self._connect() as conn:
            conn.execute(sql, vals)
            conn.commit()

    def delete_word(self, word_id: int) -> None:
        """删除单词 (级联删除例句和学习记录)"""
        with self._connect() as conn:
            conn.execute("DELETE FROM words WHERE id = ?", (word_id,))
            conn.commit()

    def get_word(self, word_id: int) -> Optional[dict]:
        """按 id 查询单词"""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM words WHERE id = ?", (word_id,)).fetchone()
            return dict(row) if row else None

    def find_word(self, word: str) -> Optional[dict]:
        """精确查找单词"""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM words WHERE word = ?", (word,)).fetchone()
            return dict(row) if row else None

    def search_words(self, keyword: str = "", limit: int = 100,
                     level: str = "") -> list[dict]:
        """模糊搜索单词，支持等级筛选，按等级排序(同等级管理顺序)再按单词"""
        with self._connect() as conn:
            conditions = []
            params = []
            if keyword:
                conditions.append("w.word LIKE ?")
                params.append(f"%{keyword}%")
            if level:
                conditions.append("w.level = ?")
                params.append(level)

            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            sql = f"""SELECT w.*, COALESCE(r.repetitions, 0) as review_count,
                             r.last_quality
                      FROM words w
                      LEFT JOIN word_levels l ON w.level = l.name
                      LEFT JOIN reviews r ON r.word_id = w.id
                      {where}
                      ORDER BY l.sort_order NULLS LAST, w.word
                      LIMIT ?"""
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def count_words(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]

    # ── 例句 CRUD ──────────────────────────────────────────

    def add_example(self, word_id: int, sentence_en: str,
                    sentence_cn: str = "", audio_filename: str = "",
                    source: str = "manual") -> int:
        sql = """INSERT INTO examples (word_id, sentence_en, sentence_cn, audio_filename, source)
                 VALUES (?, ?, ?, ?, ?)"""
        with self._connect() as conn:
            cur = conn.execute(sql, (word_id, sentence_en, sentence_cn, audio_filename, source))
            conn.commit()
            return cur.lastrowid

    def get_examples(self, word_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM examples WHERE word_id = ? ORDER BY id", (word_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_examples(self, word_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM examples WHERE word_id = ?", (word_id,))
            conn.commit()

    # ── 学习记录 / SM-2 ────────────────────────────────────

    def get_or_create_review(self, word_id: int) -> dict:
        """获取单词的学习记录，没有则创建一条默认的"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reviews WHERE word_id = ?", (word_id,)
            ).fetchone()
            if row:
                return dict(row)
            conn.execute(
                "INSERT INTO reviews (word_id) VALUES (?)", (word_id,)
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM reviews WHERE word_id = ?", (word_id,)
            ).fetchone()
            return dict(row)

    def update_review(self, word_id: int, ease_factor: float,
                      interval_days: int, repetitions: int,
                      quality: int) -> None:
        """更新 SM-2 学习记录 (不存在则插入)"""
        interval_days = min(interval_days, 365)  # 最长间隔不超过1年
        next_date = date.today() + timedelta(days=interval_days)
        now = datetime.now().isoformat()
        sql = """INSERT INTO reviews (word_id, ease_factor, interval_days, repetitions,
                                      last_quality, next_review_at, reviewed_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?)
                 ON CONFLICT(word_id) DO UPDATE SET
                    ease_factor = excluded.ease_factor,
                    interval_days = excluded.interval_days,
                    repetitions = excluded.repetitions,
                    last_quality = excluded.last_quality,
                    next_review_at = excluded.next_review_at,
                    reviewed_at = excluded.reviewed_at"""
        with self._connect() as conn:
            conn.execute(sql, (
                word_id, ease_factor, interval_days, repetitions,
                quality, next_date.isoformat(), now,
            ))
            conn.commit()


    # ── 等级管理 ──────────────────────────────────────────

    def get_levels(self) -> list[str]:
        """获取所有等级名称（按 sort_order 排序）"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name FROM word_levels ORDER BY sort_order"
            ).fetchall()
            return [r["name"] for r in rows]

    def add_level(self, name: str) -> bool:
        """新增等级，成功返回 True，重复返回 False"""
        try:
            with self._connect() as conn:
                # 取最大 sort_order
                max_order = conn.execute(
                    "SELECT COALESCE(MAX(sort_order), -1) FROM word_levels"
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO word_levels (name, sort_order) VALUES (?, ?)",
                    (name.strip(), max_order + 1),
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def reorder_levels(self, names: list[str]) -> None:
        """按名称列表顺序更新 sort_order"""
        with self._connect() as conn:
            for i, name in enumerate(names):
                conn.execute(
                    "UPDATE word_levels SET sort_order = ? WHERE name = ?",
                    (i, name),
                )
            conn.commit()

    def delete_level(self, name: str) -> None:
        """删除等级（同时清除单词上该等级标记）"""
        with self._connect() as conn:
            conn.execute("DELETE FROM word_levels WHERE name = ?", (name,))
            conn.execute("UPDATE words SET level = '' WHERE level = ?", (name,))
            conn.commit()

    def mark_learned(self, word_id: int) -> None:
        """标记单词为已掌握 (只更新 last_quality, 不影响复习间隔)"""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO reviews (word_id, last_quality) VALUES (?, 4) "
                "ON CONFLICT(word_id) DO UPDATE SET last_quality = 4",
                (word_id,),
            )
            conn.commit()

    def clear_learned(self, level: str = "") -> None:
        """清除已掌握标记 (清空该等级单词的 last_quality=4)"""
        with self._connect() as conn:
            if level:
                conn.execute("""
                    UPDATE reviews SET last_quality = NULL
                    WHERE word_id IN (SELECT id FROM words WHERE level = ?)
                    AND last_quality = 4
                """, (level,))
            else:
                conn.execute("""
                    UPDATE reviews SET last_quality = NULL
                    WHERE last_quality = 4
                """)
            conn.commit()

    def reset_repetitions(self) -> None:
        """将所有单词的学习次数归零"""
        with self._connect() as conn:
            conn.execute("UPDATE reviews SET repetitions = 0")
            conn.commit()

    def clear_all_progress(self) -> None:
        """清除所有学习记录（清空 reviews 表）"""
        with self._connect() as conn:
            conn.execute("DELETE FROM reviews")
            conn.commit()

    def get_statistics(self, level: str = "") -> dict:
        """返回学习统计数据，支持等级筛选"""
        with self._connect() as conn:
            if level:
                total = conn.execute(
                    "SELECT COUNT(*) FROM words WHERE level = ?", (level,)
                ).fetchone()[0]
                # 已掌握: 该等级单词中最近一次复习 quality=4 (认识) 的
                learned = conn.execute("""
                    SELECT COUNT(*) FROM words w
                    INNER JOIN reviews r ON r.word_id = w.id
                    WHERE w.level = ? AND r.last_quality = 4
                """, (level,)).fetchone()[0]
            else:
                total = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
                learned = conn.execute("""
                    SELECT COUNT(*) FROM reviews WHERE last_quality = 4
                """).fetchone()[0]
            return {
                "total": total,
                "learned": learned,
            }
