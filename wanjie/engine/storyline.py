# -*- coding: utf-8 -*-
"""Storyline & StoryBoard —— 棋盘式多线叙事引擎。

基于美剧编剧方法论（棋盘布局 / 多线交织 / 角色弧光驱动）：

核心概念：
  Storyline   = 一条叙事线（A-plot 主线 / B-plot 玩家线 / C-plot 对抗线）
  StoryBoard  = 棋盘——管理多条 Storyline 的交叉调度
  StoryBeat   = 棋盘上的一格——某个时间步上某条线的一个叙事单元

调度规则：
  1. 每段（section）在 2-3 条线之间切换，不会连续两段都是同一条线。
  2. 交叉点（intersection）在两个条件同时满足时触发：
     a) 两条线的剧情在物理/信息上可相遇
     b) 至少有一方处于高戏剧张力状态
  3. 每条线有自己的节奏（轻重缓急），棋盘负责全局均衡。
  4. 角色弧光五步法：初始形象 → 揭示真性 → 内外冲突 → 艰难抉择 → 人性蜕变
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
import random
import json
import os


# POV 编排内容（选角/事件脊梁）已外置到 word_banks/narrative/，
# 便于维护与扩展；此处统一加载。
_POV_CONF_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'word_banks', 'narrative')
def _load_pov_json(name):
    with open(os.path.join(_POV_CONF_DIR, name), encoding='utf-8') as _f:
        return json.load(_f)
_POV_ASSIGNMENT = _load_pov_json('pov_assignment.json')
_EVENT_SPINE = _load_pov_json('event_spine.json')
# ★ P3：时间线编排规则（汇聚默认 / 防混乱约束 / 阶段阈值 / 各线 beat 间隔）
_POV_TIMELINE = _load_pov_json('pov_timeline.json')


class ArcPhase(Enum):
    """角色弧光阶段（五步法）。"""
    ESTABLISH = auto()      # 1. 建立初始形象
    REVEAL = auto()         # 2. 揭示真实本性
    CONFLICT = auto()       # 3. 制造内外冲突
    CHOICE = auto()         # 4. 设置艰难抉择
    TRANSFORM = auto()      # 5. 完成人性蜕变


class StorylineType(Enum):
    """故事线类型。"""
    A_PLOT = 'a_plot'       # 主线：林朔回收碎片 / 世界解锁
    B_PLOT = 'b_plot'       # 玩家线：唐川 / 玩家社区动态
    C_PLOT = 'c_plot'       # 对抗线：代理人 / 祂们 / 源能波动
    D_PLOT = 'd_plot'       # 世界线：特定世界的 NPC 弧（叶琳等）


class ArcStage(Enum):
    """叙事弧阶段（比 ArcPhase 更宏观的节奏层面）。"""
    SETUP = 'setup'           # 起：建立各自的世界和角色状态
    RISE = 'rise'             # 承：各线独立发展，张力逐渐累积
    CONVERGE = 'converge'     # 转：多线开始交叉，信息开始流通
    CLIMAX = 'climax'         # 合：所有线汇聚到同一个高张力事件
    FALL = 'fall'             # 尾声：交代汇聚事件的余波


# ---------------------------------------------------------------------------
# 故事线定义
# ---------------------------------------------------------------------------
@dataclass
class Storyline:
    """一条叙事线。"""
    line_id: str
    line_type: StorylineType
    label: str                          # 人类可读标签
    pov_characters: list[str]           # 这条线的 POV 角色
    default_tone: str = 'neutral'       # 默认叙事基调
    tension_baseline: int = 3           # 基础张力水平

    # 动态状态
    current_phase: ArcPhase = ArcPhase.ESTABLISH
    phase_progress: float = 0.0         # 当前阶段进度 0-1
    tension: int = 3                    # 当前张力 1-10
    beat_count: int = 0                 # 已产出的叙事单元数
    last_beat_at: int = -1              # 上一个 beat 的时间步
    active: bool = True                 # 是否激活

    # 交叉点条件
    can_intersect_with: list[str] = field(default_factory=list)  # 可与哪些线交叉
    intersection_ready: bool = False    # 是否准备好交叉

    # 节奏控制
    beat_interval: int = 3              # 理想间隔（每 N 步出一次这条线的 beat）
    priority: int = 1                   # 调度优先级 1-5，越高越优先

    # 世界绑定
    world_name: str = ''                # 该故事线所属的世界（空串表示跟随主线）

    # 内容偏好
    preferred_ops: list[str] = field(default_factory=list)  # 偏好的操作类型
    narrative_themes: list[str] = field(default_factory=list)  # 叙事主题关键词

    def advance_phase(self, progress_increment: float = 0.05):
        """推进角色弧光阶段。"""
        self.phase_progress = min(1.0, self.phase_progress + progress_increment)
        if self.phase_progress >= 0.95:
            phases = list(ArcPhase)
            current_idx = phases.index(self.current_phase)
            if current_idx < len(phases) - 1:
                self.current_phase = phases[current_idx + 1]
                self.phase_progress = 0.0


# ---------------------------------------------------------------------------
# 棋盘——管理多条故事线的交叉调度
# ---------------------------------------------------------------------------
class StoryBoard:
    """棋盘式布局引擎。

    管理 A/B/C/D 四条故事线的并行推进和交叉调度。
    """

    def __init__(self, seed: int = None,
                 arc_manager: NarrativeArcManager = None):
        self._rng = random.Random(seed)
        self._lines: dict[str, Storyline] = {}
        self._beat_history: list[tuple[int, str]] = []  # (time_step, line_id)
        self._intersection_points: list[dict] = []       # 已触发的交叉点
        self._global_time: int = 0
        # ★ P3：防混乱约束（来自 pov_timeline.json 的 anti_chaos）
        self._anti_chaos = _POV_TIMELINE.get('anti_chaos', {}) or {}
        # ★ P2：叙事弧管理器——协调多线汇聚
        self._arc_mgr = arc_manager or NarrativeArcManager()

    # -- 构造 API -----------------------------------------------------------
    def add_line(self, line: Storyline):
        self._lines[line.line_id] = line

    def line(self, line_id: str) -> Optional[Storyline]:
        return self._lines.get(line_id)

    @property
    def active_lines(self) -> list[Storyline]:
        return [l for l in self._lines.values() if l.active]

    # -- 调度 API -----------------------------------------------------------
    def tick(self, time_step: int) -> list[StoryBeat]:
        """时间步前进，返回本步应产出的叙事单元列表（已在多条线间交织）。"""
        self._global_time = time_step
        active = self.active_lines
        if not active:
            return []

        beats = []

        # 1. 选择本步的主线（优先最近没出 beat 的线）
        primary = self._pick_primary_line(active, time_step)
        if primary:
            beats.append(StoryBeat(
                line_id=primary.line_id, time_step=time_step,
                beat_type='primary', priority=primary.priority,
                pov_char=self._rng.choice(primary.pov_characters),
                tone=primary.default_tone,
                phase=primary.current_phase,
            ))
            primary.beat_count += 1
            primary.last_beat_at = time_step
            self._beat_history.append((time_step, primary.line_id))

        # 2. 检查交叉点——另一条线是否应在本步与主线交汇
        for other in active:
            if other.line_id == (primary.line_id if primary else ''):
                continue
            if self._should_intersect(primary, other, time_step):
                beats.append(StoryBeat(
                    line_id=other.line_id, time_step=time_step,
                    beat_type='intersection', priority=other.priority,
                    pov_char=self._rng.choice(other.pov_characters),
                    tone='tense',  # 交叉点天然带有戏剧张力
                    phase=other.current_phase,
                    intersects_with=primary.line_id if primary else '',
                ))
                other.beat_count += 1
                other.last_beat_at = time_step
                other.intersection_ready = False
                primary.intersection_ready = False
                self._intersection_points.append({
                    'time': time_step,
                    'lines': [primary.line_id, other.line_id],
                })

        # 3. ★ P2：检查汇聚点——当多条线满足汇聚条件时触发多POV交替叙述
        triggered_convergences = self._arc_mgr.check_and_trigger(
            self._lines, time_step, self._rng)
        for cp in triggered_convergences:
            # 提升所有参与线的张力（汇聚自带戏剧性）
            for lid in cp.line_ids:
                line = self._lines.get(lid)
                if line:
                    line.tension = min(10, line.tension + cp.tension_boost)
            # 生成多POV汇聚beat序列
            conv_beats = self._arc_mgr.build_convergence_beats(
                cp, time_step, self._lines)
            beats.extend(conv_beats)
            self._intersection_points.append({
                'time': time_step,
                'lines': cp.line_ids,
                'convergence': cp.convergence_id,
                'label': cp.label,
            })

        # 4. 如果有 D-plot（世界NPC线）且该世界活跃，偶尔插入
        d_lines = [l for l in active if l.line_type == StorylineType.D_PLOT]
        if d_lines and time_step % 5 == 0:
            dl = self._rng.choice(d_lines)
            beats.append(StoryBeat(
                line_id=dl.line_id, time_step=time_step,
                beat_type='atmosphere', priority=1,
                pov_char=self._rng.choice(dl.pov_characters),
                tone=dl.default_tone,
                phase=dl.current_phase,
            ))

        # 5. 推进各线弧光
        for line in active:
            line.advance_phase(0.03)

        # 6. ★ P2：推进全局叙事弧阶段
        self._arc_mgr.advance_stage(self._lines)

        # 7. ★ P3：anti_chaos——避免同一 section 内连续重复同一 POV 角色
        #    （来自 pov_timeline.json 的 anti_chaos.forbid_consecutive_same_pov；
        #    确定性：仅在本 tick 已产出的 beats 内、于该 beat 所属线的候选角色中重选）
        if self._anti_chaos.get('forbid_consecutive_same_pov'):
            _seen = set()
            for _b in beats:
                if _b.pov_char in _seen:
                    _ln = self._lines.get(_b.line_id)
                    _alts = [p for p in (_ln.pov_characters if _ln else []) if p != _b.pov_char]
                    if _alts:
                        _b.pov_char = self._rng.choice(_alts)
                _seen.add(_b.pov_char)

        return beats

    def _pick_primary_line(self, active: list[Storyline], time_step: int) -> Optional[Storyline]:
        """选择本步的主线——优先考虑优先级 + 距上次 beat 的间隔。"""
        candidates = []
        for line in active:
            gap = time_step - line.last_beat_at
            # 如果距上次 beat 超过 beat_interval，优先调度
            if gap >= line.beat_interval:
                candidates.append((line.priority + min(gap, 10) * 0.1, line))
        if not candidates:
            # 全部都不够间隔 → 选最近没出过的
            candidates = [(time_step - l.last_beat_at, l) for l in active]
        candidates.sort(key=lambda x: -x[0])  # 降序：高优先级优先
        if candidates:
            return candidates[0][1]
        return active[0] if active else None

    def _should_intersect(self, a: Optional[Storyline], b: Storyline,
                          time_step: int) -> bool:
        """判断两条线是否应在当前步交叉。"""
        if a is None:
            return False
        # 双方都在可交叉列表中
        if b.line_id not in a.can_intersect_with:
            return False
        if a.line_id not in b.can_intersect_with:
            return False
        # 至少一方处于高张力状态
        if a.tension < 6 and b.tension < 6:
            return False
        # 最近 3 步内已经交叉过 → 不重复
        for ip in self._intersection_points[-3:]:
            if a.line_id in ip['lines'] and b.line_id in ip['lines']:
                return False
        # 概率触发（高张力时更容易触发）
        prob = 0.15 + max(a.tension, b.tension) * 0.05
        return self._rng.random() < prob

    # -- 查询 API -----------------------------------------------------------
    def recent_beats(self, n: int = 10) -> list[tuple[int, str]]:
        return self._beat_history[-n:]

    def line_distribution(self) -> dict[str, int]:
        """各条线的 beat 分布统计。"""
        dist = {}
        for _, lid in self._beat_history:
            dist[lid] = dist.get(lid, 0) + 1
        return dist

    # -- 默认棋盘构建 -------------------------------------------------------
    @classmethod
    def default_board(cls, seed: int = None,
                      worlds_config: list[dict] = None) -> StoryBoard:
        """构建《万界归墟》默认棋盘布局。

        A-plot: 林朔主线——碎片回收、世界解锁、真相揭示
        B-plot: 唐川/玩家线——真相发现、社区组织、玩家自主
        C-plot: 对抗线——代理人渗透、源能波动、祂们威胁
        D-plot: 世界NPC线——根据 worlds_config 动态生成

        worlds_config: [{'name': '归墟', 'enabled': True, 'pov': '林朔'}, ...]
        """
        board = cls(seed=seed,
                   arc_manager=NarrativeArcManager.default_for_wanjie())
        random.Random(seed)

        # 解析配置
        if worlds_config is None:
            worlds_config = [
                {'name': '归墟', 'enabled': True, 'pov': '林朔'},
                {'name': '武侠·苍云之殇', 'enabled': True, 'pov': '叶琳'},
                {'name': '末日废土', 'enabled': True, 'pov': ''},
            ]
        enabled = [w for w in worlds_config if w.get('enabled', True)]

        # B-plot 绑定：取第一个启用世界（一般为归墟中枢）
        b_world = enabled[0]['name'] if enabled else '归墟'

        # A/B/C 三线：POV 角色与编排参数来自 pov_assignment.json（默认林朔/唐川/白夜），
        # 作者可改 JSON 调整选角与编排，无需动代码。B-plot 世界名动态取首个启用世界。
        _ROLE_TYPE = {'a_plot': StorylineType.A_PLOT, 'b_plot': StorylineType.B_PLOT, 'c_plot': StorylineType.C_PLOT}
        _TL_INTERVALS = _POV_TIMELINE.get('beat_intervals', {}) or {}
        for _rk in ('a_plot', 'b_plot', 'c_plot'):
            _r = _POV_ASSIGNMENT['plot_roles'][_rk]
            _world_name = _r.get('world_name') or (b_world if _rk == 'b_plot' else '')
            # ★ P3：各线 beat 间隔由 pov_timeline.json 驱动（作者可配置，非硬编码）
            _bi = _TL_INTERVALS.get(_rk, _r['beat_interval'])
            board.add_line(Storyline(
                line_id=_r['line_id'],
                line_type=_ROLE_TYPE[_rk],
                label=_r['label'],
                world_name=_world_name,
                pov_characters=list(_r['pov_characters']),
                default_tone=_r['default_tone'],
                tension_baseline=_r['tension_baseline'],
                priority=_r['priority'],
                beat_interval=_bi,
                can_intersect_with=list(_r['can_intersect_with']),
                preferred_ops=list(_r['preferred_ops']),
                narrative_themes=list(_r['narrative_themes']),
            ))

        # D-plot: 世界NPC线——根据 worlds_config 动态生成
        for w in enabled:
            pov = w.get('pov', '').strip()
            if not pov:
                continue
            board.add_line(Storyline(
                line_id=f'd_{w["name"].replace("·", "_").replace(" ", "_")}',
                line_type=StorylineType.D_PLOT,
                label=f'{w["name"]}·{pov}',
                world_name=w['name'],
                pov_characters=[pov],
                default_tone='neutral',
                tension_baseline=4,
                priority=1,
                beat_interval=_TL_INTERVALS.get('d_plot', 8),
                can_intersect_with=['b_tang_chuan'],
                preferred_ops=['scene', 'emotion', 'action'],
                narrative_themes=[w['name'], pov],
            ))

        return board

    def add_world_line(self, world_name: str, npc_name: str,
                       label: str = '', themes: list[str] = None):
        """为一个新解锁的世界添加 D-plot 故事线。"""
        line_id = f'd_{world_name.replace("·", "_").replace(" ", "_")}_{npc_name}'
        self.add_line(Storyline(
            line_id=line_id,
            line_type=StorylineType.D_PLOT,
            label=label or f'{world_name}·{npc_name}',
            world_name=world_name,
            pov_characters=[npc_name],
            default_tone='neutral',
            tension_baseline=3,
            priority=1,
            beat_interval=10,
            can_intersect_with=['b_tang_chuan'],
            preferred_ops=['scene', 'emotion', 'action'],
            narrative_themes=themes or [],
        ))


# ---------------------------------------------------------------------------
# 叙事单元（棋盘上的一格）
# ---------------------------------------------------------------------------
@dataclass
class StoryBeat:
    """棋盘上的一个叙事单元——某条故事线在某个时间步的一个场景。"""
    line_id: str
    time_step: int
    beat_type: str          # primary / intersection / atmosphere / flashback / convergence
    priority: int = 1
    pov_char: str = ''
    tone: str = 'neutral'
    phase: ArcPhase = ArcPhase.ESTABLISH
    intersects_with: str = ''      # 如果是交叉 beat，与哪条线交叉
    convergence_id: str = ''       # ★ P2：如果是汇聚 beat，属于哪个汇聚点
    convergence_pov_index: int = 0 # ★ P2：汇聚多POV序列中的索引（0=第一个视角）


# ---------------------------------------------------------------------------
# 汇聚点定义（P2：多线叙事弧汇聚）
# ---------------------------------------------------------------------------
@dataclass
class ConvergencePoint:
    """定义多条故事线在哪个阶段、围绕什么事件汇聚。

    参考冰与火之歌的多POV处理：同一场战役/灾难/揭示，从不同角色视角各写一段，
    读者看到事件的全貌，但每个角色只看到自己能看到的碎片。
    """
    convergence_id: str                         # 汇聚点唯一标识
    label: str                                  # 人类可读标签
    line_ids: list[str]                         # 参与汇聚的故事线ID列表
    trigger_phase: ArcPhase = ArcPhase.CONFLICT # 在哪个弧光阶段触发
    trigger_progress_min: float = 0.5           # 阶段进度达到此阈值后可触发
    shared_event_description: str = ''          # 共享的事件描述（所有POV围绕此事件）
    world_name: str = ''                        # 汇聚发生的世界
    pov_sequence: list[str] = field(default_factory=list)  # POV轮替顺序（如 ['林朔','唐川','白夜']）
    tension_boost: int = 3                      # 张力提升量（汇聚自带戏剧性）
    one_shot: bool = True                       # 是否只触发一次
    triggered: bool = False                     # 是否已触发


class NarrativeArcManager:
    """叙事弧管理器——协调多条线从独立推进到汇聚再到尾声。

    工作流程：
      1. SETUP 阶段：各线各自建立
      2. RISE 阶段：各线独立发展，张力逐渐累积
      3. CONVERGE 阶段：检查汇聚条件 → 触发多POV汇聚 render
      4. CLIMAX 阶段：所有汇聚线在同一事件中达到高潮
      5. FALL 阶段：交代余波、角色各自走向新的平衡
    """

    def __init__(self):
        self._convergence_points: list[ConvergencePoint] = []
        self._global_stage: ArcStage = ArcStage.SETUP

    def add_convergence(self, cp: ConvergencePoint):
        """注册一个汇聚点。"""
        self._convergence_points.append(cp)

    def active_convergences(self) -> list[ConvergencePoint]:
        """返回所有未触发的汇聚点。"""
        return [cp for cp in self._convergence_points if not cp.triggered]

    def check_and_trigger(self, lines: dict[str, Storyline],
                          time_step: int, rng: random.Random) -> list[ConvergencePoint]:
        """检查汇聚条件，返回本步应触发的汇聚点列表。

        触发条件：
        1. 所有参与线的当前阶段 >= 汇聚点要求的触发阶段
        2. 至少一半参与线的阶段进度 >= 触发进度阈值
        3. 概率触发（进度越高越容易触发）
        """
        triggered = []
        for cp in self._convergence_points:
            if cp.triggered and cp.one_shot:
                continue

            # 检查所有参与线是否满足阶段条件
            all_ready = True
            ready_count = 0
            for lid in cp.line_ids:
                line = lines.get(lid)
                if not line:
                    all_ready = False
                    break
                phases = list(ArcPhase)
                if phases.index(line.current_phase) < phases.index(cp.trigger_phase):
                    all_ready = False
                    break
                if line.phase_progress >= cp.trigger_progress_min:
                    ready_count += 1

            if not all_ready:
                continue

            # 至少一半线进度达标 + 概率触发
            min_ready = max(1, len(cp.line_ids) // 2)
            if ready_count >= min_ready:
                max_progress = max(
                    (lines[lid].phase_progress for lid in cp.line_ids if lid in lines),
                    default=0)
                prob = 0.1 + max_progress * 0.3
                if rng.random() < prob:
                    cp.triggered = True
                    triggered.append(cp)

        return triggered

    def build_convergence_beats(self, cp: ConvergencePoint,
                                 time_step: int,
                                 lines: dict[str, Storyline]) -> list[StoryBeat]:
        """为一个汇聚点生成多POV beat序列。

        每个POV角色产生一个 beat，beat_type='convergence'，
        这些 beat 共享同一个 convergence_id，SceneDirector 负责将它们
        编织成一段多视角交替叙述。

        Args:
            cp: 汇聚点定义
            time_step: 当前时间步
            lines: 所有故事线字典 {line_id: Storyline}，用于解析POV→line_id映射
        """
        beats = []
        povs = cp.pov_sequence if cp.pov_sequence else []
        for i, pov_char in enumerate(povs):
            # 找到这个POV角色属于哪条故事线
            line_id = ''
            for lid in cp.line_ids:
                line = lines.get(lid)
                if line and pov_char in line.pov_characters:
                    line_id = lid
                    break
            # 如果没找到精确匹配，使用汇聚点第一条参与线
            if not line_id and cp.line_ids:
                line_id = cp.line_ids[0]

            beats.append(StoryBeat(
                line_id=line_id,
                time_step=time_step,
                beat_type='convergence',
                priority=5,  # 汇聚点优先级最高
                pov_char=pov_char,
                tone='tense',
                convergence_id=cp.convergence_id,
                convergence_pov_index=i,
            ))
        return beats

    @property
    def global_stage(self) -> ArcStage:
        return self._global_stage

    def advance_stage(self, lines: dict[str, Storyline]):
        """根据各线进度推进全局叙事弧阶段。"""
        if not lines:
            return

        phases = list(ArcPhase)
        avg_phase_idx = sum(phases.index(l.current_phase) for l in lines.values()) / len(lines)
        avg_progress = sum(l.phase_progress for l in lines.values()) / max(1, len(lines))

        if avg_phase_idx >= 3.5 and avg_progress > 0.7:
            self._global_stage = ArcStage.CLIMAX
        elif avg_phase_idx >= 2.5:
            self._global_stage = ArcStage.CONVERGE
        elif avg_phase_idx >= 1.5:
            self._global_stage = ArcStage.RISE
        else:
            self._global_stage = ArcStage.SETUP

        # 检查汇聚点是否全部触发 → 进入FALL
        if all(cp.triggered for cp in self._convergence_points if cp.one_shot):
            if self._global_stage == ArcStage.CLIMAX and avg_progress > 0.8:
                self._global_stage = ArcStage.FALL

    # -- 默认汇聚点配置（《万界归墟》） --

    @classmethod
    def default_for_wanjie(cls) -> NarrativeArcManager:
        """构建《万界归墟》的默认叙事弧汇聚方案。

        三个关键汇聚点：
        1. 苍云之殇汇聚：林朔（A线）+ 叶琳（D线）+ 白夜（C线）在苍云山交汇
        2. 废土抉择汇聚：林朔（A线）+ 唐川（B线）+ 代理人（C线）在末日废土交汇
        3. 最终真相汇聚：所有线在归墟中枢汇聚，揭示第47次循环真相
        """
        mgr = cls()

        # 汇聚点来自 event_spine.json（默认万界归墟三汇聚），作者可改 JSON 调整。
        _phase_map = {_p.name: _p for _p in ArcPhase}
        for _cp in _EVENT_SPINE['convergence_points']:
            mgr.add_convergence(ConvergencePoint(
                convergence_id=_cp['convergence_id'],
                label=_cp['label'],
                line_ids=list(_cp['line_ids']),
                trigger_phase=_phase_map[_cp['trigger_phase']],
                trigger_progress_min=_cp['trigger_progress_min'],
                shared_event_description=_cp['shared_event_description'],
                world_name=_cp['world_name'],
                pov_sequence=list(_cp['pov_sequence']),
                tension_boost=_cp['tension_boost'],
                one_shot=_cp.get('one_shot', True),
            ))

        return mgr
