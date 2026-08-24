# -*- coding: utf-8 -*-
"""叙事上下文 —— 双引擎融合的共享状态总线。

这是整合的核心：因果引擎的"大脑"（情节状态）和ASP引擎的"声音"（词库渲染）
通过 NarrativeContext 在每一次文本生成时同步上下文。

上下文包含：
  - 当前叙事位置（节拍/章号/子索引）
  - 当前世界设定（决定使用哪个词库族）
  - 在场角色的情绪状态（决定对话和描写的基调）
  - 情感弧线（决定节奏和句长）
  - 已发生的关键事件（决定因果一致性）
"""

from typing import Optional
from dataclasses import dataclass, field
from .beat_constants import BEAT_NAMES_CN


# 词库键 → 正文地名。键是设定/流派标签，不能直接当地名写进句子；
# 见 NarrativeContext.world_prose_name() 的说明。
WORLD_PROSE_NAMES = {
    '归墟': '归墟',
    '武侠·苍云之殇': '苍云山',
    '末日废土': '废土',
    '近代乱世': '旧城',
    '低魔中世纪': '旧王国',
    '剑与魔法': '魔法大陆',
    '星际殖民': '殖民星',
    '东方修仙': '青云界',
    '赛博都市': '赛博都市',
    '诸神黄昏': '神域',
    '克苏鲁深渊': '深渊',
    '高等文明实验场': '实验场',
    '造物主遗迹': '造物主遗迹',
}


@dataclass
class CharacterSnapshot:
    """角色在当前章节的快照。"""
    name: str
    emotional_state: str = '中性'
    current_goal: str = ''
    location: str = ''
    knows_truth: bool = False
    corruption_level: int = 0  # 叶琳专用
    personality_tag: str = ''  # 性格标签
    relations: dict = field(default_factory=dict)

    def mood_modifier(self) -> str:
        """将情绪映射为词库选择的修饰符。"""
        mapping = {
            '困惑': 'uncertain', '恐惧': 'tense', '愤怒': 'aggressive',
            '绝望': 'dark', '希望': 'warm', '坚定': 'resolute',
            '警觉': 'sharp', '兴奋': 'energetic', '疲惫': 'weary',
            '认可': 'approving', '投入': 'focused', '偏执': 'paranoid',
            '崩溃': 'shattered', '重新坚定': 'renewed',
            '中性': 'neutral', '被迫接受': 'resigned',
        }
        return mapping.get(self.emotional_state, 'neutral')

    def voice_hint(self) -> str:
        """返回角色在当前情绪下的声音特征。"""
        mood = self.emotional_state
        if mood in ('恐惧', '崩溃'):
            return 'voice_trembling'
        elif mood in ('愤怒', '偏执'):
            return 'voice_sharp'
        elif mood in ('疲惫', '绝望'):
            return 'voice_quiet'
        elif mood in ('兴奋', '热血'):
            return 'voice_loud'
        elif mood in ('坚定', '重新坚定'):
            return 'voice_steady'
        return 'voice_neutral'


