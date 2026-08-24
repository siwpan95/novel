# 模块化架构与接口契约

> 配套：`REDESIGN-Overview.md`（总览）、`WordCount-Driver.md`（驱动循环）、`Config-Schema.md`（配置）。

## 1. 模块划分

```
┌─────────────────────────────────────────────────────────────┐
│  WordCountDirector  （新增·主编排循环）                       │
│  - 以 target_chars 为目标，循环 emit Passage 直到达标          │
│  - 拥有 resume / 进度日志 / 输出分段                          │
└───────────────┬─────────────────────────────────────────────┘
                │ 每轮：read state → orchestrator.plan → renderer.render
                ▼
┌──────────────────────────┐   ┌──────────────────────────────┐
│  NarrativeState           │   │  EmergentOrchestrator        │
│  （新增·轻量状态快照）      │   │  （新增·替代 BeatOrchestrator │
│  - tension                │   │   在字数路径的角色）           │
│  - pending_foreshadowing  │   │  - plan(ctx, state)           │
│  - arc_progress           │   │    → PassageSpec             │
│  - recent_passage_types   │   │  - 软元弧概率微调            │
│  - phase                  │   │  - 状态驱动采样              │
│  - chars_present          │   └──────────────┬───────────────┘
└───────────────┬──────────┘                  │
                │ 复用数据                    ▼
                │   ┌──────────────────────────────────────────┐
                │   │  PassageRenderer  （复用现有渲染管线）     │
                │   │  = _execute_operation 分派 + VoiceEngine  │
                │   │  输入 PassageSpec → 文本行列表            │
                │   └──────────────────────────────────────────┘
                │
   ┌────────────┴─────────────────────────────────────────┐
   │  保留不动的底层（抗罐头发动机）                          │
   │  VoiceEngine（_deal 无放回发牌）                        │
   │  PlotState（伏笔 / 千层饼 / 节奏 / 角色）                │
   │  foreshadowing / rhythm / persona / scene_spot        │
   └──────────────────────────────────────────────────────┘
```

## 2. 核心数据结构

```python
# 一段叙事单元（原「章」退化为可变的 Passage）
@dataclass
class PassageSpec:
    passage_type: str          # scene / action / dialogue / battle / reveal / hook / mixed
    ops: list[VoiceOperation]  # 由 EmergentOrchestrator 采样得到
    weight_trace: dict         # 记录本次采样的概率依据（可观测、可调试）

# 轻量状态快照（从 PlotState + NarrativeContext 派生，不新增持久依赖）
@dataclass
class NarrativeState:
    total_chars: int
    target_chars: int
    tension: int               # 来自 ctx.tension_level
    pending_foreshadowing: int # plot_state 中 status=='active' 且 recovery 到期的数量
    arc_progress: float        # 角色弧推进度 0..1（示例：已揭示真相层数 / 总层数）
    recent_passage_types: list # 最近 N 段类型，用于去重惩罚（抗清单式重复）
    chars_present: list        # 在场具名角色
    phase: str                 # establish / escalate / resolve（软元弧，仅概率微调）
```

## 3. 模块接口契约（伪代码）

```python
class WordCountDirector:
    def __init__(self, voice, plot_state, orchestrator, renderer, config): ...
    def generate(self, target_chars: int, *, seed=None, resume=False) -> str:
        """循环 emit Passage 直到累计字数 >= target_chars。
        返回完整正文（无章/卷标题，仅自然分段）。"""

class EmergentOrchestrator:
    def plan(self, ctx: NarrativeContext, state: NarrativeState) -> PassageSpec:
        """弱化大纲：不再读 ctx.beat 硬指派。
        1. 计算阶段权重（phase 仅微调）；
        2. 叠加状态权重（tension→action/battle，pending→reveal/hook，arc→dialogue）；
        3. 对近期重复类型做惩罚（抗 checklist）；
        4. 采样 passage_type 与内部 op 数量（base_quota + 状态增量）。"""

class PassageRenderer:
    def render(self, spec: PassageSpec, ctx: NarrativeContext) -> list[str]:
        """复用现有 _execute_operation 分派 + VoiceEngine。
        每个 op 仍走无放回发牌。"""
```

## 4. 迁移与兼容性

- 旧路径 `UnifiedNovelEngine.generate(mode='integrated', chapters=N)` / `generate_outline` 的处置，由 `REDESIGN` 任务确认后决定（移除 / 保留为 deprecated）。
- 所有底层引擎（VoiceEngine / PlotState / 伏笔 / 节奏 / 性格 / 镜头）**接口不变**，仅调用方从「按章」改为「按 Passage」。
- 测试：`test_deal.py` 继续守门；新增 `test_wordcount_director.py`（字数达标 + 状态驱动可观测）。
