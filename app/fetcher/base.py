"""数据获取抽象基类和数据结构"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Example:
    """例句"""
    sentence_en: str           # 英文例句
    sentence_cn: str = ""      # 中文翻译
    audio_url: str = ""        # 例句朗读在线地址 (可选)
    source: str = "api"        # 来源标识


@dataclass
class WordData:
    """标准化单词数据"""
    word: str
    phonetic_uk: str = ""      # 英式音标
    phonetic_us: str = ""      # 美式音标
    translation: str = ""      # 中文释义
    pos: str = ""              # 词性 (n./v./adj./etc.)
    level: str = ""            # 等级 (CET4/CET6/IELTS/...)
    examples: list[Example] = field(default_factory=list)


class WordFetcher(ABC):
    """词典数据源抽象基类"""

    @abstractmethod
    async def fetch(self, word: str) -> Optional[WordData]:
        """获取单词的完整数据，失败返回 None"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称 (用于日志)"""
        ...