@dataclass
class NarrativeContext:
    """跨双引擎的叙事上下文。

    因果引擎向它写入（当前节拍/事件/情绪），
    ASP引擎从它读取（决定用什么词库/什么模板/什么语气）。
    """

    # === 因果引擎写入 ===
    chapter: int = 0
    volume: int = 1  # 新增：卷号 1/2/3
    beat: str = 'opening'
    beat_cn: str = ''
    sub_index: int = 1
    total_in_beat: int = 3
    world_name: str = '归墟'

    # 情感弧线
    emotional_start: str = '中性'
    emotional_end: str = '中性'
    tension_level: int = 3  # 1-10

    # 关键事件
    key_events: list = field(default_factory=list)
    must_include: list = field(default_factory=list)  # 本章必须出现的元素

    # === 角色快照 ===
    characters_present: dict = field(default_factory=dict)  # name -> CharacterSnapshot

    # === ASP引擎读取 ===
    # 词库选择修饰符
    tone_modifier: str = 'neutral'  # dark/warm/tense/energetic/neutral
    pace_hint: str = 'medium'  # fast/medium/slow — 影响句长和段落密度

    # 描写密度
    description_density: str = 'normal'  # sparse/normal/rich — 外貌描写详细度
    dialogue_ratio: float = 0.3  # 对话占比建议 0-1

    # === 场景落地 / 章间节奏（P0 / P1 修复接通的字段） ===
    scene_spot: str = ''            # 当前章具体落点（来自 scene_locations 词库，消除世界级远景漂浮感）
    prev_beat_tension: int = 0      # 上一章张力等级（章间节奏调制：连续高张力→给一拍缓冲）

    # === Layer 3: 世界术语缓存（预加载全键合并池，供任意算子消费） ===
    world_terms: list = field(default_factory=list)  # 当前世界全部术语条目（genre_terms 全键合并）

    # === 质量管线 ===
    skip_rubric: bool = False
    skip_rashomon: bool = False
    skip_rhythm: bool = False

    def set_beat(self, beat: str, ch: int, sub_idx: int, total: int):
        """从因果大纲设置当前叙事位置。"""
        self.beat = beat
        self.beat_cn = BEAT_NAMES_CN.get(beat, '')
        self.chapter = ch
        self.sub_index = sub_idx
        self.total_in_beat = total

        # 自动推断基调
        self._infer_tone_from_beat()

    def _infer_tone_from_beat(self):
        """根据节拍自动推断叙述基调。"""
        tone_map = {
            'opening': ('tense', 'fast'),
            'theme': ('dark', 'slow'),
            'inciting': ('energetic', 'fast'),
            'debate': ('weary', 'medium'),
            'break_1': ('sharp', 'medium'),
            'b_story': ('warm', 'slow'),
            'fun_games': ('energetic', 'fast'),
            'midpoint': ('resolute', 'medium'),
            'bad_guys': ('tense', 'fast'),
            'all_lost': ('dark', 'slow'),
            'dark_night': ('shattered', 'slow'),
            'break_2': ('renewed', 'medium'),
        }
        tone, pace = tone_map.get(self.beat, ('neutral', 'medium'))
        self.tone_modifier = tone
        self.pace_hint = pace

        # P1 修复：把此前从未被消费的死字段接到节拍语义上
        # ——节奏调制（影响 ASP 配额注入）、描写密度（影响场景算子数量）、
        # 对话密度（影响是否额外注入对话算子）、必含元素（影响成稿校验）。
        density_map = {
            'theme': 'rich', 'dark_night': 'rich', 'all_lost': 'rich',
            'bad_guys': 'rich', 'midpoint': 'normal',
            'fun_games': 'sparse', 'debate': 'normal', 'opening': 'normal',
            'inciting': 'normal', 'break_1': 'normal', 'b_story': 'normal',
            'break_2': 'normal', 'epilogue': 'normal', 'generic': 'normal',
        }
        dialogue_map = {
            'b_story': 0.55, 'fun_games': 0.5, 'debate': 0.45,
            'break_2': 0.4, 'break_1': 0.4,
        }
        must_map = {
            'inciting': ['墟核直连'],
            'theme': ['协议附录'],
            'all_lost': ['叶琳的紫纹'],
            'midpoint': ['碎片能量读数'],
            'bad_guys': ['渗透型'],
        }
        self.description_density = density_map.get(self.beat, 'normal')
        self.dialogue_ratio = dialogue_map.get(self.beat, 0.3)
        self.must_include = must_map.get(self.beat, [])

    def add_character(self, name: str, **kwargs):
        """添加或更新在场角色。"""
        if name in self.characters_present:
            snap = self.characters_present[name]
            for k, v in kwargs.items():
                if hasattr(snap, k):
                    setattr(snap, k, v)
        else:
            self.characters_present[name] = CharacterSnapshot(name=name, **kwargs)

    def get_character(self, name: str) -> Optional[CharacterSnapshot]:
        return self.characters_present.get(name)

    def dominant_emotion(self) -> str:
        """返回在场角色中最突出的情绪。"""
        if not self.characters_present:
            return '中性'
        # 主角情绪优先
        if '林朔' in self.characters_present:
            return self.characters_present['林朔'].emotional_state
        return list(self.characters_present.values())[0].emotional_state

    def world_prose_name(self) -> str:
        """返回可直接写进正文的地名。

        `world_name` 是**词库键**，不是地名。其中「武侠·苍云之殇」带类型前缀、
        「东方修仙」「剑与魔法」「低魔中世纪」是流派名而非地点，直接插进
        `_ACTION_TEMPLATES`（「林朔踏进{w}。」「林朔在{w}边站住」）会写出
        「林朔踏进武侠·苍云之殇」这种把设定标签当地名用的句子。此处提供一层
        键→地名的翻译，正文只用这一层，词库查找仍用原键。
        """
        return WORLD_PROSE_NAMES.get(self.world_name, self.world_name)

    def world_key(self) -> str:
        """返回当前世界的词库键名。"""
        mapping = {
            '归墟': '归墟',
            '武侠·苍云之殇': '武侠·苍云之殇',
            '末日废土': '末日废土',
            '近代乱世': '近代乱世',
            '低魔中世纪': '低魔中世纪',
            '剑与魔法': '剑与魔法',
            '星际殖民': '星际殖民',
            '东方修仙': '东方修仙',
            '赛博都市': '赛博都市',
            '诸神黄昏': '诸神黄昏',
            '克苏鲁深渊': '克苏鲁深渊',
            '高等文明实验场': '高等文明实验场',
            '造物主遗迹': '造物主遗迹',
        }
        return mapping.get(self.world_name, '归墟')

    def summary(self) -> str:
        """返回上下文摘要，用于调试。"""
        chars = ', '.join(
            f'{name}({snap.emotional_state})'
            for name, snap in self.characters_present.items()
        )
        return (
            f'第{self.chapter}章 [{self.beat_cn}] '
            f'世界:{self.world_name} 基调:{self.tone_modifier} '
            f'角色:[{chars}]'
        )
