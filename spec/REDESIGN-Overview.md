# 《万界归墟》生成器重构总览：从「罐头开放世界」到涌现式字数目标生成

> 本文档是重构的总纲。配套文档：
> - `Architecture-Modules.md`：模块划分与接口契约
> - `WordCount-Driver.md`：字数目标驱动循环设计
> - `Config-Schema.md`：配置项 schema

---

## 1. 我们当前的「罐头」问题（精准定位）

调研育碧「罐头开放世界」批评后，回头看本生成器，问题高度同源：

| 育碧被骂的点 | 本生成器的对应实现 | 代码位置 |
|---|---|---|
| 公式化节拍 / 脚本化推进 | `generate_outline` 把 Save the Cat 15 拍**硬编码**到每一章号（如 `('midpoint', 49, 53)`） | `integrated_chapter_generator.py:84-120` |
| 按模板填算子（清单式） | `orchestrate` 用 `_QUOTA[beat]` 给每章定死 `(scene, action, battle)` 数量 | `beat_orchestrator.py:88-103` |
| 主线被结构稀释 | `volume` + `BEAT_TO_WORLD` 把整本书切成固定卷/世界骨架 | `beat_constants.py` |
| 重复填充 | 同一 beat 的章节复用同一套定场语/对话模板 | `beat_orchestrator.py` 各 `_beat_*` |

一句话：**大纲（15 拍）强驱动一切**，生成器只是在「执行剧本」，不是「在生长世界」。这正是玩家腻味罐头游戏的根因在文学生成上的翻版。

---

## 2. 调研给出的「抗罐头」解法（我们采用的原则）

来自联网调研（育碧批评 + 成功案例 + 涌现式叙事理论）：

1. **系统胜过脚本（涌现式叙事）**
   - 《七国》「蝴蝶效应事件引擎」：2000+ 叙事碎片织成动态网络，玩家行为触发十年后才显现的事件。
   - 《上古卷轴》Radiant 任务系统、《求生之路》AI Director：按玩家状态动态调节强度/类型。
   - 原则：故事从「系统交互」中**涌现**，而非预设全部内容。
2. **puzzle-piece 世界**：手工模块 + 程序化组装，而非全程序化或全手写。
3. **密度 > 规模**：一条设计精良的走廊胜过空旷的大陆；核心循环 explore→challenge→reward 要有意义。
4. **软骨架只做概率微调，不做硬指派**：避免「空旷无物」，但也不锁死脚本。
5. **《波斯王子：失落的王冠》反例**：聚焦、致密、手感独特，而非清单打卡。

---

## 3. 我们**保留**的（已经是真抗罐头机制，绝不丢）

这些在前面几轮工作中建成，正是「无放回发牌 + 状态感知」的核心，必须保留：

- **VoiceEngine 洗牌发牌（`_deal`）**：每副牌堆无放回、发完重洗、跨章持久 —— 从根上压住逐字复读（已有 `test_deal.py` 守门）。
- **伏笔闭环**（`_wire_foreshadowing`）：种植节拍埋设、到期回收呼应句写进正文。
- **章间节奏调制**（`_inject_quota` 的 `prev_beat_tension` 逻辑）：连续高张力→给一拍缓冲。
- **性格尾句**（`personality_tag` 经 `_sync_characters` 透传 + 轮换 ACTION）。
- **镜头落点**（`scene_spot` / `spot_frames`）：从世界级远景落到具体地点。
- **OpType 渲染管线**（`_execute_operation` 的 SCENE/TEXT/ACTION/EMOTION/DIALOGUE/PLAYER/REVEAL/BATTLE/HOOK/BREAK 分派）。

---

## 4. 我们**改变**的

| 旧 | 新 |
|---|---|
| `generate_outline(chapters)` 硬编码 15 拍到章号 | 取消。改为**软元弧**：仅按「已生成字数 / 目标字数」给出 `establish / escalate / resolve` 阶段信号，作为**概率微调**，不指派 beat |
| `volume` + `BEAT_TO_WORLD` 固定卷世界骨架 | `volume` 降级为**可选元数据标签**（仅用于输出分段/书名），不再驱动生成逻辑 |
| `orchestrate(ctx)` 读 `ctx.beat` → 固定 `_QUOTA[beat]` | `EmergentOrchestrator.plan(ctx, state)`：由发牌员 `Dealer` **无放回均匀发牌**世界/段落类型/算子类型（完全随机，取消状态加权） |
| `UnifiedNovelEngine.generate(chapters=N)` 章/卷循环 | `generate_by_words(target_chars=N)`：字数目标循环，emit `Passage` 直到达标 |

---

## 5. 一句话价值主张

> 从「按剧本演 80 章」变成「让一个会呼吸的世界长到 20 万字」——
> 大纲退居幕后，字数是目标，发牌员（无放回 bag）是发动机、也是方向盘。生成完全由发牌员随机发牌驱动。
