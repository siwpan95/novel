# 《万界归墟》小说生成器 — 架构文档 v2.0

## 基于双引擎融合：因果链流（大脑）+ ASP 模板流（声音）

---

## 一、项目概述

《万界归墟》小说生成器是一个**双引擎程序化中文长篇小说生成系统**，面向莲花式地图诸天无限流世界观。系统将两种截然不同的文本生成策略深度融合：

- **因果引擎（大脑）**：基于 Save the Cat! 15 节拍叙事结构，通过 `BeatOrchestrator` 将情节骨架分解为 `VoiceOperation` 序列，决定"说什么"——谁在什么世界、处于什么情绪、发生什么事件。
- **ASP 引擎（声音）**：继承自《宇宙巨校闪级生》的多层嵌套循环 + 16 个 JSON 词库随机替换，通过 `VoiceEngine` 将节拍操作渲染为具体文字，决定"怎么说"——用什么词库、什么模板、什么语气。

两个引擎通过 **`NarrativeContext`**（共享状态总线）实时同步，由 **`IntegratedChapterGenerator`** 统一调度执行，实现"因果一致、每次输出不同的"深度融合生成。系统纯 Python 标准库实现，零外部依赖，支持断点续写、Rubric 自动评分和质量流水线。

---

## 二、项目结构

```
novel_generator/
├── __init__.py                              # 包初始化
├── __main__.py                              # ★ 统一入口（CLI + 交互式菜单）
├── main.py                                  # 旧版入口（ASP 演示，向后兼容）
├── unified_engine.py                        # 双引擎统一编排器（UnifiedNovelEngine）
├── causal_main.py                           # 因果链独立入口（旧版）
├── fix_quotes.py                            # 引号修复工具
├── word_banks/                              # 30 个 JSON 词库，按 vocab/genre_terms/narrative/world/voice 5 类分子目录；详见 word_banks/README.md
│   ├── names.json                           # 姓氏（40）+ 名字用字（100）
│   ├── adjectives.json                      # 外貌/场景/品质/尺寸形容词
│   ├── body_parts.json                      # 24 个身体部位的描写短语
│   ├── equipment.json                       # 兵器/武功/魔法/法宝名称组件
│   ├── locations.json                       # 地形/地标/场景描写短语
│   ├── personality_tags.json                # 角色性格标签库
│   ├── senses/world_senses_ambient.json     # 世界环境五感（visual/auditory/olfactory/tactile/taste）
│   ├── senses/world_senses_battle.json      # 战场地形描写；二者合并为 world_senses（见 WordBank.load_world_senses）
│   ├── wanjie_context.json                 # 万界归墟世界观专属上下文
│   ├── beat_narratives.json                 # 节拍叙事硬编码文本（由 extract_beat_texts.py 提取）
│   ├── hook_templates.json                  # 章末钩子模板（悬念/爽点预告/关系三类型，来自网文写作研究）
│   ├── wuxia_terms.json                     # 武侠·苍云之殇专用术语
│   ├── post_apocalyptic_terms.json          # 末日废土专用术语
│   ├── cultivation_terms.json               # 东方修仙专用术语
│   ├── cyberpunk_terms.json                 # 赛博都市专用术语
│   ├── scifi_terms.json                     # 星际殖民专用术语
│   └── cthulhu_terms.json                   # 克苏鲁深渊专用术语
├── engine/
│   ├── __init__.py                          # 引擎包初始化
│   ├── word_bank.py                         # 词库加载器：加载/缓存/随机选取/种子控制
│   ├── template.py                          # 模板引擎：{{bank.key}} 占位符解析
│   ├── narrative_context.py                 # ★ 共享状态总线（NarrativeContext + CharacterSnapshot）
│   ├── voice_engine.py                      # ★ 上下文感知词库渲染引擎（VoiceEngine）
│   ├── beat_orchestrator.py                 # ★ 节拍→操作序列编排器（BeatOrchestrator + VoiceOperation）
│   ├── beat_constants.py                    # Save the Cat! 15 节拍常量 + 节拍→世界映射
│   ├── integrated_chapter_generator.py      # ★ 双引擎融合章节生成器（核心）
│   ├── causal_chapter.py                    # 因果链章节生成器（旧版，硬编码文本，v3.0 移除）
│   ├── causal_dialogue.py                   # 因果对话引擎：角色议程驱动对话
│   ├── plot_state.py                        # 跨章节情节状态管理器（角色/伏笔/千层饼）
│   ├── rubric_player.py                     # RubricEngine + PlayerArchetypeEngine + FamousSceneEngine
│   ├── text_quality.py                      # 文本质感引擎：句式节奏 + 去AI味 + 五感分配
│   ├── rashomon.py                          # 复眼叙事引擎 + 信息不对称矩阵
│   ├── expansion.py                         # 事件展开引擎 + 世界差异化词库注入
│   ├── rhythm_engine.py                     # 「三番四震」网文黄金节奏引擎
│   ├── fusion_generator.py                  # 跨界混搭生成器（12个世界的嫁接公式）
│   ├── interactive_nlp.py                   # 交互式大纲插桩 + NLP 一致性检查
│   ├── llm_rewrite.py                       # LLM 润色引擎 + Rubric 自动重写
│   └── generators/                          # ASP 引擎1 子模块（向后兼容）
│       ├── __init__.py                      # 生成器包初始化
│       ├── character.py                     # 角色生成器（姓名+外貌+装备+技能）
│       ├── battle.py                        # 场景+战斗生成器（招式随机组合）
│       ├── dialogue.py                      # 对话生成器（模板+填充）
│       ├── chapter.py                       # 章节+卷生成器（多层嵌套循环核心）
│       └── novel.py                         # 小说生成器（最外层循环+前言尾声）
├── tests/                                   # 测试（pytest）
│   ├── __init__.py
│   ├── conftest.py                          # 测试夹具
│   ├── test_word_bank.py                    # 词库加载与选取测试
│   ├── test_template.py                     # 模板引擎测试
│   └── test_plot_state.py                   # PlotState 持久化测试
└── output/                                  # 生成的小说输出目录
```

