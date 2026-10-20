"""叙事状态快照 + 段落规格 —— 字数目标生成模式的核心数据结构。

本模块刻意不依赖任何引擎实现，只通过参数接收 plot_state，
便于单测与在 WordCountDirector / EmergentOrchestrator 之间传递。

设计要点（呼应 REDESIGN 重构）：
- 去掉「卷 / 阶段(phase) / 固定 beat」：NarrativeState 不含这些字段。
- 生成完全由「叙事状态」驱动：张力、待回收伏笔、角色弧进度、近期段落多样性。
- 这是「弱化大纲 / 纯状态驱动（无软元弧）」在数据结构层的落地。
"""
from dataclasses import dataclass, field
from typing import Dict, List


PASSAGE_TYPES = ['scene', 'action', 'dialogue', 'battle', 'reveal', 'mixed']


@dataclass
class PassageSpec:
    """一段叙事单元的规格：类型 + 采样得到的算子序列 + 可观测的权重轨迹。"""
    passage_type: str
    ops: list
    weight_trace: Dict = field(default_factory=dict)


@dataclass
class NarrativeState:
    """轻量状态快照，从 PlotState + 当前累计字数派生。"""
    total_chars: int = 0
    target_chars: int = 0
    tension: int = 3                 # 0..10，由导演做随机游走维护
    pending_foreshadowing: int = 0   # 已到期、待回收的伏笔数
    arc_progress: float = 0.0        # 角色弧 / 真相揭示进度 0..1
    recent_passage_types: List[str] = field(default_factory=list)
    chars_present: List[str] = field(default_factory=list)

    @property
    def progress(self) -> float:
        return (self.total_chars / self.target_chars) if self.target_chars else 0.0


def derive_state(total_chars: int, target_chars: int, tension: int,
                 plot_state, recent_types: List[str],
                 chapter_num: int, config: dict) -> NarrativeState:
    """从持久化状态派生 NarrativeState。

    - pending_foreshadowing: 已到期待回收的伏笔数（驱动 REVEAL/HOOK 权重）
    - arc_progress: 真相层揭示进度（驱动 DIALOGUE 权重）
    - chars_present: 在场具名角色（排除系统/群体），用于对话参与者轮换
    """
    # 待回收伏笔（plot_state 的伏笔 API，状态驱动而非 beat 驱动）
    pending = 0
    try:
        due = plot_state.get_pending_foreshadowing(chapter_num)
        pending = len(due) if due else 0
    except Exception:
        pending = 0

    # 角色弧 / 真相进度
    arc_progress = 0.0
    try:
        truth = plot_state.state.get('truth', {}) or {}
        cur = truth.get('current_layer', 0) or 0
        total_layers = truth.get('total_layers', 6) or 6
        arc_progress = min(1.0, cur / total_layers)
    except Exception:
        arc_progress = 0.0

    # 在场具名角色（排除系统墟核 / 群体）
    chars_present = [
        n for n in (plot_state.state.get('characters', {}) or {}).keys()
        if n not in ('墟核', '玩家群体')
    ]

    return NarrativeState(
        total_chars=total_chars,
        target_chars=target_chars,
        tension=tension,
        pending_foreshadowing=pending,
        arc_progress=arc_progress,
        recent_passage_types=list(recent_types),
        chars_present=chars_present,
    )
