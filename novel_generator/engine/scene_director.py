# -*- coding: utf-8 -*-
"""SceneDirector —— 事件驱动 + 空间连续的生成导演。

替代 WordCountDirector + EmergentOrchestrator。
不再通过「节拍→算子序列」的机械流水线生成，而是：
  1. 读世界地图 → 确定"在哪里"
  2. 读时间轴 → 检查"正在发生什么"
  3. 读角色状态 → 决定"谁做什么"
  4. 综合上述 → 自然语言场景

设计要点：
  - 取消 OpType 硬配额——段落类型由当前情境决定，不是固定比例。
  - 取消机械张力随机游走——张力锚定到当前区域危险度 + 事件严重性。
  - 空间连续性——角色在地图上移动，访问邻接区域，避免瞬移。
  - 事件密度自适应——拥挤的区域多发生事件，安静的区域有更多描写空间。
"""
from __future__ import annotations
import logging
import os
import json
import random
import time
from dataclasses import dataclass, field
from typing import Optional

from .world_state import WorldStateManager, Region
from .timeline import Timeline, Event, EventScope
from .storyline import StoryBoard, StoryBeat, Storyline, StorylineType, ArcPhase
from .narrative_context import NarrativeContext
from .beat_orchestrator import OpType, VoiceOperation
from .knowledge_graph import KnowledgeGraph

_logger = logging.getLogger('novel.scene_director')


# ---------------------------------------------------------------------------
# 场景上下文
# ---------------------------------------------------------------------------
@dataclass
class SceneContext:
    """一个场景生成的上下文——替代原有的 NarrativeContext + NarrativeState 组合。"""
    # 空间
    world_name: str
    region: Region                      # 当前区域
    neighbor_regions: list[str] = field(default_factory=list)  # 可达邻接区域

    # 时间
    time_step: int = 0
    time_of_day: str = 'day'            # day / dusk / night / dawn
    events_active: list[Event] = field(default_factory=list)  # 当前触发的事件

    # 角色
    pov_character: str = '林朔'
    characters_here: list[str] = field(default_factory=list)  # 在此区域的角色

    # 叙事基调
    tension: int = 3                    # 1-10，由区域危险度+事件严重性决定
    mood: str = 'neutral'               # dark / tense / calm / mysterious / hopeful
    pace: str = 'medium'                # slow / medium / fast / urgent

    # 伏笔/进度
    pending_foreshadowing: int = 0
    arc_progress: float = 0.0

    # 缓存
    world_terms: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# 角色模拟器
# ---------------------------------------------------------------------------
@dataclass
class CharacterState:
    """角色的运行时状态。"""
    name: str
    current_world: str = '归墟'
    current_region: str = '归墟·中心'
    goal: str = 'explore'               # explore / investigate / fight / flee / rest / talk
    mood_modifier: str = 'neutral'
    energy: int = 100                   # 精力 0-100
    personality_tag: str = ''
    corruption_level: int = 0           # 腐化程度 0-10（叶琳专用，其余角色默认0）
    last_action: str = ''


class CharacterSim:
    """轻量角色模拟——每个角色有位置、目标、精力，自主决策。"""

    def __init__(self, plot_state, world_manager: WorldStateManager, rng: random.Random):
        self._ps = plot_state
        self._wm = world_manager
        self._rng = rng
        self._chars: dict[str, CharacterState] = {}
        self._init_from_plot_state()

    def _init_from_plot_state(self):
        chars_data = self._ps.state.get('characters', {})
        for name, data in chars_data.items():
            if name in ('墟核', '玩家群体'):
                continue
            cs = CharacterState(
                name=name,
                current_world='归墟',
                current_region=f'{data.get("location", "归墟")}·中心',
                mood_modifier=data.get('emotional_state', 'neutral'),
                personality_tag=data.get('personality_tag', ''),
                corruption_level=data.get('corruption_level', 0),
                goal=self._rng.choice(['explore', 'rest', 'explore', 'investigate']),
            )
            self._chars[name] = cs

    def get(self, name: str) -> Optional[CharacterState]:
        return self._chars.get(name)

    def chars_in_region(self, world_name: str, region_name: str) -> list[str]:
        return [name for name, cs in self._chars.items()
                if cs.current_world == world_name and cs.current_region == region_name]

    def move_to(self, name: str, target_region: str):
        cs = self._chars.get(name)
        if cs:
            cs.current_region = target_region
            cs.energy = max(0, cs.energy - 10)

    def switch_char_world(self, name: str, world_name: str):
        """将角色切换到指定世界，并自动定位到该世界的中心区域。"""
        cs = self._chars.get(name)
        if cs and cs.current_world != world_name:
            cs.current_world = world_name
            cs.current_region = f'{world_name}·中心'
            cs.energy = max(0, cs.energy - 5)

    def decide_action(self, name: str, scene: SceneContext) -> str:
        """角色自主决策下一步行动。"""
        cs = self._chars.get(name)
        if not cs:
            return 'observe'

        # 精力过低 → 休息
        if cs.energy < 20:
            return 'rest'

        # 高危险区域 → 战斗或逃跑
        if scene.tension >= 8:
            return self._rng.choice(['react', 'fight', 'fight', 'flee'])

        # 有事件发生 → 调查
        if scene.events_active:
            return self._rng.choice(['investigate', 'react', 'observe'])

        # 默认 → 探索/观察
        actions = ['observe', 'explore', 'move', 'observe', 'decide']
        if scene.neighbor_regions:
            actions.append('move')
        return self._rng.choice(actions)

    def tick(self):
        """角色精力自然恢复。"""
        for cs in self._chars.values():
            cs.energy = min(100, cs.energy + self._rng.randint(1, 5))


# ---------------------------------------------------------------------------
# 场景导演
# ---------------------------------------------------------------------------