---

## 三、双引擎架构

### 3.1 总体架构图

```
                           ┌────────────────────────────┐
                           │     UnifiedNovelEngine      │
                           │       （统一编排器）          │
                           └────────────┬───────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
              ▼                         ▼                         ▼
    ┌─────────────────┐    ┌─────────────────────┐    ┌──────────────────────┐
    │   引擎1: ASP     │    │  引擎2: 因果链       │    │    质量保障管线        │
    │  （模板流/声音）   │    │  （节拍流/大脑）      │    │                      │
    ├─────────────────┤    ├─────────────────────┤    ├──────────────────────┤
    │ NovelGenerator  │    │ Save the Cat! 15节拍 │    │ RubricEngine (5维)   │
    │  └─VolumeGen    │    │  └─BeatOrchestrator  │    │ TextQualityPipeline  │
    │    └─ChapterGen │    │    └─VoiceOperation  │    │  ├─句式节奏           │
    │      ├─SceneGen │    │      ├─SCENE         │    │  ├─去AI味黑名单(32词) │
    │      ├─CharGen  │    │      ├─ACTION        │    │  └─五感分配           │
    │      ├─BattleGen│    │      ├─EMOTION       │    │ RashomonEngine       │
    │      └─DlgGen   │    │      ├─DIALOGUE      │    │  └─多视角折射         │
    │                 │    │      ├─REVEAL        │    │ ExpansionEngine      │
    │  多层嵌套循环    │    │      ├─PLAYER        │    │  └─句子类型展开       │
    │  词库随机替换    │    │      ├─BATTLE        │    │ RhythmEngine          │
    │  半随机命名      │    │      ├─HOOK          │    │  └─三番四震           │
    └────────┬────────┘    └──────────┬──────────┘    └──────────┬───────────┘
             │                        │                          │
             │           ┌────────────┴───────────┐              │
             │           │                        │              │
             └───────────┤  NarrativeContext      ├──────────────┘
                         │  （共享状态总线）        │
                         │                        │
                         │  · chapter / beat      │
                         │  · world_name / tone   │
                         │  · characters_present  │
                         │  · key_events          │
                         │  · truth_layer         │
                         └────────────┬───────────┘
                                      │
                                      ▼
                         ┌─────────────────────┐
                         │    VoiceEngine       │
                         │  （上下文感知渲染）    │
                         ├─────────────────────┤
                         │ render_scene()       │
                         │ render_action()      │
                         │ render_emotion()     │
                         │ render_dialogue()    │
                         │ render_reveal()      │
                         │ render_player_chaos()│
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ IntegratedChapter   │
                         │ Generator           │
                         │ （融合执行层）        │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   输出: .txt 章节    │
                         └─────────────────────┘
```

