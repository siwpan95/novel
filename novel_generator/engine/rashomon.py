# -*- coding: utf-8 -*-
"""P1: 复眼叙事引擎 + 信息不对称矩阵。

复眼叙事：关键转折章生成多视角 mini 节，同一事件不同维度折射。
信息不对称：四象限追踪谁-知道-什么，自动决定每章该释放还是扣留信息。
"""

import json
import os
import random


# ================================================================
# 1. 复眼叙事引擎 (Rashomon Engine)
# ================================================================

# POV 复眼叙事内容（触发节拍/视角透镜/各角色片段）已外置到
# word_banks/narrative/rashomon.json，便于维护与扩展；此处统一加载。
_RASHOMON_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "word_banks", "narrative", "rashomon.json")
with open(_RASHOMON_JSON, encoding="utf-8") as _rf:
    _RASHOMON_DATA = json.load(_rf)
RASHOMON_TRIGGERS = _RASHOMON_DATA["triggers"]
POV_INFO_LENS = _RASHOMON_DATA["lenses"]
RASHOMON_SCENES = _RASHOMON_DATA["scenes"]






class RashomonEngine:
    """复眼叙事引擎：在关键转折章生成多视角 mini 节。"""

    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self._used_scenes = set()

    def should_trigger(self, beat: str) -> bool:
        return beat in RASHOMON_TRIGGERS

    def generate(self, beat: str) -> list:
        """为指定节拍生成多视角叙事片段。

        Returns:
            [(pov_name, content), ...] 每个视角一段。
        """
        if beat not in RASHOMON_TRIGGERS:
            return []

        povs = RASHOMON_TRIGGERS[beat]
        scenes = RASHOMON_SCENES.get(beat, {})
        results = []

        for pov in povs:
            if pov in scenes and scenes[pov]:
                content = self._rng.choice(scenes[pov])
                lens = POV_INFO_LENS.get(pov, {})
                header = '【%s视角】' % pov
                lens.get('adds', '')
                results.append((pov, '%s\n%s\n' % (header, content)))

        return results

    def format_section(self, pov_scenes: list) -> str:
        """格式化多视角段落。"""
        if not pov_scenes:
            return ''
        parts = []
        for pov, text in pov_scenes:
            parts.append(text)
        return '\n──── 同一时刻 ────\n\n'.join(parts)


# ================================================================
# 2. 信息不对称矩阵
# ================================================================

class InfoMatrix:
    """四象限信息不对称追踪器。

    象限：
    ┌─────────────────┬─────────────────┐
    │ 读者已知 + 林朔已知 │ 读者已知 + 林朔不知 │
    │   (同步区)        │   (悬疑区)        │
    ├─────────────────┼─────────────────┤
    │ 读者不知 + 林朔已知 │ 读者不知 + 林朔不知 │
    │   (蓄力区)        │   (双盲区)        │
    └─────────────────┴─────────────────┘
    """

    def __init__(self):
        self.matrix = {
            'sync': [],        # 同步区 - 读者和林朔都知道
            'suspense': [],    # 悬疑区 - 读者知道林朔不知道
            'charge': [],      # 蓄力区 - 林朔知道读者不知道
            'blind': [],       # 双盲区 - 都没人知道
        }

    def add_info(self, zone: str, content: str, chapter: int):
        self.matrix[zone].append({
            'content': content,
            'chapter': chapter,
            'status': 'active',
        })

    def move_info(self, info_id: int, from_zone: str, to_zone: str, chapter: int):
        """移动一条信息到另一个象限（如蓄力→同步，悬疑→同步）。"""
        if 0 <= info_id < len(self.matrix[from_zone]):
            info = self.matrix[from_zone].pop(info_id)
            info['revealed_chapter'] = chapter
            self.matrix[to_zone].append(info)

    def should_reveal_suspense(self, current_chapter: int, beat: str) -> bool:
        """判断当前章是否应该揭示悬疑区的信息。

        规则：在 midpoint 和 break_2 节拍，悬疑区信息应该向同步区转移。
        """
        return beat in ('midpoint', 'break_2') and len(self.matrix['suspense']) > 0

    def should_charge(self, current_chapter: int, beat: str) -> bool:
        """判断当前章是否应该把蓄力区的信息转移给读者。

        规则：每 20 章检查蓄力区，选择一条转移到同步区。
        """
        return current_chapter % 20 == 0 and len(self.matrix['charge']) > 0

    def get_narrative_tip(self, beat: str, chapter: int) -> str:
        """返回叙事提示——告诉引擎当前章该以什么策略处理信息。

        Returns:
            'reveal' - 释放信息给读者
            'withhold' - 扣留信息
            'surprise' - 反转（蓄力区释放）
            'neutral' - 正常推进
        """
        # 关键节拍：释放悬疑
        if beat in ('break_1', 'midpoint', 'break_2'):
            if self.matrix['suspense']:
                return 'reveal'
        # 每20章：蓄力释放
        if chapter % 20 == 0 and self.matrix['charge']:
            return 'surprise'
        # 普通章
        return 'neutral'

    def blind_spot_count(self) -> int:
        """未解决的谜题数量。"""
        return len(self.matrix['blind'])

    def summary(self) -> dict:
        return {
            zone: len(items)
            for zone, items in self.matrix.items()
        }
