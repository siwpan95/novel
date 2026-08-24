# 《万界归墟》多卷展开方案

## 一、差距分析：Novel Bible vs 当前实现

### 第一卷（已完成 ✓）
| 已实现 | 说明 |
|--------|------|
| 12个Save the Cat节拍编排 | BeatOrchestrator._beat_opening ~ _beat_break_2 |
| 2个世界模板 | 归墟、武侠·苍云之殇（VoiceEngine + world_senses.json） |
| 千层饼1-2层 | 自动触发矩阵已就绪 |
| 角色初始状态 | 林朔/唐川/叶琳/白夜/墟核 |
| 玩家沙雕生成 | VoiceEngine.render_player_chaos |

### 第二卷（待构建 ✗）
| 需要 | Novel Bible规划 | 当前状态 |
|------|----------------|---------|
| 4个新世界 | 东方修仙、星际殖民、剑与魔法、赛博都市 | world_senses.json已有五感数据，VoiceEngine缺世界模板 |
| 代理人战争节拍 | 多线冲突，遭遇不同类型代理人 | BeatOrchestrator零覆盖 |
| 唐川觉醒 | 发现"不是游戏"→崩溃→成为盟友 | 无独立节拍编排 |
| 千层饼3-4层 | "万界是实验场"+"祂们是入侵者" | 触发矩阵已有条件，缺揭示文本 |
| 终局预演战 | 玩家+原住民 vs 代理人军队 | 无可编排 |

### 第三卷（待构建 ✗）
| 需要 | Novel Bible规划 | 当前状态 |
|------|----------------|---------|
| 4个新世界 | 诸神黄昏、克苏鲁深渊、高等文明实验场、造物主遗迹 | world_senses.json已有五感，缺模板 |
| 循环真相 | 第47次循环+前锚定者玩家被收编 | 缺揭示文本 |
| 林朔身份 | 源之碎片/祂们叛逃/变体锚定者 | 缺揭示文本 |
| 终极选择+终局大战 | 三段式结局+开放尾声 | 缺编排 |

---

## 二、实施方案

### 阶段A：BeatOrchestrator多卷化（2-3小时）

当前架构的BeatOrchestrator是节拍→操作序列的映射，天然支持多卷扩展。
方案：为每个节拍方法增加`volume`参数，dispatch到不同内容。

```python
class BeatOrchestrator:
    def orchestrate(self, ctx: NarrativeContext) -> list:
        beat = ctx.beat
        volume = ctx.volume  # 新增：卷号 1/2/3
        orchestrator = getattr(self, f'_beat_{beat}_{volume}', None)
        if not orchestrator:
            orchestrator = getattr(self, f'_beat_{beat}', None)  # fallback
        ...
```

需要新增的方法：
- `_beat_opening_2` — 觉醒界初探（修仙世界第一印象）
- `_beat_opening_3` — 神陨界第一印象
- `_beat_inciting_2` — 代理人遭遇升级
- `_beat_inciting_3` — 终局危机爆发
- `_beat_midpoint_2` — 千层饼第3层+"第一次大规模战役"
- `_beat_midpoint_3` — 千层饼第5层+"林朔身份初现"
- `_beat_break_2_2` — 唐川觉醒
- `_beat_break_2_3` — 终极选择
- `_beat_b_story_2` — 新世界原住民羁绊
- `_beat_all_lost_3` — 终局的代价
- `_beat_bad_guys_2` — 代理人战争多线
- `_beat_bad_guys_3` — 前锚定者玩家叛变
- `_beat_epilogue_3` — 开放结局

### 阶段B：VoiceEngine世界模板（1-2小时）

已有world_senses.json覆盖全部12个世界。VoiceEngine需要：
- `_render_world_entry(world_name)` — 根据五感词库渲染每个世界的首次进入
- 修仙世界：灵气潮涌、天劫雷云、飞剑破空
- 星际世界：舷窗星海、异星地表、AI报告
- 赛博世界：霓虹雨夜、义体诊所、数据流
- 克苏鲁世界：不可名状、SAN值、深海低语

### 阶段C：千层饼3-6层揭示文本（0.5小时）

PlotState.TRUTH_TRIGGERS已有条件矩阵，只需补揭示文本：
```python
TRUTH_TRIGGERS = {
    3: {'narrative': '万界是源的"文明可能性实验场"...', 'new_info': '...'},
    4: {'narrative': '祂们是源沉睡后的入侵者...', 'new_info': '...'},
    5: {'narrative': '47次循环，林朔是第48个锚定者...', 'new_info': '...'},
    6: {'narrative': '林朔的真实身份——可能来自祂们阵营...', 'new_info': '...'},
}
```

### 阶段D：终局编排（1小时）

第三卷需要独特的叙事结构：
- 终局选择分叉点（交互式大纲）
- 多结局框架（维持/摧毁/重建）
- 尾声模板

---

## 三、生成器调用方式

```python
# 第二卷
engine = UnifiedNovelEngine(seed=42)
engine.generate(mode='integrated', volume=2, chapters=170, start_chapter=81)

# 第三卷
engine.generate(mode='integrated', volume=3, chapters=250, start_chapter=251)
```

## 四、优先级建议

| 优先级 | 项目 | 预估 | 效果 |
|:---:|---|:---:|---|
| **P0** | BeatOrchestrator多卷化 + 4个觉醒界世界模板 | 2h | 第二卷可生成 |
| **P1** | 千层饼3-6层文本 + 神陨界模板 | 1.5h | 第三卷可生成 |
| **P2** | 终局分支 + 多结局 | 1h | 完整500章 |