### 3.2 引擎1：ASP 模板流（声音）

```
最外层循环 (for 部 = 1 to N)
  ├─ 中层循环 (for 卷 = 1 to M)
  │   ├─ 生成主角 hero + 搭档 partner（跨章复用）
  │   └─ 内层循环 (for 章 = 1 to K)
  │       ├─ 生成场景描写（~500字）
  │       ├─ 输出 hero + partner 外貌（~3000字/人）
  │       └─ 最内层循环 (for 对手 = 1 to P)
  │           ├─ 生成对手外貌（~1500字/人）
  │           ├─ 对战循环 (for round = 1 to 3)
  │           │   └─ 随机招式名 + 填充打斗模板
  │           └─ 生成对话
  └─ 输出前言、尾声
```

核心机制：**框架模板 + 多层嵌套循环 + 16 个 JSON 词库随机替换**。通过 `{{bank.key}}` 占位符模板引擎，将词库内容填充到预设模板中。配合 24 身体部位独立随机选取，理论角色组合数远超万亿级。

### 3.3 引擎2：因果链流（大脑）

```
Save the Cat! 15 节拍 × n 章/节拍 × 每章 3-5 个子索引

opening → theme → inciting → debate → break_1 → b_story
  → fun_games → midpoint → bad_guys → all_lost
  → dark_night → break_2 → finale → final_image

每个节拍通过 BeatOrchestrator 分解为 VoiceOperation 序列：
  [VoiceOp(SCENE, world=归墟, tone=tense),
   VoiceOp(ACTION, character=林朔, emotion=警觉),
   VoiceOp(DIALOGUE, participants=[林朔,墟核]),
   VoiceOp(REVEAL, layer=2, info=归墟是星图观测站),
   ...]
```

核心机制：**节拍驱动 + 状态追踪 + 操作序列**。PlotState 追踪跨章节的因果链、角色状态、伏笔进度和千层饼揭秘层次。每次生成"因果一致、文字不同"。

### 3.4 融合层：NarrativeContext 共享总线

```
因果引擎写入:                 ASP 引擎读取:
  beat / chapter               tone_modifier → 选词策略
  world_name                    pace_hint → 句长控制
  emotional_start/end           description_density → 描写密度
  key_events                    dialogue_ratio → 对话占比
  characters_present            world_key() → 世界专属词库族
```

融合引擎执行流程：因果大纲 → BeatOrchestrator 编排 → VoiceEngine 渲染 → TextQualityPipeline 质检 → 输出。两个引擎通过 NarrativeContext 在每次文本生成时同步上下文，实现真正的"大脑+声音"深度融合。

---

## 四、核心组件说明

### 4.1 UnifiedNovelEngine（统一编排器）
`unified_engine.py` — 双引擎的顶层入口。负责初始化所有子组件（WordBank、PlotState、ASP 生成器、因果链生成器、融合生成器、质量管线），提供 `generate(mode, **kwargs)` 统一接口，根据 mode 参数派发到 `_gen_asp()`、`_gen_causal()` 或 `_gen_integrated()`。支持大纲预览（`preview_outline`）和诊断报告（`diagnostic_report`）。

### 4.2 IntegratedChapterGenerator（融合章节生成器）★
`engine/integrated_chapter_generator.py` — 双引擎融合的核心执行器。替代旧版硬编码 `CausalChapterGenerator`，实现真正的"一次生成，双引擎同时工作"。每章生成流程：`BeatOrchestrator.orchestrate(ctx)` → 获得 `VoiceOperation[]` → `VoiceEngine` 逐条渲染 → 组装段落 → `TextQualityPipeline` 质检 → 返回章节文本。内部整合了 RubricEngine、RashomonEngine、ExpansionEngine、RhythmEngine、FamousSceneEngine 等全部质量组件。

