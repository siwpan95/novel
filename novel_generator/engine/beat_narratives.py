"""节拍叙事文本加载器 — 从 JSON 数据文件加载，消除硬编码文本。

使用方式：
  loader = BeatNarrativeLoader()
  texts = loader.get('_beat_opening')  # 返回叙事文本列表
"""
import json

from .word_bank import resolve_bank_path

_NARRATIVE_FILE = resolve_bank_path('beat_narratives')


class BeatNarrativeLoader:
    """从 beat_narratives.json 加载节拍叙事文本。"""

    def __init__(self):
        self._data = {}
        self._loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            if _NARRATIVE_FILE.exists():
                with open(_NARRATIVE_FILE, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            self._loaded = True

    def get(self, beat_name: str, index: int = None) -> str:
        """获取指定节拍的叙事文本。

        Args:
            beat_name: 如 '_beat_opening'
            index: 文本索引，None 则返回第一条
        Returns:
            叙事文本字符串，不存在则返回空字符串
        """
        self._ensure_loaded()
        texts = self._data.get(beat_name, [])
        if not texts:
            return ''
        if index is not None and 0 <= index < len(texts):
            return texts[index]
        return texts[0] if texts else ''

    def get_all(self, beat_name: str) -> list:
        """获取指定节拍的全部叙事文本。"""
        self._ensure_loaded()
        return self._data.get(beat_name, [])

    def has_beat(self, beat_name: str) -> bool:
        """检查是否存在指定节拍数据。"""
        self._ensure_loaded()
        return beat_name in self._data

    @property
    def beat_count(self) -> int:
        """已加载的节拍方法数。"""
        self._ensure_loaded()
        return len(self._data)

    @property
    def text_count(self) -> int:
        """叙事文本总数。"""
        self._ensure_loaded()
        return sum(len(v) for v in self._data.values())
