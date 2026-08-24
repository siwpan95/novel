"""词库加载与随机选取引擎。

支持：
- JSON词库文件的加载和缓存
- 基于权重的随机选取
- 半随机名字生成（姓氏固定挑选 + 名字字符随机组合）
- 种子控制（可复现生成）
"""

import json
import random
import re
from pathlib import Path
from typing import Optional

WORD_BANK_DIR = Path(__file__).parent.parent / "word_banks"

# 术语前缀词表：用于识别「纯前缀堆叠」垃圾（如 远古远古远古、远古混沌混沌）。
# 这类条目无实义锚点，拼入正文会产生 远古墨黑赤红远古永恒罡风 之类的无意义灌水。
_PREFIX_TOKENS = (
    '远古', '浩渺', '渊深', '杳冥', '太古', '赤红', '凤羽', '断罪',
    '混元', '归墟', '九幽', '混沌', '虚空中', '寂灭', '焚天', '孤绝',
)


def _is_meaningless(text: str) -> bool:
    """判定一条词库文本是否为「术语前缀堆叠」垃圾，例如 远古远古虚空、太古太古寂灭。

    规则：
      1) 剥离所有前缀词后无实义汉字锚点（纯堆叠）；
      2) 同一前缀词紧邻重复两次及以上（远古远古 / 太古太古）—— 数据生成脚本
         的 bug 产物；
      3) 同一前缀词连续出现三次及以上（远古远古远古）。
    注意：单前缀 + 实义词（远古归墟 / 太古混元）合法，不删。
    """
    if not isinstance(text, str) or len(text) < 4:
        return False
    content = re.sub(r'[，。、\s：:（）()【】\[\]「」\'\"]', '', text)
    if not content:
        return True
    stripped = content
    for tok in _PREFIX_TOKENS:
        stripped = stripped.replace(tok, '')
    if len(stripped) == 0 and len(content) >= 3:
        return True
    for tok in _PREFIX_TOKENS:
        if tok + tok in content or tok * 3 in content:
            return True
    return False


def _filter_pool(pool: list) -> list:
    """过滤掉纯前缀堆叠的垃圾条目；若过滤后为空则原样返回（兜底不崩溃）。"""
    cleaned = [x for x in pool if not (isinstance(x, str) and _is_meaningless(x))]
    return cleaned if cleaned else pool


def resolve_bank_path(bank_name: str) -> Path:
    """将词库名解析为 JSON 文件路径，兼容扁平与子目录两种布局。

    - bank_name 可带或不带 `.json` 后缀；
    - 优先取扁平路径 ``WORD_BANK_DIR/<bank_name>.json``（向后兼容）；
    - 若扁平路径不存在，递归搜索 ``WORD_BANK_DIR`` 下首个同名文件
      （用于「升格为内容库文件夹」后的分类子目录结构）。
    """
    name = bank_name if bank_name.endswith(".json") else f"{bank_name}.json"
    flat = WORD_BANK_DIR / name
    if flat.exists():
        return flat
    matches = [p for p in WORD_BANK_DIR.rglob(name) if p.is_file()]
    if matches:
        return matches[0]
    raise FileNotFoundError(f"词库文件不存在: {flat}（含子目录递归搜索）")