### 4.3 BeatOrchestrator（节拍编排器）
`engine/beat_orchestrator.py` — 将 Save the Cat! 因果节拍转换为 `VoiceOperation` 序列的编排层。定义 9 种操作类型（`OpType`）：SCENE（场景描写）、ACTION（角色动作）、EMOTION（情绪节拍）、DIALOGUE（对话）、REVEAL（信息揭示）、PLAYER（玩家行为）、BATTLE（战斗）、TEXT（直接文本）、HOOK（悬念钩子）。每个节拍通过 `orchestrate(ctx)` 方法，根据当前 NarrativeContext 生成约 6-15 个有序操作，VoiceEngine 按序执行。

### 4.4 VoiceEngine（上下文感知词库渲染）
`engine/voice_engine.py` — ASP 词库的上下文感知渲染层。提供 6 大渲染方法：`render_opening_scene()`（世界初现场景）、`render_action()`（角色动作+情绪+性格标签）、`render_emotion()`（用身体反应而非直接命名表达情绪）、`render_dialogue()`（调用 CausalDialogueEngine 生成话轮）、`render_reveal()`（千层饼信息分层揭示）、`render_player_chaos()`（玩家沙雕行为生成）。内置防重复机制（最近 20 条去重），每个世界有独立渲染变体（如归墟世界的 4 个开场变体）。

### 4.5 NarrativeContext（共享状态总线）★
`engine/narrative_context.py` — 双引擎融合的核心数据总线。`@dataclass` 包含：因果侧（chapter、beat、sub_index、world_name、emotional_start/end、tension_level、key_events）、角色快照（`CharacterSnapshot`：姓名、情绪、目标、位置、腐败度、声纹特征）、ASP 侧（tone_modifier、pace_hint、description_density、dialogue_ratio）。提供 `_infer_tone_from_beat()` 自动推断叙述基调、`world_key()` 返回当前世界的词库键名。

### 4.6 PlotState（情节状态管理器）
`engine/plot_state.py` — 跨章节因果一致性保障。以 JSON 文件持久化（`spec/tracking/plot_state.json`），追踪维度：角色状态（位置、情绪、目标、关系、隐藏真相层数）、情节开关（是否触发过某事件）、伏笔清单（已埋+计划回收章）、已解锁花瓣世界、已回收源界碎片数、千层饼揭秘进度（1-6 层）、玩家关系状态。支持断点续写（`--resume` 参数）。

### 4.7 RubricEngine + TextQualityPipeline（质量保障）
`engine/rubric_player.py` + `engine/text_quality.py` — 双维度质量保障体系。
- **RubricEngine**：5 维自动评分（因果一致性 25% / 节奏感 20% / 对话自然度 20% / 情感曲线 20% / 去AI味 15%），低于阈值（2.5/5）触发局部重写。
- **TextQualityPipeline**：句式节奏引擎（短/中/长句按节拍权重分配 + 单字独段）、去 AI 味黑名单（32 词，分 3 级严重度扣分）、五感描写分配（视/听/触/嗅/味按比例触发）。
- 附带 `PlayerArchetypeEngine`（5 种玩家行为原型）和 `FamousSceneEngine`（名场面自动生成）。

### 4.8 WordBank（词库管理器）
`engine/word_bank.py` — 词库加载、缓存、随机选取的统一入口。支持：`load(bank_name)` 加载 JSON 词库（自动缓存）、`pick(bank, key)` 随机选取一项、`pick_n(bank, key, n)` 随机选取多项、`pick_without(bank, key, exclude)` 排除选取、半随机名字生成（姓氏池 + 名字字池有序组合）。所有随机操作受种子控制，保证可复现。

---

## 五、数据流