# POV 声音→叙述口吻映射内容已外置到 word_banks/narrative/voice_flavours.json，
# 便于维护与扩展；此处统一加载为模块级字典，供类属性引用。
_VOICE_FLAVOUR_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "word_banks", "narrative", "voice_flavours.json")
with open(_VOICE_FLAVOUR_PATH, encoding="utf-8") as _vf_f:
    _VOICE_FLAVOUR_POOL = json.load(_vf_f)["flavours"]

# ★ P3：POV 新词库加载（内省 / 视角透镜 / 多立场解读 / 视角类型）
#   这些词库是"作者可配置"的叙事系统数据，被引擎实际选用，而非装饰。
_POV_NARRATIVE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "word_banks", "narrative")

def _load_pov_bank(name):
    with open(os.path.join(_POV_NARRATIVE_DIR, name), encoding="utf-8") as _f:
        return json.load(_f)

_POV_INTERIORITY = _load_pov_bank("interiority.json")      # 内省 / 心理活动
_POV_LENSES = _load_pov_bank("pov_lenses.json")             # 视角透镜（按角色/性格）
_POV_INFO_ASYM = _load_pov_bank("info_asymmetry.json")      # 信息不对称 / 多立场解读
_POV_TYPES = _load_pov_bank("pov_types.json")               # 视角类型目录

# 故事线类型 → 视角角色（pov_lenses.by_role 透镜）与 POV 类型（pov_types）
_LINE_ROLE = {
    StorylineType.A_PLOT: "protagonist",
    StorylineType.B_PLOT: "player_proxy",
    StorylineType.C_PLOT: "observer",
    StorylineType.D_PLOT: "bystander",
}
_LINE_POV_TYPE = {
    StorylineType.A_PLOT: "deep_pov",
    StorylineType.B_PLOT: "first_person",
    StorylineType.C_PLOT: "third_limited",
    StorylineType.D_PLOT: "third_limited",
}
# POV 类型 → 内省类别（pov_types 驱动内省注入风格，作者改 JSON 即改心理刻画强度）
_POV_TYPE_INTERIORITY = {
    "first_person": "soliloquy",
    "deep_pov": "soliloquy",
    "second_person": "soliloquy",
    "third_limited": "emotion_flow",
    "omniscient": "emotion_flow",
    "unreliable": "sensory_introspection",
    "objective_data": "sensory_introspection",
}


