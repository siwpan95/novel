# -*- coding: utf-8 -*-
"""Timeline —— 事件时间轴，替代抽象大纲和节拍系统。

设计原则：
  1. 事件驱动：不是"第X章应该发生Y"，而是"当条件满足时，事件Z触发"。
  2. 分层调度：全局事件（世界级）→ 区域事件（地点级）→ 角色事件（个人级）。
  3. 自然节奏：不需要 save the cat 节拍表，世界自身的因果关系产生叙事弧。

事件类型：
  WorldEvent   — 跨世界事件（新世界解锁、代理人入侵、源能波动）
  RegionEvent  — 区域级事件（势力冲突、天气突变、宝藏出世）
  CharacterGoal — 角色目标驱动（探索、战斗、对话、逃跑）
"""
from __future__ import annotations
import random
import json
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# 默认事件脊梁（时间轴）已外置到 word_banks/narrative/event_spine.json，
# 便于维护与扩展；此处统一加载。
_EVENT_SPINE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'word_banks', 'narrative', 'event_spine.json')
with open(_EVENT_SPINE_PATH, encoding='utf-8') as _es_f:
    _EVENT_SPINE_DATA = json.load(_es_f)


class EventScope(Enum):
    WORLD = auto()    # 跨世界全局事件
    REGION = auto()   # 当前世界区域事件
    CHARACTER = auto()  # 角色个人事件


@dataclass
class Event:
    """时间轴上的一个事件。"""
    event_id: str
    scope: EventScope
    name: str                          # 人类可读名称
    trigger_time: int = 0              # 触发时间步（0=条件触发）
    condition: Optional[str] = None    # 触发条件表达式（e.g. "danger >= 7 & region == '战场'")
    narrative_hint: str = ''           # 叙事提示——VoiceEngine 可以用这个选择模板
    duration: int = 1                  # 持续时间步
    repeatable: bool = False           # 是否可重复触发
    fired: bool = False                # 已触发标记
    cooldown: int = 0                  # 重复触发的冷却时间步
    last_fired: int = -999             # 上次触发时间步
    payload: dict = field(default_factory=dict)  # 额外数据


class Timeline:
    """事件时间轴——分层调度，条件触发。"""

    def __init__(self, seed: int = None):
        self._rng = random.Random(seed)
        self._events: list[Event] = []
        self._global_time: int = 0
        self._fired_ids: set[str] = set()

    # -- 构造 API -----------------------------------------------------------
    def add_event(self, event: Event):
        self._events.append(event)

    def add_world_event(self, event_id: str, name: str, trigger_time: int = 0,
                        condition: str = None, narrative_hint: str = '',
                        duration: int = 1, repeatable: bool = False,
                        cooldown: int = 0, **payload):
        self.add_event(Event(
            event_id=event_id, scope=EventScope.WORLD, name=name,
            trigger_time=trigger_time, condition=condition,
            narrative_hint=narrative_hint, duration=duration,
            repeatable=repeatable, cooldown=cooldown,
            payload=payload,
        ))

    def add_region_event(self, event_id: str, name: str, trigger_time: int = 0,
                         condition: str = None, narrative_hint: str = '',
                         duration: int = 1, **payload):
        self.add_event(Event(
            event_id=event_id, scope=EventScope.REGION, name=name,
            trigger_time=trigger_time, condition=condition,
            narrative_hint=narrative_hint, duration=duration,
            payload=payload,
        ))

    # -- 查询 API -----------------------------------------------------------
    def tick(self, current_time: int, world_state: dict = None) -> list[Event]:
        """时钟前进，返回当前时间步触发的所有事件列表。"""
        self._global_time = current_time
        fired = []

        for ev in self._events:
            if self._should_fire(ev, current_time, world_state):
                ev.fired = True
                ev.last_fired = current_time
                self._fired_ids.add(ev.event_id)
                fired.append(ev)

        return fired

    def _should_fire(self, ev: Event, current_time: int, world_state: dict = None) -> bool:
        # 已触发且不可重复 → 跳过
        if ev.fired and not ev.repeatable:
            return False
        # 冷却中 → 跳过
        if ev.repeatable and current_time - ev.last_fired < ev.cooldown:
            return False
        # 时间触发：到了 trigger_time 就触发
        if ev.trigger_time > 0 and current_time >= ev.trigger_time:
            if not ev.fired or ev.repeatable:
                return True
        # 条件触发：检查条件表达式
        if ev.condition and world_state:
            if self._eval_condition(ev.condition, world_state):
                return True
        return False

    def _eval_condition(self, condition: str, world_state: dict) -> bool:
        """简单的条件表达式求值。支持：danger>=7, region==重镇, visited>=3"""
        try:
            parts = condition.split('&')
            for part in parts:
                part = part.strip()
                for op in ('>=', '<=', '!=', '==', '>', '<'):
                    if op in part:
                        key, val = part.split(op, 1)
                        key = key.strip()
                        val = val.strip()
                        actual = world_state.get(key, 0)
                        if isinstance(actual, str):
                            if op == '==':
                                if actual != val:
                                    return False
                            elif op == '!=':
                                if actual == val:
                                    return False
                        else:
                            val_num = float(val) if '.' in val else int(val)
                            actual_num = float(actual) if isinstance(actual, float) else int(actual)
                            if op == '>=' and not (actual_num >= val_num):
                                return False
                            if op == '<=' and not (actual_num <= val_num):
                                return False
                            if op == '>' and not (actual_num > val_num):
                                return False
                            if op == '<' and not (actual_num < val_num):
                                return False
                            if op == '==' and not (actual_num == val_num):
                                return False
                            if op == '!=' and not (actual_num == val_num):
                                return False
                        break
            return True
        except Exception:
            return False

    def upcoming(self, lookahead: int = 5) -> list[Event]:
        """查看未来 lookahead 步内即将触发的定时事件。"""
        upcoming = []
        for ev in self._events:
            if ev.trigger_time > 0 and self._global_time < ev.trigger_time <= self._global_time + lookahead:
                if not ev.fired or ev.repeatable:
                    upcoming.append(ev)
        return sorted(upcoming, key=lambda e: e.trigger_time)

    # -- 默认时间轴构建 -------------------------------------------------------
    @classmethod
    def default_timeline(cls, seed: int = None) -> Timeline:
        """构建包含《万界归墟》标准事件流的默认时间轴。

        事件定义外置在 word_banks/narrative/event_spine.json 的 timeline_events，
        作者可改 JSON 增删/调整事件，无需动代码。
        """
        tl = cls(seed=seed)
        for _ev in _EVENT_SPINE_DATA['timeline_events']:
            _payload = _ev.get('payload') or {}
            _common = dict(
                trigger_time=_ev.get('trigger_time', 0),
                condition=_ev.get('condition'),
                narrative_hint=_ev.get('narrative_hint', ''),
                duration=_ev.get('duration', 1),
            )
            if _ev['type'] == 'region':
                tl.add_region_event(_ev['id'], _ev['name'], **_common, **_payload)
            else:
                tl.add_world_event(_ev['id'], _ev['name'],
                                   repeatable=_ev.get('repeatable', False),
                                   cooldown=_ev.get('cooldown', 0),
                                   **_common, **_payload)
        return tl