```
用户参数 (--mode words, --preset, --seed, --resume)
        │
        ▼
  UnifiedNovelEngine.generate(mode='words', preset='book')
        │
        ├─ 初始化 WordBank(seed) + PlotState(resume?)
        │
        ▼
  PlotState 构建大纲 (Save the Cat! 15 节拍 × 章数分配)
        │
        ├─ 每章创建 NarrativeContext（当前节拍/世界/情绪/角色）
        │
        ▼
  IntegratedChapterGenerator.generate_chapter(ch, outline_entry)
        │
        ├─ BeatOrchestrator.orchestrate(ctx) → VoiceOperation 序列
        │       │
        │       └─ 根据节拍类型 dispatching 到对应编排方法
        │          (beat_opening / beat_inciting / beat_midpoint / ...)
        │
        ├─ VoiceEngine 逐条执行 VoiceOperation
        │       │
        │       ├─ render_opening_scene()   → 场景段落
        │       ├─ render_action()          → 角色动作
        │       ├─ render_emotion()         → 情绪身体反应
        │       ├─ render_dialogue()        → CausalDialogueEngine 话轮
        │       ├─ render_reveal()          → 千层饼信息揭示
        │       └─ render_player_chaos()    → 玩家沙雕行为
        │
        ├─ RashomonEngine    → 关键节拍多视角折射
        ├─ ExpansionEngine   → 弱势节拍人物内心展开
        ├─ RhythmEngine      → 「三番四震」节奏注入
        ├─ FusionGenerator   → 跨界混搭元素注入
        │
        ▼
  TextQualityPipeline 质检
        │
        ├─ 句式节奏检查（短/中/长句分布）
        ├─ 去AI味检测（32词黑名单扫描）
        └─ 五感描写覆盖验证
        │
        ▼
  RubricEngine 评分（可选 --no-rubric 跳过）
        │
        ├─ score < 2.5 → 触发局部重写
        └─ score >= 2.5 → 通过
        │
        ▼
  写入 output/novel_YYYYMMDD_HHMMSS.txt
  保存 plot_state.json（支持断点续写）
```

---

## 六、词库系统

| 词库文件 | 条目数（约） | 用途 |
|---------|-----------|------|
| `names.json` | 140 | 姓氏池（40）+ 名字用字池（100），有序组合产生 39.6 万角色名 |
| `adjectives.json` | 70+ | 外貌/场景/品质/尺寸形容词，24 部位独立随机 → 70^24 级组合 |
| `body_parts.json` | 24 | 24 个身体部位的描写短语模板（头/眼/臂/腿…） |
| `equipment.json` | 76+ | 兵器/武功/魔法/法宝名称组件（前缀+类型+后缀） |
| `locations.json` | — | 地形/地标/场景描写短语 |
| `personality_tags.json` | — | 角色性格标签库（决定 VoiceEngine 渲染时的语气锚点） |
| `world_senses`（合并） | — | 世界五感描写池（视觉/听觉/触觉/嗅觉/味觉，跨世界通用）；由 `world/senses/` 下两份文件经 `WordBank.load_world_senses()` 合并 |
| `wanjie_context.json` | — | 万界归墟世界观专属上下文（归墟/墟核/锚定者等概念） |
| `wuxia_terms.json` | — | 武侠·苍云之殇专用术语（内力/招式/门派体系） |
| `post_apocalyptic_terms.json` | — | 末日废土专用术语（辐射/避难所/变异生物） |
| `cultivation_terms.json` | — | 东方修仙专用术语（灵气/金丹/渡劫） |
| `cyberpunk_terms.json` | — | 赛博都市专用术语（义体/黑客/巨型企业） |
| `scifi_terms.json` | — | 星际殖民专用术语（跃迁/星舰/基因改造） |
| `cthulhu_terms.json` | — | 克苏鲁深渊专用术语（古神/低语/不可名状） |
| `hook_templates.json` | 30 | 章末钩子模板（悬念钩/横向爽点钩/人物关系钩，研究驱动，提升追读率） |

> 世界专属词库（wuxia / post_apocalyptic / cultivation / cyberpunk / scifi / cthulhu）由 `NarrativeContext.world_key()` 根据当前世界自动选择加载。

---

## 七、使用方式

### 7.1 CLI 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--mode` | str | words | 引擎模式：`words` / `asp` / `causal` |
| `--preset` | str | tiny | 字数规模（words 模式）：tiny=2万 / small=5万 / book=20万 |
| `--target-chars` | int | (无) | 自定义目标字数（words 模式，覆盖 --preset） |
| `-v, --volumes` | int | 3 | 部数（asp 模式） |
| `-c, --chapters-per-volume` | int | 7 | 每部章数（asp 模式） |
| `-o, --opponents` | int | 4 | 每章对手数（asp 模式） |
| `-s, --seed` | int | 42 | 随机种子（可复现） |
| `--output` | str | output/ | 输出目录 |
| `--resume` | flag | false | 从 plot_state.json 断点续写（words 模式） |
| `--diagnose` | flag | false | 引擎诊断报告 |
| `--no-rubric` | flag | false | 跳过 Rubric 评分（causal 模式加速） |

