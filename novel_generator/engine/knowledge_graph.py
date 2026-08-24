# -*- coding: utf-8 -*-
"""KnowledgeGraph —— 多POV信息不对称引擎。

POV写作技法的核心：不同视角角色知道不同的事，这种认知差本身就是叙事张力。
本模块提供：
  - CharacterKnowledge: 单角色的认知状态（已知事件、秘密、错误信念、嫌疑人）
  - KnowledgeGraph: 全局真相 + 所有角色的视角滤镜
  - 知识传播机制：角色相遇时共享信息
  - 渲染集成：为特定 POV 角色生成「信息差」叙事提示

设计参考：冰与火之歌的角色信息不对称、罗生门的多视角温差效应。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import random


# ---------------------------------------------------------------------------
# 知识事件定义
# ---------------------------------------------------------------------------
@dataclass
class KnowledgeEvent:
    """一条可被角色获知的知识事件。"""
    event_id: str                        # 唯一标识
    category: str                        # 类别：shard / truth / agent / protocol / loop / secret
    description: str                     # 真相描述
    layer: int = 1                       # 千层饼层级（越高越深层）
    discoverable_in: list[str] = field(default_factory=list)  # 可在哪些世界发现
    prerequisite: str = ''               # 前置知识事件ID（需先知道A才能知道B）


# ---------------------------------------------------------------------------
# 角色认知快照
# ---------------------------------------------------------------------------
@dataclass
class CharacterKnowledge:
    """单个角色的认知状态——这是信息不对称的基本单元。"""
    char_id: str
    known_events: set[str] = field(default_factory=set)       # 该角色已知的事件ID
    known_secrets: set[str] = field(default_factory=set)      # 该角色知道的秘密
    false_beliefs: dict[str, str] = field(default_factory=dict) # 错误认知 {事件ID: 错误理解}
    suspicion_targets: list[str] = field(default_factory=list)  # 该角色怀疑的角色列表
    discovered_in_world: set[str] = field(default_factory=set)  # 曾在哪些世界获得过信息

    def knows(self, event_id: str) -> bool:
        """该角色是否知道某个事件。"""
        return event_id in self.known_events

    def is_misinformed(self, event_id: str) -> bool:
        """该角色对某事件是否有错误认知。"""
        return event_id in self.false_beliefs

    def knowledge_gap(self, ground_truth: set[str]) -> set[str]:
        """返回该角色不知道的真相集合（信息差）。"""
        return ground_truth - self.known_events

    def share_with(self, other: CharacterKnowledge, max_events: int = 3) -> list[str]:
        """与另一个角色共享信息——返回本次新传递的事件ID列表。"""
        new_to_other = self.known_events - other.known_events
        if not new_to_other:
            return []
        shared = list(new_to_other)[:max_events]
        other.known_events.update(shared)
        return shared

    def learn(self, event_id: str, world_name: str = ''):
        """角色获知一个新事件。"""
        self.known_events.add(event_id)
        if world_name:
            self.discovered_in_world.add(world_name)
        # 学到真相后清除对应的错误信念
        self.false_beliefs.pop(event_id, None)

    def learn_false(self, event_id: str, false_version: str):
        """角色获得一个错误认知。"""
        self.false_beliefs[event_id] = false_version
        # 错误认知可能覆盖真相
        self.known_events.discard(event_id)


# ---------------------------------------------------------------------------
# 全局知识图谱
# ---------------------------------------------------------------------------
class KnowledgeGraph:
    """全局真相 + 所有角色的认知滤镜。

    用法：
      kg = KnowledgeGraph(seed=42)
      kg.register_event('shard_01', 'shard', '第一块碎片在归墟·遗忘之殿')
      kg.register_character('林朔')
      kg.character_learns('林朔', 'shard_01', '归墟')

      # 渲染时查询信息差
      gap = kg.knowledge_gap_for('林朔')  # → 林朔还不知道的事件列表
      narrative_hint = kg.render_gap_hint('林朔')  # → 可注入prompt的叙事提示
    """

    def __init__(self, seed: int = None):
        self._rng = random.Random(seed)
        self._events: dict[str, KnowledgeEvent] = {}           # 全局事件注册表
        self._characters: dict[str, CharacterKnowledge] = {}   # 角色认知表
        self._event_history: list[tuple[int, str, str]] = []   # (time_step, char_id, event_id)

    # -- 注册 API ------------------------------------------------------------

    def register_event(self, event_id: str, category: str,
                       description: str, layer: int = 1,
                       discoverable_in: list[str] = None,
                       prerequisite: str = '') -> KnowledgeEvent:
        """注册一条全局真相事件。"""
        ev = KnowledgeEvent(
            event_id=event_id,
            category=category,
            description=description,
            layer=layer,
            discoverable_in=discoverable_in or [],
            prerequisite=prerequisite,
        )
        self._events[event_id] = ev
        return ev

    def register_character(self, char_id: str,
                           initial_knowledge: list[str] = None,
                           false_beliefs: dict[str, str] = None):
        """注册一个角色的认知状态。"""
        ck = CharacterKnowledge(char_id=char_id)
        if initial_knowledge:
            ck.known_events.update(initial_knowledge)
        if false_beliefs:
            ck.false_beliefs.update(false_beliefs)
        self._characters[char_id] = ck

    def get_character(self, char_id: str) -> Optional[CharacterKnowledge]:
        """获取角色的认知状态。不存在则返回 None。"""
        return self._characters.get(char_id)

    def ensure_character(self, char_id: str) -> CharacterKnowledge:
        """获取或自动创建角色的认知状态。"""
        if char_id not in self._characters:
            self.register_character(char_id)
        return self._characters[char_id]

    # -- 知识传播 API --------------------------------------------------------

    def character_learns(self, char_id: str, event_id: str,
                         world_name: str = '', time_step: int = 0):
        """角色获知一个真相事件。如果事件不存在则忽略。"""
        if event_id not in self._events:
            return
        ck = self.ensure_character(char_id)
        ck.learn(event_id, world_name)
        self._event_history.append((time_step, char_id, event_id))

    def character_is_misinformed(self, char_id: str, event_id: str,
                                  false_version: str):
        """角色获得一个错误认知。"""
        ck = self.ensure_character(char_id)
        ck.learn_false(event_id, false_version)

    def share_on_intersection(self, char_a: str, char_b: str,
                              time_step: int = 0) -> list[str]:
        """两条故事线交汇时，角色间共享信息。返回本次传递的事件ID列表。"""
        ca = self.ensure_character(char_a)
        cb = self.ensure_character(char_b)
        shared_a_to_b = ca.share_with(cb, max_events=3)
        shared_b_to_a = cb.share_with(ca, max_events=3)
        all_shared = shared_a_to_b + shared_b_to_a
        for eid in all_shared:
            self._event_history.append((time_step, 'intersection', eid))
        return all_shared

    def discover_in_world(self, char_id: str, world_name: str,
                          time_step: int = 0) -> list[str]:
        """角色在当前世界可能发现的新知识。返回本次发现的事件ID列表。"""
        ck = self.ensure_character(char_id)
        discovered = []
        for eid, ev in self._events.items():
            if world_name not in ev.discoverable_in:
                continue
            if eid in ck.known_events:
                continue
            if ev.prerequisite and ev.prerequisite not in ck.known_events:
                continue
            # 概率发现：深层事件更难发现
            prob = max(0.1, 1.0 - ev.layer * 0.15)
            if self._rng.random() < prob:
                ck.learn(eid, world_name)
                self._event_history.append((time_step, char_id, eid))
                discovered.append(eid)
        return discovered

    # -- 查询 API ------------------------------------------------------------

    def knowledge_gap_for(self, char_id: str) -> dict:
        """返回某角色的信息差详情。

        返回值：
          {'known': [...], 'unknown': [...], 'misinformed': {...}, 'total_truths': N}
        """
        ck = self.ensure_character(char_id)
        all_truths = set(self._events.keys())
        return {
            'char_id': char_id,
            'known': sorted(ck.known_events & all_truths),
            'unknown': sorted(all_truths - ck.known_events),
            'misinformed': dict(ck.false_beliefs),
            'total_truths': len(all_truths),
            'knowledge_pct': len(ck.known_events & all_truths) / max(1, len(all_truths)),
        }

    def all_gaps(self) -> dict[str, dict]:
        """返回所有角色的信息差概览。"""
        return {cid: self.knowledge_gap_for(cid) for cid in self._characters}

    def ground_truth_events(self, category: str = None) -> list[KnowledgeEvent]:
        """返回全局真相事件列表（可按类别过滤）。"""
        if category:
            return [ev for ev in self._events.values() if ev.category == category]
        return list(self._events.values())

    def all_character_ids(self) -> list[str]:
        """返回所有已注册角色ID。"""
        return list(self._characters.keys())

    # -- 渲染集成 API --------------------------------------------------------

    def render_gap_hint(self, char_id: str, max_hints: int = 2) -> str:
        """为指定POV角色生成「信息差」叙事提示。

        返回可注入 prompt / 文本的提示字符串，描述该角色当前知道什么、不知道什么。
        用于在渲染时让同一场景在不同POV下产生不同的叙述角度。

        返回值示例：
          「林朔已知：归墟是源界遗址。未知：碎片总共有12块、第47次循环的真相。」
          → 空字符串表示无需提示（角色无所不知或知识图谱为空）。
        """
        gap = self.knowledge_gap_for(char_id)
        ck = self._characters.get(char_id)

        parts = []

        # 已知的关键信息
        if gap['known']:
            known_descs = []
            for eid in gap['known'][:max_hints]:
                ev = self._events.get(eid)
                if ev:
                    known_descs.append(ev.description[:30])
            if known_descs:
                parts.append(f'{char_id}已知：{"；".join(known_descs)}')

        # 未知的关键信息
        if gap['unknown']:
            unknown_descs = []
            for eid in gap['unknown'][:max_hints]:
                ev = self._events.get(eid)
                if ev:
                    unknown_descs.append(ev.description[:30])
            if unknown_descs:
                parts.append(f'未知：{"；".join(unknown_descs)}')

        # 错误认知
        if ck and ck.false_beliefs:
            false_items = list(ck.false_beliefs.items())[:1]
            for eid, false_ver in false_items:
                parts.append(f'误以为：{false_ver[:40]}')

        # 怀疑对象
        if ck and ck.suspicion_targets:
            parts.append(f'怀疑：{"、".join(ck.suspicion_targets[:2])}')

        if not parts:
            return ''

        return '。'.join(parts)

    def characters_with_gap_on(self, event_id: str) -> list[str]:
        """返回不知道某个特定事件的角色列表——用于制造「读者替角色着急」的张力。"""
        return [cid for cid, ck in self._characters.items()
                if event_id not in ck.known_events]

    # -- 默认知识图谱构建（《万界归墟》世界观） -----------------------------

    @classmethod
    def default_for_wanjie(cls, seed: int = None) -> KnowledgeGraph:
        """构建《万界归墟》默认知识图谱。

        注册核心真相事件和各角色的初始认知状态。
        """
        kg = cls(seed=seed)

        # === 层级1：表层碎片信息 ===
        kg.register_event('shard_01', 'shard',
                          '归墟·遗忘之殿存在第一块源界碎片',
                          layer=1, discoverable_in=['归墟'])
        kg.register_event('shard_02', 'shard',
                          '苍云山深处封印着第二块碎片',
                          layer=1, discoverable_in=['武侠·苍云之殇'])
        kg.register_event('shard_03', 'shard',
                          '废土地下避难所有第三块碎片的能量反应',
                          layer=1, discoverable_in=['末日废土'])

        # === 层级2：协议与锚定者 ===
        kg.register_event('protocol_purpose', 'protocol',
                          '锚定者协议的真实目的不是守护世界，而是维持源能的循环消耗',
                          layer=2, prerequisite='shard_01')
        kg.register_event('anchor_count', 'protocol',
                          '林朔是第47任锚定者——前46任全部失败',
                          layer=2, discoverable_in=['归墟'],
                          prerequisite='shard_01')
        kg.register_event('protocol_cost', 'protocol',
                          '每次锚定都会消耗锚定者自身的「存在」——记忆、情感、最终是生命',
                          layer=3, prerequisite='protocol_purpose')

        # === 层级2：代理人 ===
        kg.register_event('agent_type_1', 'agent',
                          '白夜是第一代代理人，融合了源界科技与人类意识',
                          layer=2, discoverable_in=['赛博都市'])
        kg.register_event('agent_infiltrate', 'agent',
                          '渗透型代理人已经进入了至少三个世界',
                          layer=2, discoverable_in=['归墟', '武侠·苍云之殇', '末日废土'])
        kg.register_event('agent_ye_lin', 'agent',
                          '叶琳正在逐渐转变为新型代理人——她的紫纹不是伤，是进化',
                          layer=3, discoverable_in=['武侠·苍云之殇'],
                          prerequisite='agent_type_1')

        # === 层级3：祂们 ===
        kg.register_event('them_nature', 'truth',
                          '祂们是上一个宇宙纪元的幸存者——源界文明不是灭亡了，是逃走了',
                          layer=3, prerequisite='protocol_purpose')
        kg.register_event('them_goal', 'truth',
                          '祂们要回收所有碎片，重启宇宙——而重启意味着当前一切存在的终结',
                          layer=4, prerequisite='them_nature')
        kg.register_event('loop_truth', 'truth',
                          '源界文明从未消亡——祂们把文明编码进了碎片本身，每一个锚定者都是祂们的一次「测试」',
                          layer=4, prerequisite='them_nature')

        # === 层级2：玩家侧 ===
        kg.register_event('player_real', 'truth',
                          '归墟不是游戏——每一个"玩家"都是现实中的人类意识映射',
                          layer=2, discoverable_in=['归墟'])
        kg.register_event('player_risk', 'truth',
                          '玩家的意识映射不是永久的——源能消耗会切断连接，就像"删号"',
                          layer=3, prerequisite='player_real')

        # === 角色间秘密 ===
        kg.register_event('secret_lin_shuo', 'secret',
                          '林朔在现实中的策划案——那个被否决的企划——恰好描述了归墟的结构',
                          layer=2, prerequisite='shard_01')

        # === 注册角色初始认知 ===
        # 林朔：只知道最表层的信息
        kg.register_character('林朔', initial_knowledge=['shard_01'])
        kg.character_is_misinformed('林朔', 'protocol_purpose',
                                     '锚定者协议是为了修复源界文明留下的破损')

        # 唐川：知道玩家侧的真相，不知道更大的图景
        kg.register_character('唐川', initial_knowledge=['player_real', 'shard_01'])
        kg.character_is_misinformed('唐川', 'them_nature',
                                     '以为是某种超级AI或服务器的异常行为')

        # 白夜：知道代理人相关，但对祂们一知半解
        kg.register_character('白夜', initial_knowledge=['agent_type_1', 'agent_infiltrate'])
        kg.character_is_misinformed('白夜', 'them_goal',
                                     '认为祂们只是在收集碎片用于某种研究')

        # 叶琳：正在转变为代理人，但自己还不太清楚
        kg.register_character('叶琳', initial_knowledge=['shard_02'])
        kg.character_is_misinformed('叶琳', 'agent_ye_lin',
                                     '以为紫纹是某种诅咒或疾病')

        return kg