class WordBank:
    """词库管理器：加载、缓存、随机选取。"""

    def __init__(self, seed: Optional[int] = None):
        self._seed_value = seed
        self._cache: dict[str, dict] = {}
        self._rng = random.Random(seed)

    @property
    def seed(self) -> Optional[int]:
        """返回初始化时传入的主种子（可能为 None）。"""
        return self._seed_value

    def load(self, bank_name: str) -> dict:
        """加载指定词库JSON文件（带缓存）。"""
        if bank_name in self._cache:
            return self._cache[bank_name]

        filepath = resolve_bank_path(bank_name)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._cache[bank_name] = data
        return data

    def pick(self, bank_name: str, key: str) -> str:
        """从词库的指定key中随机挑选一项（自动跳过纯前缀堆叠垃圾）。"""
        data = self.load(bank_name)
        if key not in data:
            raise KeyError(f"词库'{bank_name}'中无键'{key}'")
        pool = _filter_pool(data[key])
        return self._rng.choice(pool)

    def pick_n(self, bank_name: str, key: str, n: int, unique: bool = False) -> list[str]:
        """从词库中随机挑选n项（自动跳过纯前缀堆叠垃圾）。"""
        data = self.load(bank_name)
        pool = _filter_pool(data[key])
        if unique and n > len(pool):
            n = len(pool)
        if unique:
            return self._rng.sample(pool, n)
        return [self._rng.choice(pool) for _ in range(n)]

    def pick_without(self, bank_name: str, key: str, exclude: set[str]) -> str:
        """从词库中随机挑选，排除某些项（自动跳过纯前缀堆叠垃圾）。"""
        data = self.load(bank_name)
        pool = _filter_pool([item for item in data[key] if item not in exclude])
        if not pool:
            return self._rng.choice(_filter_pool(data[key]))  # fallback
        return self._rng.choice(pool)

    def generate_name(self, length: int = 2, surname: Optional[str] = None) -> str:
        """半随机生成中文名字。

        - 姓氏：可指定或随机选
        - 名字：从名字用字池中随机组合指定长度
        """
        data = self.load("names")
        if surname is None:
            surname = self._rng.choice(data["surnames"])

        given_chars = self._rng.sample(data["given_name_chars"], length)
        given_name = "".join(given_chars)
        return f"{surname}{given_name}"

    def generate_name_pair(self, gender_hint: str = "neutral") -> tuple[str, str]:
        """生成一对名字（可指定性别倾向）。"""
        return self.generate_name(), self.generate_name()

    def get_rng(self) -> random.Random:
        """获取内部随机数生成器。"""
        return self._rng

    def all_keys(self, bank_name: str) -> list[str]:
        """获取词库中所有键名。"""
        data = self.load(bank_name)
        return list(data.keys())

    def load_world_senses(self) -> dict:
        """合并拆分后的世界五感词库。

        原 ``world_senses.json`` 同时承载环境五感（``worlds``）与战场地形
        （``battlefields``）两块，体量 ~2964 条，难以维护。升格后拆为
        ``world/senses/world_senses_ambient.json`` 与
        ``world/senses/world_senses_battle.json`` 两份，本方法一次性取回
        与旧结构兼容的合并字典：``{'worlds': {...}, 'battlefields': {...}}``。
        """
        if "world_senses" in self._cache:
            return self._cache["world_senses"]
        ambient = self.load("world_senses_ambient")
        battle = self.load("world_senses_battle")
        merged = {
            "worlds": ambient.get("worlds", {}),
            "battlefields": battle.get("battlefields", {}),
        }
        self._cache["world_senses"] = merged
        return merged

    def load_voice_helpers(self) -> dict:
        """合并拆分后的声音·体感辅助词库。

        原 ``voice_helpers.json`` 把四类体感数据（身体反应 / 身体部位 /
        情绪体感 / 感官兜底）揉在一个文件里。升格后拆为
        ``voice/voice_helpers_*.json`` 四份，本方法一次性取回与旧结构兼容的
        合并字典：``{'body_reaction', 'body_parts', 'sensations',
        'sense_fallbacks'}``。
        """
        if "voice_helpers" in self._cache:
            return self._cache["voice_helpers"]
        merged = {
            "body_reaction": self.load("voice_helpers_body_reaction").get("body_reaction", {}),
            "body_parts": self.load("voice_helpers_body_parts").get("body_parts", {}),
            "sensations": self.load("voice_helpers_sensations").get("sensations", {}),
            "sense_fallbacks": self.load("voice_helpers_sense_fallbacks").get("sense_fallbacks", {}),
        }
        self._cache["voice_helpers"] = merged
        return merged
