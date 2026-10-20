"""EmergentOrchestrator —— 发牌员驱动的涌现式编排器（替代 BeatOrchestrator 在字数路径的角色）。

设计原则（呼应 REDESIGN 重构 + 育碧「抗罐头」调研 + 7-bag/TGM 联网调研）：
1. 完全由发牌员随机发牌：世界 / 段落类型 / 算子类型一律经 Dealer 无放回均匀发牌，
   取消状态加权采样（张力 / 待回收伏笔 / 角色弧进度不再影响「发什么」，只参与
   算子细节参数的填充，如 REVEAL 的层数、ACTION 的角色）。
2. 抗清单式重复：无放回 bag 天然限制「旱涝」；跨包接缝防涝消除紧邻重复。
3. 世界选择也由 Dealer 发牌，保证与落点词库（scene_locations）对齐。
4. 确定性：同 seed 同输出；零依赖。

原 BeatOrchestrator._QUOTA[beat] 与 _weights/_sample 已全部移除，不再有状态加权。
"""
import random

from .beat_orchestrator import OpType, VoiceOperation
from .narrative_state import NarrativeState, PassageSpec, PASSAGE_TYPES
from .dealer import Dealer

# 均匀发牌的算子类型池（hook 由导演在段落收尾单独发牌，不在此列）
OP_TYPE_POOL = ['scene', 'action', 'battle', 'dialogue', 'reveal']

# ACTION 算子的动作轮换（跨段落共享下标，避免同段落内动作雷同）
ACTION_CYCLE = ['observe', 'arrive', 'react', 'decide', 'stand_up', 'collapse']


class EmergentOrchestrator:
    def __init__(self, voice, config: dict, rng: random.Random = None):
        self._voice = voice
        self._config = config
        if rng is not None:
            self._rng = rng
        elif 'rng_seed' in config:
            self._rng = random.Random(config['rng_seed'])
        else:
            # 兜底：从 WordBank 借用共享 RNG，保持种子链路一致
            self._rng = voice._wb.get_rng()
        # 发牌员：编排层唯一随机源（世界 / 段落类型 / 算子类型）
        self._dealer = Dealer(seed=config.get('rng_seed', 42))
        self._action_idx = 0

    # ------------------------------------------------------------------
    # 世界选择（发牌员无放回发牌；无 beat→world 映射、无卷）
    # ------------------------------------------------------------------
    def _pick_world(self, ctx) -> str:
        pool = self._world_pool()
        if not pool:
            return '归墟'
        return self._dealer.deal('world', pool)

    def _world_pool(self) -> list:
        try:
            data = self._voice._wb.load('scene_locations')
            keys = list(data.keys())
            if keys:
                return keys
        except Exception:
            pass
        return ['归墟', '武侠·苍云之殇', '末日废土', '东方修仙',
                '星际殖民', '赛博都市', '克苏鲁深渊', '造物主遗迹', '诸神黄昏']

    # ------------------------------------------------------------------
    # 段落类型：发牌员均匀发牌（替代原 _weights/_sample 加权采样）
    # ------------------------------------------------------------------
    def _deal_passage_type(self) -> str:
        return self._dealer.deal('passage_type', list(PASSAGE_TYPES))

    # ------------------------------------------------------------------
    # 算子构建：发牌员均匀发牌（替代原固定 scene/action 比例）
    # ------------------------------------------------------------------
    def _action_char(self, ctx, chars_present: list) -> str:
        if not chars_present:
            return '林朔'
        name = chars_present[self._action_idx % len(chars_present)]
        self._action_idx += 1
        return name

    def _dialogue_participants(self, chars_present: list) -> list:
        present = [n for n in chars_present if n != '墟核']
        if len(present) >= 2:
            return present[:2]
        return ['林朔', '墟核']

    def _make_op(self, op_type: str, ctx, state: NarrativeState) -> VoiceOperation:
        """按发到的算子类型构造 VoiceOperation；状态只用于填充细节参数，不决定发不发。"""
        if op_type == 'scene':
            return VoiceOperation(OpType.SCENE)
        if op_type == 'action':
            char = self._action_char(ctx, state.chars_present)
            action = ACTION_CYCLE[self._action_idx % len(ACTION_CYCLE)]
            return VoiceOperation(OpType.ACTION, char=char, action=action)
        if op_type == 'battle':
            return VoiceOperation(OpType.BATTLE, intensity='mid')
        if op_type == 'dialogue':
            return VoiceOperation(
                OpType.DIALOGUE,
                scene_type='generic',
                participants=self._dialogue_participants(state.chars_present),
            )
        if op_type == 'reveal':
            layer = max(1, int(state.arc_progress * 6) + 1)
            return VoiceOperation(OpType.REVEAL, layer=layer)
        return VoiceOperation(OpType.SCENE)

    def _build_ops(self, ctx, state: NarrativeState, extra: bool) -> list:
        cfg = self._config
        # 段落目标字数 → 估算算子数
        lo = cfg['min_passage_chars']
        hi = cfg['max_passage_chars']
        size = self._rng.randint(lo, hi) * (2 if extra else 1)
        avg_op = cfg.get('avg_op_chars', 110)
        n_ops = max(4, min(14, round(size / avg_op)))

        # 均匀无放回发牌：各算子类型在每包内各出现一次，再发下一包
        types = self._dealer.deal('op_type', OP_TYPE_POOL, take=n_ops)
        return [self._make_op(t, ctx, state) for t in types]

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def plan(self, ctx, state: NarrativeState, extra: bool = False) -> PassageSpec:
        passage_type = self._deal_passage_type()
        ops = self._build_ops(ctx, state, extra)
        return PassageSpec(
            passage_type=passage_type,
            ops=ops,
            weight_trace={'passage_type': passage_type, 'mode': 'uniform_deal'},
        )
