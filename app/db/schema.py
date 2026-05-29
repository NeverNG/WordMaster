"""数据库建表与初始化"""

from pathlib import Path
import sqlite3

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- 单词表
CREATE TABLE IF NOT EXISTS words (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    word        TEXT UNIQUE NOT NULL,
    phonetic_uk TEXT,                -- 英式音标
    phonetic_us TEXT,                -- 美式音标
    translation TEXT,                -- 中文翻译
    pos         TEXT,                -- 词性 (n./v./adj./...)
    level       TEXT DEFAULT '',      -- 等级 (CET4/CET6/IELTS/TOEFL/GRE/考研/商务英语)
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 例句表 (一对多, 按 word_id 关联)
CREATE TABLE IF NOT EXISTS examples (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id         INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    sentence_en     TEXT NOT NULL,        -- 英文例句
    sentence_cn     TEXT,                 -- 例句中文翻译
    audio_filename  TEXT,                 -- 缓存 MP3 文件名
    source          TEXT DEFAULT 'manual', -- api / cambridge / youdao / edge-tts / manual
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 学习记录表 (SM-2 算法核心)
CREATE TABLE IF NOT EXISTS reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id         INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    ease_factor     REAL DEFAULT 2.5,     -- 难度系数 (>=1.3)
    interval_days   INTEGER DEFAULT 0,    -- 当前间隔天数
    repetitions     INTEGER DEFAULT 0,    -- 连续正确次数
    next_review_at  DATE,                 -- 下次复习日期
    last_quality    INTEGER,              -- 本次复习质量 (0-5)
    reviewed_at     TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 等级表 (用户自定义)
CREATE TABLE IF NOT EXISTS word_levels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    sort_order  INTEGER DEFAULT 0
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_examples_word ON examples(word_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reviews_word ON reviews(word_id);
CREATE INDEX IF NOT EXISTS idx_reviews_next ON reviews(next_review_at);
"""


DEFAULT_LEVELS = [
    "CET4", "CET6", "考研", "IELTS", "TOEFL", "GRE", "SAT", "商务英语",
]


def _seed_levels(conn: sqlite3.Connection) -> None:
    """插入默认等级（仅首次运行时）"""
    existing = conn.execute("SELECT COUNT(*) FROM word_levels").fetchone()[0]
    if existing > 0:
        return
    for i, name in enumerate(DEFAULT_LEVELS):
        conn.execute(
            "INSERT OR IGNORE INTO word_levels (name, sort_order) VALUES (?, ?)",
            (name, i),
        )
    conn.commit()


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """初始化数据库，返回连接对象"""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()

    # 迁移: 旧数据库加 level 列
    try:
        conn.execute("ALTER TABLE words ADD COLUMN level TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # 种子数据: 默认等级
    _seed_levels(conn)

    return conn
