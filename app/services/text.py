"""文字工具函数"""
import re


def short_translation(text: str) -> str:
    """截取短释义: 取第一个分句 (支持中文/英文分号)，清理多余空格"""
    if not text:
        return ""
    import re
    # 去掉词性前缀 (如 "n. " 或 "vt.& vi. ") 只出现在开头时保留，但截断时处理
    text = re.sub(r"\s+", " ", text).strip()
    # 以中文或英文分号切分
    for sep in ("；", ";"):
        if sep in text:
            text = text.split(sep)[0].strip()
    if len(text) > 30:
        text = text[:28] + "…"
    return text