class SceneDirector:
    """事件驱动 + 空间连续 + 棋盘多线叙事的场景生成导演。

    棋盘布局（美剧编剧方法论）：
      A-plot: 林朔主线（碎片回收/世界解锁）—— 几乎每段都出现
      B-plot: 唐川玩家线（真相发现/社区组织）—— 每 3 段一次
      C-plot: 对抗线（代理人/祂们）—— 每 5 段一次，高张力
      D-plot: 世界NPC线（叶琳等）—— 每 8 段一次

      交叉点：当两条线的高张力场景在物理/信息上可相遇时触发。
    """

    def __init__(self, integrated_gen, plot_state,
                 world_manager: WorldStateManager, timeline: Timeline,
                 storyboard: StoryBoard,
                 config: dict, output_dir: str, seed: int = None,
                 phase_world_map: dict = None):
        self._gen = integrated_gen
        self._ps = plot_state
        self._wm = world_manager
        self._timeline = timeline
        self._board = storyboard        # 棋盘——多线叙事调度
        self._cfg = config
        self._output_dir = output_dir
        self._rng = random.Random(seed)

        # 角色模拟器
        self._chars = CharacterSim(plot_state, world_manager, self._rng)

        # ★ P1：信息不对称引擎——管理每个角色对世界真相的认知差异
        self._knowledge = KnowledgeGraph.default_for_wanjie(seed=seed)

        # 阶段→世界映射（可外部覆盖）
        if phase_world_map:
            # UI 传来的 key 是字符串，转换为 ArcPhase 枚举
            self._phase_world_map = {}
            for k, v in phase_world_map.items():
                try:
                    self._phase_world_map[ArcPhase[k]] = v
                except KeyError:
                    pass  # 忽略不认识的阶段名
        else:
            self._phase_world_map = {
                ArcPhase.ESTABLISH: '归墟',
                ArcPhase.REVEAL: '归墟',
                ArcPhase.CONFLICT: '武侠·苍云之殇',
                ArcPhase.CHOICE: '末日废土',
                ArcPhase.TRANSFORM: '归墟',
            }

        # 全局状态
        self._total_chars: int = 0
        self._passage_no: int = 0
        self._recent_regions: list[str] = []    # 最近访问的区域（抗重复）
        self._recent_event_types: list[str] = []  # 最近的事件类型

        # 跨段去重
        self._long_counter: dict = {}

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def generate(self, target_chars: int, resume: bool = False) -> str:
        cfg = self._cfg
        if resume:
            self._total_chars = self._ps.state.get('current_chars', 0)
            self._passage_no = self._ps.state.get('current_passage', 0)

        max_p = cfg.get('max_passages') or max(50, (target_chars // cfg['min_passage_chars']) * 3)
        buffer = []
        if resume:
            prev_text = self._ps.state.get('last_output_text', '')
            if prev_text:
                buffer = prev_text.split('\n\n')
                _logger.info(f'[棋盘导演] 恢复断点 | 已载入 {self._total_chars:,}字 / '
                             f'{len(buffer)} 段落')
        t0 = time.time()

        _logger.info(f'[棋盘导演] 启动 | 目标 {target_chars:,}字 | '
                     f'故事线: {len(self._board.active_lines)}条')

        while self._total_chars < target_chars and self._passage_no < max_p:
            # 1. 世界时钟前进
            self._wm.tick()
            world_state = self._build_world_state_snapshot()

            # 2. 检查时间轴事件
            fired_events = self._timeline.tick(self._wm.global_time, world_state)
            for ev in fired_events:
                if ev.scope == EventScope.WORLD and 'world' in ev.payload:
                    self._wm.unlock_world(ev.payload['world'])

            # 3. 棋盘调度——获取本段的多线叙事单元
            beats = self._board.tick(self._passage_no)
            if not beats:
                beats = [StoryBeat(line_id='a_lin_shuo', time_step=self._passage_no,
                                   beat_type='primary', pov_char='林朔')]

            # 字数达标接近时，缩小末段规模
            remaining = target_chars - self._total_chars
            if remaining < cfg['min_passage_chars']:
                break

            # 4. 渲染棋盘段——多条故事线编织成一个 section
            text = self._render_section(beats, fired_events, remaining)

            n = len(text)
            self._total_chars += n
            self._passage_no += 1
            buffer.append(text)

            # 5. 角色模拟 tick + 持久化
            self._chars.tick()
            if self._passage_no % cfg.get('save_every', 10) == 0:
                self._ps.state['current_chars'] = self._total_chars
                self._ps.state['current_passage'] = self._passage_no
                self._ps.save()

            if self._passage_no % cfg.get('log_every', 5) == 0:
                dist = self._board.line_distribution()
                _logger.info(
                    f'  第{self._passage_no}段 | {n}字 | '
                    f'累计{self._total_chars:,}/{target_chars:,} | '
                    f'线分布: {dist}'
                )

        elapsed = time.time() - t0
        _logger.info(f'[棋盘导演] 完成 | {self._total_chars:,}字 | '
                     f'{self._passage_no}段 | {elapsed:.1f}s | '
                     f'交叉点: {len(self._board._intersection_points)}个')
        return self._finalize(buffer)

    # ------------------------------------------------------------------
    # 棋盘段渲染——多条故事线编织成一个 section
    # ------------------------------------------------------------------
    def _render_section(self, beats: list[StoryBeat],
                        fired_events: list[Event], remaining: int) -> str:
        """将同一时间步的多条故事线编织成一个完整的叙事段。

        Section 结构（棋盘布局）：
          [A-plot 场景]        ← 林朔在当前区域的探索/行动   (主线，~60%篇幅)
          ——                  ← 视觉分隔
          [B-plot 场景]        ← 唐川/玩家线的平行进展        (辅线，~25%篇幅)
          ——
          [交叉点 / C-plot]   ← 如果本步有交叉或对抗线推进    (调味，~15%篇幅)
          ——
          [汇聚块]            ← ★ P2：多POV交替叙述同一事件（无内部分隔，外有边界）
        """
        section_parts = []
        beat_lines = {}  # line_id → line_label 映射

        i = 0
        while i < len(beats):
            beat = beats[i]
            line = self._board.line(beat.line_id)
            label = line.label if line else beat.line_id
            beat_lines[beat.line_id] = label

            # ★ P2：检测汇聚块——连续的 convergence beat 共享同一 convergence_id
            if beat.beat_type == 'convergence' and beat.convergence_id:
                conv_id = beat.convergence_id
                conv_texts = []
                while i < len(beats) and beats[i].beat_type == 'convergence' \
                        and beats[i].convergence_id == conv_id:
                    conv_beat = beats[i]
                    bt = self._render_beat(conv_beat, fired_events,
                                          is_primary=False,
                                          is_intersection=False)
                    if bt.strip():
                        conv_texts.append(bt)
                    i += 1
                # 汇聚块内部用短分隔，外部有完整的视觉边界
                if conv_texts:
                    block = '\n'.join(conv_texts)
                    section_parts.append(block)
                continue

            # 常规 beat 渲染
            beat_text = self._render_beat(beat, fired_events,
                                         is_primary=(i == 0),
                                         is_intersection=(beat.beat_type == 'intersection'))
            if beat_text.strip():
                section_parts.append(beat_text)
            i += 1

        # 用分隔线连接
        separator = '\n\n' + '—' * 30 + '\n\n'
        return separator.join(section_parts)

    def _render_beat(self, beat: StoryBeat, fired_events: list[Event],
                     is_primary: bool = False, is_intersection: bool = False) -> str:
        """渲染单个故事线的一个 beat。"""
        line = self._board.line(beat.line_id)
        if not line:
            return ''

        # ★ 根据故事线确定世界并切换
        world = self._resolve_world_for_line(line)
        world_changed = (world and world != self._wm._active_world)
        if world_changed:
            self._wm.switch_to(world)
            # 把当前 beat 的 POV 角色也移动到新世界
            for pov in line.pov_characters:
                self._chars.switch_char_world(pov, world)

        ctx = NarrativeContext()
        ctx.world_name = self._wm._active_world
        ctx.beat = 'generic'
        ctx.volume = 1

        # 获取 POV 角色的状态
        cs = self._chars.get(beat.pov_char)
        region_name = cs.current_region if cs else f'{self._wm._active_world}·中心'
        ctx.scene_spot = region_name
        ctx.tension_level = line.tension

        # ★ P0修复：将 personality_tag 和 corruption_level 注入 CharacterSnapshot
        # 此前这两个字段定义在 CharacterSnapshot 上但从未被赋值，属于死字段
        ctx.add_character(beat.pov_char,
                         emotional_state=cs.mood_modifier if cs else 'neutral',
                         personality_tag=cs.personality_tag if cs else '',
                         corruption_level=cs.corruption_level if cs else 0)

        # ★ P0修复：提取 POV 角色的声音特征（voice_hint）
        # 此前 voice_hint() 被计算但从未在渲染中消费——不同 POV 角色输出雷同
        pov_snapshot = ctx.get_character(beat.pov_char)
        voice = pov_snapshot.voice_hint() if pov_snapshot else 'voice_neutral'
        personality = pov_snapshot.personality_tag if pov_snapshot else ''
        corruption = pov_snapshot.corruption_level if pov_snapshot else 0

        # ★ P1：信息不对称——查询当前POV角色的认知状态
        # 该角色知道什么、不知道什么、误信了什么，决定了叙述角度
        knowledge_gap = self._knowledge.render_gap_hint(beat.pov_char)

        # ★ P1：世界切换时触发知识发现——新世界可能揭示新真相
        if world_changed or self._passage_no == 0:
            discovered = self._knowledge.discover_in_world(
                beat.pov_char, self._wm._active_world, self._passage_no)
            if discovered:
                _logger.debug(f'[知识发现] {beat.pov_char} 在 {self._wm._active_world} '
                             f'发现了: {discovered}')

        # ★ P1：交叉点时角色间共享信息
        if is_intersection and beat.intersects_with:
            other_line = self._board.line(beat.intersects_with)
            if other_line and other_line.pov_characters:
                other_pov = other_line.pov_characters[0]
                shared = self._knowledge.share_on_intersection(
                    beat.pov_char, other_pov, self._passage_no)
                if shared:
                    _logger.debug(f'[信息共享] {beat.pov_char} ↔ {other_pov}: {shared}')

        # 世界术语
        if hasattr(self._gen, '_voice'):
            ctx.world_terms = self._gen._voice._world_term_pool(ctx.world_name)

        L = []

        # ★ P2：汇聚beat——多POV交替叙述同一事件
        if beat.beat_type == 'convergence':
            L = self._beat_convergence(ctx, beat, line, fired_events,
                                       voice=voice, personality=personality,
                                       corruption=corruption,
                                       knowledge_gap=knowledge_gap)

        # 根据故事线类型和弧光阶段决定内容策略
        elif line.line_type == StorylineType.A_PLOT:
            # 主线：重心在探索、发现、回收碎片
            L = self._beat_a_plot(ctx, beat, line, fired_events,
                                  voice=voice, personality=personality,
                                  corruption=corruption,
                                  knowledge_gap=knowledge_gap)

        elif line.line_type == StorylineType.B_PLOT:
            # 玩家线：重心在社区动态、真相拼图、对话
            L = self._beat_b_plot(ctx, beat, line, fired_events,
                                  voice=voice, personality=personality,
                                  corruption=corruption,
                                  knowledge_gap=knowledge_gap)

        elif line.line_type == StorylineType.C_PLOT:
            # 对抗线：重心在威胁信号、代理人活动、暗流
            L = self._beat_c_plot(ctx, beat, line, fired_events,
                                  voice=voice, personality=personality,
                                  corruption=corruption,
                                  knowledge_gap=knowledge_gap)

        elif line.line_type == StorylineType.D_PLOT:
            # 世界NPC线：重心在特定世界的角色弧
            L = self._beat_d_plot(ctx, beat, line, fired_events,
                                  voice=voice, personality=personality,
                                  corruption=corruption,
                                  knowledge_gap=knowledge_gap)

        else:
            L = [f'{beat.pov_char}在{region_name}。']

        # 交叉点标记
        if is_intersection and beat.intersects_with:
            other_label = self._board.line(beat.intersects_with)
            other_name = other_label.label if other_label else beat.intersects_with
            L.insert(0, f'[与「{other_name}」线交汇]')

        # 主线打区域标题
        if is_primary:
            L.insert(0, f'——{region_name}——')
            L.insert(1, '')

        # 氛围注入
        if hasattr(self._gen, '_voice'):
            flavour = self._gen._voice.render_world_flavour(ctx, prob=0.4, op_type='SCENE')
            if flavour:
                L.insert(-1 if len(L) > 1 else 0, flavour)

        # ★ P3：内省注入——深入人物心理（来自 interiority.json，按 POV 类型选类别）
        #   确定性：用本导演固定 RNG 选择；作者改 interiority.json / pov_types.json 即改心理刻画。
        if _POV_INTERIORITY:
            _ptype = _LINE_POV_TYPE.get(line.line_type if line else None, "third_limited")
            if _ptype not in _POV_TYPES:
                _ptype = "third_limited"
            _cat = _POV_TYPE_INTERIORITY.get(_ptype, "emotion_flow")
            _pool = _POV_INTERIORITY.get(_cat) or _POV_INTERIORITY.get("emotion_flow") or []
            if _pool and self._rng.random() < 0.45:
                _tpl = self._rng.choice(_pool)
                _char = self._ps.state['characters'].get(beat.pov_char, {})
                _emo = _char.get('emotional_state', '某种说不清的情绪')
                _line_content = {
                    '警觉': '必须保持清醒',
                    '兴奋': '心跳得比任何时候都快',
                    '绝望→希望': '黑暗中似乎有光',
                    '偏执': '绝不能相信任何人',
                    '信息受限': '还有很多不知道的事',
                    '游戏心态': '这不就是一场游戏吗',
                }.get(_emo, f'{_emo}的感觉涌上心头')
                L.append(_tpl.replace("{pov}", beat.pov_char).replace("{line}", _line_content))

        return '\n'.join(L)

    # ------------------------------------------------------------------
    # 世界解析——根据故事线确定当前应在哪个世界
    # ------------------------------------------------------------------

    def _resolve_world_for_line(self, line: Storyline) -> str:
        """解析一条故事线当前应处在哪个世界。

        优先级：
          1. Storyline.world_name 已显式指定 → 直接使用
          2. A-plot → 按弧光阶段映射（由 UI 配置的阶段-世界映射）
          3. C-plot → 跟随 A-plot 的世界
          4. 其它 → 归墟
        """
        # 显式绑定（B-plot、D-plot）
        if line.world_name:
            return line.world_name

        # A-plot：按阶段映射
        if line.line_type == StorylineType.A_PLOT:
            phase_world = self._phase_world_map.get(line.current_phase)
            if phase_world:
                return phase_world

        # C-plot：跟随 A-plot
        if line.line_type == StorylineType.C_PLOT:
            a_line = self._board.line('a_lin_shuo')
            if a_line:
                return self._resolve_world_for_line(a_line)

        return '归墟'

    # ------------------------------------------------------------------
    # 各故事线的 beat 渲染策略
    # ------------------------------------------------------------------
    def _beat_a_plot(self, ctx, beat, line, events,
                     voice='voice_neutral', personality='', corruption=0,
                     knowledge_gap='') -> list:
        """A-plot: 林朔主线——探索、遭遇、发现（POV声音 + 信息差注入）。"""
        L = []
        region = self._wm.active_map().region(ctx.scene_spot)
        danger = region.current_danger if region else 3

        # ★ P0修复：POV声音特征注入——角色情绪影响叙述口吻
        voice_flavour = self._voice_flavour_line(voice, corruption)

        # ★ P1：信息差注入——当前POV角色对世界的认知缺口
        if knowledge_gap and self._rng.random() < 0.35:
            L.append(f'（{knowledge_gap}）')

        # 场景描写
        scene_lines = self._gen._voice.render_scene_beat(ctx, 'default')
        if scene_lines:
            L.extend(scene_lines)

        # 危险区域 → 紧张遭遇
        if danger >= 6 and self._rng.random() < 0.4:
            L.append('')
            L.append(self._gen._voice._deal(
                f'danger::{ctx.scene_spot}',
                [f'{ctx.scene_spot}的空气中弥漫着不安——有什么在暗处窥视。',
                 '脚下的地面传来细微震动——不是地震，是某种大型存在的移动。',
                 f'远处传来一声低吼，{ctx.scene_spot}的黑暗深处亮起了两点光——那是眼睛。']))
            if voice_flavour:
                L.append(voice_flavour)
        else:
            # 正常探索 → 观察 + 行动
            action_char = ctx.get_character(beat.pov_char)
            if action_char:
                for act in ['observe', 'decide']:
                    text = self._gen._voice.render_character_action(action_char, act, ctx)
                    if text:
                        L.extend(['', text])
                        if voice_flavour:
                            L.append(voice_flavour)
                        break

        # 弧光阶段进度标记
        if line.phase_progress > 0.8 and line.current_phase != ArcPhase.TRANSFORM:
            L.append('')
            phase_hints = {
                ArcPhase.ESTABLISH: '他需要更多信息。碎片散落在十二个世界——每一个都不相同，但每一个都指向同一个中心。',
                ArcPhase.REVEAL: '真相像剥洋葱——每揭开一层，都让他更接近某个他不确定是否想知道的答案。',
                ArcPhase.CONFLICT: '他不是第一个锚定者。前面有四十六个——全部失败了。这个事实像一把刀悬在头顶。',
                ArcPhase.CHOICE: '选择的权利从未真正属于他——直到现在。他必须决定：继续按规则走，还是撕掉规则。',
            }
            hint = phase_hints.get(line.current_phase, '')
            if hint:
                L.append(hint)

        return L

    def _beat_b_plot(self, ctx, beat, line, events,
                     voice='voice_neutral', personality='', corruption=0,
                     knowledge_gap='') -> list:
        """B-plot: 玩家线——发现、组织、对话（POV角色驱动，非固定唐川）。"""
        L = []
        pov = beat.pov_char  # ★ P0修复：不再硬编码'唐川'，跟随当前beat的POV角色

        voice_flavour = self._voice_flavour_line(voice, corruption)

        # ★ P0修复：玩家社区的发现——以当前POV角色为主体
        player_templates = {
            '唐川': ['唐川盯着屏幕上的数据——这些数字不应该出现在一个游戏里。',
                     '玩家频道里炸开了锅。有人发现了一个新的碎片坐标。',
                     '论坛上的帖子被顶到了第一页：标题是"这不是游戏"。',
                     '唐川把几个公会会长拉进了私密频道。他要做一个决定。'],
        }
        default_templates = [f'{pov}发现了一些不对劲的东西——信息在流动，但方向不对。',
                             f'{pov}注意到玩家社区里的气氛变了。有人在问不该问的问题。',
                             f'{pov}翻看着聊天记录——每一条都像拼图的一角。',
                             f'{pov}揉了揉眼睛。屏幕上的数据跳了一下——不是bug。']

        pool = player_templates.get(pov, default_templates)
        L.append(self._gen._voice._deal(
            f'player_beat::{beat.time_step}::{pov}', pool))

        # ★ P1：信息差注入——玩家线善于拼图，但视角受限
        if knowledge_gap and self._rng.random() < 0.4:
            L.append(f'（{knowledge_gap}）')

        # 对话：以POV角色为主体，而非固定'唐川'
        if self._rng.random() < 0.5:
            dialogue = self._gen._dlg.generate('player_interaction',
                                               [pov, '考据狂魔'], {})
            if dialogue:
                L.extend(['', dialogue])

        if voice_flavour:
            L.append(voice_flavour)

        return L

    def _beat_c_plot(self, ctx, beat, line, events,
                     voice='voice_neutral', personality='', corruption=0,
                     knowledge_gap='') -> list:
        """C-plot: 对抗线——代理人活动、源能异常（POV角色视角 + 信息差）。"""
        L = []
        pov = beat.pov_char
        voice_flavour = self._voice_flavour_line(voice, corruption)

        # ★ P1：C-plot 信息差——对抗方可能掌握比主角更多的真相
        if knowledge_gap and self._rng.random() < 0.5:
            L.append(f'（{knowledge_gap}）')

        hints = [
            (f'{pov}的通讯断断续续。「代理人——在移动。祂们盯上了下一个碎片。」'
             f'他的机械义眼闪烁着不稳定的蓝光——每一次闪烁都意味着源能消耗。'),
            ('归墟星图的暗色区域扩大了一格。墟核没有任何解释——'
             '只有四个字的注释：「祂们曾至。」'),
            (f'渗透型代理人的信号出现了——不是在一个世界，是在三个世界同时。'
             f'就像是有人在下棋——而{pov}的每一步，祂们都已经提前看到了。'),
        ]
        L.append(self._rng.choice(hints))

        if voice_flavour:
            L.append(voice_flavour)

        # 高张力 → 揭示
        if line.tension >= 7:
            reveal = self._gen._voice.render_truth_reveal(ctx, min(4, int(line.phase_progress * 5) + 1))
            if reveal:
                L.extend([''] + reveal)

        return L

    def _beat_d_plot(self, ctx, beat, line, events,
                     voice='voice_neutral', personality='', corruption=0,
                     knowledge_gap='') -> list:
        """D-plot: 世界NPC线——特定世界角色的个人弧（POV+声音+信息差驱动）。"""
        L = []
        voice_flavour = self._voice_flavour_line(voice, corruption)

        # ★ P1：NPC线信息差——NPC可能知道一些主角不知道的局部真相
        if knowledge_gap and self._rng.random() < 0.35:
            L.append(f'（{knowledge_gap}）')

        action_char = ctx.get_character(beat.pov_char)
        if action_char:
            text = self._gen._voice.render_character_action(action_char, 'observe', ctx)
            if text:
                L.extend([text])
                # ★ P0修复：腐化程度影响NPC描写
                if corruption >= 5:
                    L.append('她的指尖泛着淡淡的紫色——那不是光，是源能侵蚀留下的痕迹。'
                             '每过一天，纹路就往上蔓延一点点。')
                if voice_flavour:
                    L.append(voice_flavour)
        else:
            L.append(f'{beat.pov_char}站在那里，望着远方。'
                     f'这个世界在改变——就像她/他自己一样。')
        return L

    # ------------------------------------------------------------------
    # ★ P2：汇聚beat渲染——多POV交替叙述同一事件（罗生门式温差）
    # ------------------------------------------------------------------
    def _beat_convergence(self, ctx, beat, line, events,
                          voice='voice_neutral', personality='',
                          corruption=0, knowledge_gap='') -> list:
        """渲染汇聚点的一个POV视角。

        汇聚点的每个POV角色都生成了一个 beat，这里渲染单个POV视角下的
        共享事件片段。多个汇聚beat被 _render_section() 连在一起后，
        读者会看到同一事件从 A→B→C 三个视角依次展开——每个视角带有
        不同的声音特征、信息差和情感滤镜。

        这是P2的核心：让多视角从"各行其是"变为"围绕同一事件的不同面向"。
        """
        L = []
        pov = beat.pov_char
        voice_flavour = self._voice_flavour_line(voice, corruption)
        pov_idx = beat.convergence_pov_index
        # ★ P3：视角角色（来自 pov_lenses.by_role）——驱动汇聚标识与透镜风味
        role = _LINE_ROLE.get(line.line_type if line else None, "observer")

        # 汇聚POV视角标记（罗生门标识）
        if pov_idx == 0:
            L.append(f'【{beat.convergence_id} · 汇聚事件】')
        # ★ P3：汇聚标识使用 pov_lenses.by_role[role].header 模板（作者可配置视角风味）
        _header_tpl = (_POV_LENSES.get("by_role", {}).get(role, {}).get("header")
                       or "——{pov}的视角——")
        try:
            L.append(_header_tpl.format(pov=pov))
        except Exception:
            L.append(f'——{pov}的视角——')
        L.append('')

        # 该POV角色的场景描写（带声音特征）
        scene_lines = self._gen._voice.render_scene_beat(ctx, 'default')
        if scene_lines:
            L.extend(scene_lines)

        # POV特有的行动——角色在当前汇聚事件中的反应
        action_char = ctx.get_character(pov)
        if action_char:
            text = self._gen._voice.render_character_action(action_char, 'react', ctx)
            if text:
                L.extend(['', text])
        else:
            L.append(f'{pov}目睹了眼前发生的一切。')

        # 声音特征注入
        if voice_flavour:
            L.append(voice_flavour)

        # 信息差注入——这个POV角色可能在汇聚事件中意识到新的真相
        if knowledge_gap:
            L.append(f'（{knowledge_gap}）')

        # 腐化感知层——高腐化角色的世界在扭曲
        if corruption >= 7:
            L.append('她的视野边缘漫起一层紫色——不是光，是世界本身在源能中溶解的痕迹。')

        # ★ P3：多立场解读（info_asymmetry.json）——同一事件的不同面向，读者站在当事人角度评判
        #   确定性：按汇聚序列索引选事件原型，再取该角色对应 role 的解读；作者改 JSON 即改立场。
        _stances = _POV_INFO_ASYM.get("same_event_stances", [])
        if _stances:
            _ev = _stances[pov_idx % len(_stances)]
            _reading = None
            for _s in _ev.get("stances", []):
                if _s.get("role") == role:
                    _reading = _s.get("reading")
                    break
            if not _reading and _ev.get("stances"):
                _reading = _ev["stances"][0].get("reading")
            if _reading:
                L.append(f'（{pov}的解读：{_reading}）')

        return L

    # ------------------------------------------------------------------
        # POV 声音→叙述口吻映射内容来自 voice_flavours.json（模块级 _VOICE_FLAVOUR_POOL）
    _VOICE_FLAVOUR_POOL = _VOICE_FLAVOUR_POOL

    def _voice_flavour_line(self, voice: str, corruption: int = 0) -> str:
        """P0修复：根据POV角色的声音特征，注入一句叙述口吻调味线。

        这是POV文风差异化的核心机制——不同情绪状态的视角角色，
        即使面对同一场景，也会因为声音特征不同而产生完全不同的叙述口吻。
        腐化程度 >= 5 的角色额外叠加一层侵蚀感。
        """
        pool = self._VOICE_FLAVOUR_POOL.get(voice, [])
        if not pool:
            return ''

        # 30% 概率跳过，避免每段都注入造成机械感
        if self._rng.random() > 0.3:
            return ''

        line = self._rng.choice(pool)

        # 腐化叠加：角色源能侵蚀严重时，额外追加扭曲感知
        if corruption >= 7 and self._rng.random() < 0.5:
            corruption_lines = [
                '视野边缘有一层淡淡的紫——不知道是错觉，还是源能侵蚀已经到了眼睛。',
                '她的指尖泛着微弱的紫光——不是灯光，是从骨子里透出来的。',
            ]
            line = f'{line} {self._rng.choice(corruption_lines)}'
        elif corruption >= 5 and self._rng.random() < 0.3:
            line = f'{line} 她下意识摸了摸手腕——那块皮肤最近总是发痒，像有什么要从里面长出来。'

        return line

    # ------------------------------------------------------------------
    # 场景上下文构建
    # ------------------------------------------------------------------
    def _build_world_state_snapshot(self) -> dict:
        """构建世界状态快照——供时间轴条件求值。"""
        active_map = self._wm.active_map()
        pov = self._chars.get('林朔')
        region = active_map.region(pov.current_region) if pov else None

        return {
            'danger': region.current_danger if region else 1,
            'category': region.category if region else 'wilderness',
            'visited': region.last_visited if region else 0,
            'unlocked_worlds': len(self._wm._unlocked_worlds),
            'global_time': self._wm.global_time,
        }

    def _build_scene_context(self, fired_events: list[Event]) -> SceneContext:
        active_map = self._wm.active_map()
        pov = self._chars.get('林朔') or CharacterState(name='林朔')
        region = active_map.region(pov.current_region)
        if not region:
            region = Region(name=f'{self._wm._active_world}·中心', category='town', danger=1)
            pov.current_region = region.name

        neighbors = active_map.neighbors(region.name)
        chars_here = self._chars.chars_in_region(self._wm._active_world, region.name)

        # 计算当前张力：区域危险度 + 事件加权
        event_severity = sum(
            {'danger_encounter': 3, 'battle_looming': 4, 'agent_threat_rising': 3,
             'mystery_deepening': 1, 'peaceful_interlude': -2, 'discovery': 1}
            .get(ev.narrative_hint, 1) for ev in fired_events
        )
        tension = max(1, min(10, region.current_danger + event_severity + self._rng.randint(-1, 1)))

        # 时间
        time_step = self._wm.global_time
        tod_cycle = ['dawn', 'day', 'day', 'day', 'dusk', 'night', 'night', 'night']
        time_of_day = tod_cycle[time_step % len(tod_cycle)]

        # 情绪基调
        if tension >= 8:
            mood = 'dark'
        elif tension >= 6:
            mood = 'tense'
        elif tension <= 2:
            mood = 'calm'
        elif any(ev.narrative_hint == 'discovery' for ev in fired_events):
            mood = 'hopeful'
        else:
            mood = 'neutral'

        # 节奏
        if any(ev.narrative_hint in ('battle_looming', 'danger_encounter') for ev in fired_events):
            pace = 'urgent'
        elif tension >= 7:
            pace = 'fast'
        elif tension <= 2:
            pace = 'slow'
        else:
            pace = 'medium'

        # 世界术语预加载
        world_terms = []
        if hasattr(self._gen, '_voice'):
            world_terms = self._gen._voice._world_term_pool(self._wm._active_world)

        # 伏笔状态
        pending = len(self._ps.get_pending_foreshadowing(self._passage_no))
        arc_progress = self._ps.state.get('truth_layer', 1) / 6.0

        return SceneContext(
            world_name=self._wm._active_world,
            region=region,
            neighbor_regions=neighbors,
            time_step=time_step,
            time_of_day=time_of_day,
            events_active=fired_events,
            pov_character=pov.name,
            characters_here=chars_here,
            tension=tension,
            mood=mood,
            pace=pace,
            pending_foreshadowing=pending,
            arc_progress=arc_progress,
            world_terms=world_terms,
        )

    # ------------------------------------------------------------------
    # 场景渲染
    # ------------------------------------------------------------------
    def _render_scene(self, scene: SceneContext, char_action: str,
                      remaining: int = 999999) -> str:
        """将场景上下文渲染为文本段落。

        不再使用 OpType 硬配额——根据场景自然决定该写什么：
          - 新区域首次访问 → 环境描写
          - 有事件触发 → 事件叙事
          - 多角色在场 → 对话/互动
          - 高危险 → 战斗/紧张描写
          - 低危险+无人 → 内心独白/观察
        """
        ctx = NarrativeContext()
        ctx.world_name = scene.world_name
        ctx.tension_level = scene.tension
        ctx.world_terms = scene.world_terms
        ctx.beat = 'generic'
        ctx.volume = 1
        ctx.scene_spot = scene.region.name

        # 角色同步
        for name in scene.characters_here:
            cs = self._chars.get(name)
            if cs:
                ctx.add_character(name, emotional_state=cs.mood_modifier)

        L = []
        events_log = []

        # === 场景头部：位置定位 ===
        L.append('')
        L.append(f'——{scene.region.name}——')
        L.append('')

        # === 1. 环境描写（scene总是有，密度由pace决定）===
        scene_lines = self._gen._voice.render_scene_beat(ctx, 'default')
        if scene_lines:
            L.extend(scene_lines)
        # 世界质感注入
        flavour = self._gen._voice.render_world_flavour(ctx, op_type='SCENE')
        if flavour:
            L.extend(['', flavour])

        # === 2. 事件响应 ===
        if scene.events_active:
            for ev in scene.events_active:
                hint = ev.narrative_hint
                if hint == 'danger_encounter':
                    # 危险遭遇 → 紧张动作
                    L.append('')
                    L.append(self._gen._voice._deal(
                        f'event::danger::{scene.region.name}',
                        [f'前方传来异响——{scene.region.name}的黑暗中有什么在移动。',
                         f'一阵冷风从背后掠过。{scene.region.name}不欢迎来访者。',
                         '脚下的地面在震动——不是地震，是某种大型生物的心跳。']))
                elif hint == 'battle_looming':
                    # 战斗即将爆发 → 战前气氛
                    battle_lines = self._gen._render_battle(ctx, VoiceOperation(OpType.BATTLE, intensity='high'))
                    if battle_lines:
                        L.extend([''] + battle_lines)
                    events_log.append('battle_at_' + scene.region.name)
                elif hint == 'discovery':
                    L.append('')
                    L.append(self._gen._voice._deal(
                        f'event::discovery::{scene.region.name}',
                        [f'{scene.region.name}的废墟深处，有什么在发光。',
                         '石壁上有一行字——不是汉字，是某种更古老的文字。它不是在说话，是在记忆。',
                         '这条路之前没有——今天是第一次出现。']))
                elif hint == 'peaceful_interlude':
                    L.append('')
                    L.append(f'{scene.region.name}的这一刻，安静得不像真的。')

        # === 3. 角色行动 ===
        if char_action == 'move' and scene.neighbor_regions:
            # 移动到邻接区域
            target = self._rng.choice(scene.neighbor_regions)
            self._chars.move_to(scene.pov_character, target)
            L.append('')
            active_map = self._wm.active_map()
            path = active_map.path_to(scene.region.name, target)
            dist = path.distance if path else 1
            L.append(f'穿过{"崎岖的山路" if dist > 1 else "一条小径"}，前方是{target}。')
            # 更新区域访问计数
            scene.region.last_visited = scene.time_step

        elif char_action in ('fight', 'react', 'flee'):
            action_char = ctx.get_character(scene.pov_character) or ctx.get_character('林朔')
            if action_char:
                action_text = self._gen._voice.render_character_action(
                    action_char,
                    'react' if char_action == 'react' else 'collapse',
                    ctx)
                if action_text:
                    L.extend(['', action_text])

        elif char_action == 'investigate':
            reveal_lines = self._gen._voice.render_truth_reveal(ctx, min(3, int(scene.arc_progress * 6) + 1))
            if reveal_lines:
                L.extend([''] + reveal_lines)

        else:
            # explore / observe / rest / decide → 观察和内心
            action_char = ctx.get_character(scene.pov_character) or ctx.get_character('林朔')
            if action_char:
                action_text = self._gen._voice.render_character_action(
                    action_char, 'observe', ctx)
                if action_text:
                    L.extend(['', action_text])

        # === 4. 对话（多角色在场时概率触发）===
        if len(scene.characters_here) >= 2 and self._rng.random() < 0.3:
            dialogue = self._gen._dlg.generate(
                'generic', scene.characters_here[:2], {})
            if dialogue:
                L.extend(['', dialogue])

        # === 5. 章末钩子 ===
        hook = self._gen._voice.render_hook(ctx)
        if hook:
            L.extend(['', hook])

        # === 后处理 ===
        L = self._gen._quality.process_light(L, scene.region.category)

        # 伏笔闭环
        self._gen._wire_foreshadowing(ctx, [], L, events_log, self._passage_no)

        # 长句去重
        text = '\n'.join(L)

        # 字数逼近时截断
        if remaining < 800:
            lines = text.split('\n')
            truncated_lines = []
            chars = 0
            limit = max(200, int(remaining * 1.2))
            for line in lines:
                line_chars = len(line)
                if chars + line_chars > limit:
                    break
                truncated_lines.append(line)
                chars += line_chars
            text = '\n'.join(truncated_lines)
        for sn in self._long_sentences(text):
            self._long_counter[sn] = self._long_counter.get(sn, 0) + 1

        # 持久化
        self._ps.state['current_chapter'] = self._passage_no
        try:
            self._ps.add_chapter_summary(
                self._passage_no,
                f'第{self._passage_no}段 @ {scene.world_name}/{scene.region.name}',
                events_log, [])
        except Exception:
            pass

        return text

    @staticmethod
    def _long_sentences(text: str) -> list:
        import re
        out = []
        for s in re.split(r'[。！？!?\n]', text):
            sn = re.sub(r'\s+', '', s)
            if len(sn) >= 15 and re.search(r'[\u4e00-\u9fffA-Za-z0-9]', sn):
                out.append(sn)
        return out

    # ------------------------------------------------------------------
    # 输出
    # ------------------------------------------------------------------
    def _finalize(self, buffer: list) -> str:
        full = '\n\n'.join(buffer)
        ts = time.strftime('%Y%m%d_%H%M%S')
        out_path = os.path.join(self._output_dir,
                                f'万界归墟_场景驱动_{self._total_chars}字_{ts}.txt')
        os.makedirs(self._output_dir, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('《万界归墟》· 场景驱动生成（事件驱动 / 空间连续 / 角色自主）\n')
            f.write(f'实得字数：{self._total_chars:,}　段落数：{len(buffer)}\n\n')
            f.write(full)
        self._ps.state['current_chars'] = self._total_chars
        self._ps.state['current_passage'] = self._passage_no  # 累计段数（非 len(buffer)，防止多次 resume 累积腐蚀）
        self._ps.state['last_output_text'] = full              # 保存全文供断点续写恢复
        self._ps.save()
        return out_path