### 7.2 生成模式

**（1）字数目标生成（words，★推荐默认）**
```bash
python main.py --preset book
# 或：python -m novel_generator --mode words --preset book
# 以字数为目标、状态驱动的涌现式生成；取消章/卷/大纲，弱化罐头感
# 输出有因果一致性且每次文字不同的长篇小说
```

**（2）因果链流模式（causal，旧版兼容）**
```bash
python -m novel_generator --mode causal --chapters 80
# 使用旧版 CausalChapterGenerator（硬编码文本，每次输出相同）
# ⚠️ 已标记 DEPRECATED，v3.0 将移除，推荐使用 words
```

**（3）ASP 模板流模式（asp，海量批量）**
```bash
python -m novel_generator --mode asp -v 3 -c 7 -o 4
# 纯多层嵌套循环 + 词库随机替换
# 适用场景：海量文本批量生成、词库效果演示
```

**其他快捷操作：**
```bash
python main.py --diagnose                       # 引擎诊断报告（或 -m novel_generator --diagnose）
python main.py --resume                         # 断点续写
python -m novel_generator                       # 交互式菜单（最友好）
```

### 7.3 Python API

```python
from novel_generator.unified_engine import UnifiedNovelEngine

engine = UnifiedNovelEngine(seed=42)

# 字数目标生成（★推荐）
engine.generate(mode='words', preset='small')

# 因果链（旧版）
engine.generate(mode='causal', chapters=80)

# ASP 模板
engine.generate(mode='asp', volumes=3, chapters_per_volume=7, opponents_per_chapter=4)

# 大纲预览
print(engine.preview_outline(80))

# 诊断
print(engine.diagnostic_report())
```

---

## 八、扩展方向

| 方向 | 描述 | 状态 |
|------|------|------|
| 词库扩充 | 从网文语料库自动提取形容词、招式名、世界设定等 | ✅ 已实现（手动扩充：6 个世界氛围词库 + 章末钩子模板，均接入渲染管线） |
| LLM 润色后处理 | 用大模型对生成文本做"润色去机器感"（`llm_rewrite.py` 已预置提示词框架） | ⚠️ 框架就绪，API 未接入 |
| 交互式大纲分支 | 在关键转折点（中点/暗夜/转折2）暂停让用户选分支方向（`interactive_nlp.py`） | ⚠️ 框架就绪 |
| 多卷展开 | 第二卷（觉醒界）+ 第三卷（神陨界）完整实现（`beat_constants.py` 已预置卷 2/3 节拍映射） | ⚠️ 映射就绪，内容待生成 |
| 模板多样化 | 增加更多打斗模板、对话模板、场景模板变体 | ✅ 已实现（VoiceEngine 多世界变体） |
| 句式节奏优化 | 模仿真实写作的短-中-长句交替节奏 | ✅ 已实现（RhythmEngine 三番四震） |
| 多视角叙事 | 关键转折章自动生成林朔/唐川/白夜/叶琳多视角 mini 节 | ✅ 已实现（RashomonEngine） |
| 世界差异化词库 | 为每个花瓣世界预置专属术语和嫁接公式 | ✅ 已实现（6 个世界词库 + FusionGenerator） |
| 去 AI 味检测 | 自动扫描并扣分 32 个 AI 高频词 | ✅ 已实现（TextQualityPipeline） |
| 断点续写 | 基于 plot_state.json 恢复中断的生成进度 | ✅ 已实现（--resume） |

---

> **版本记录**：v2.0 — 完整重写，覆盖双引擎融合架构（UnifiedNovelEngine / IntegratedChapterGenerator / BeatOrchestrator / VoiceEngine / NarrativeContext / PlotState / RubricEngine / TextQualityPipeline / WordBank / 16 词库 + 质量管线体系）。
