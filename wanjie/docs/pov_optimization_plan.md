# POV（视点人物写作手法）优化方案

> 来源：百度百科《视点人物写作手法》+ 项目现状盘点 + 用户强调的 POV 内核。
> 性质：**规划文档**，未执行任何代码/JSON 改动。下一步由用户确认范围后再执行。

---

## 0. 用户强调的 POV 内核（对话原文提炼）

1. 允许作者**自由选择叙述角度**
2. 将**不同人物作为视点主体**
3. 以**事件为线索**，通过事件将主人公们的命运串联起来
4. 通过**精心编排时间线**，避免叙事混乱，使各视点人物的故事线保持**连贯推进**
5. **便于后期修改和情节调整**（对应"方便维护"）

这五点全部是**叙事架构层**诉求，而非文风修饰。

---

## 1. 现状盘点：引擎已实现 POV，但全部硬编码成"万界归墟"专属

| POV 机制 | 当前实现位置 | 是否数据驱动 |
|---|---|---|
| 事件为线索（事件驱动时间轴） | `engine/timeline.py` 事件触发机制；`default_timeline()` 硬编码具体事件（line ~161–172：`unlock_wuxia`/`unlock_wasteland`/`unlock_cultivation`…） | ❌ 事件写死 |
| 不同人物为视点主体 | `engine/storyline.py` `worlds_config` 的 `pov` 字面量（line 284–286：`林朔`/`叶琳`）、`pov_characters`（line 298/314/329/370） | ❌ 角色名写死 |
| 时间线编排 / 多视角汇聚（罗生门） | `storyline.py` `ConvergencePoint.pov_sequence`/`shared_event_description`（line 404–416、505–506）；`causal_chapter.py` 关键节拍调 `rashomon.generate`（line 102–107） | ❌ 序列写死 |
| 各视点故事线连贯 | `storyline.py` 多线 + 每线 `pov_characters` | ❌ 依赖写死角色 |
| 复眼叙事（同事件多视角） | `engine/rashomon.py` `RASHOMON_TRIGGERS`/`POV_INFO_LENS`/`RASHOMON_SCENES`（顶部，仅 `林朔/唐川/白夜/叶琳/墟核` 5 个角色） | ❌ 角色+片段写死 |
| 声音调味（叙述口吻差异） | `engine/scene_director.py` `_VOICE_FLAVOUR_POOL`（line ~723，按 voice flavor 写死）、默认 `pov_char='林朔'`（line 53）、`self._chars.get('林朔')`（line 789） | ❌ 写死 |
| 便于后期修改 | `timeline.py` 架构上支持重排，但事件/选角内容都在 Python 里 | ❌ 改需动代码 |

**核心结论**：POV 技术已"形似"落地，但**选角、事件、透镜、汇聚、声音全是字面量**。换故事/卡司即失效，作者无法"自由选角"，也无法"改 JSON 调整剧情"。这正是本次优化的靶点——把 POV 从"写死的剧情"重构为"作者可配置的叙事系统"。

---

## 2. 优化总纲

两条主线，对应"内容/逻辑解耦 + 事件为线索 + 作者可配置"：

- **内容化**：把视点调度、事件脊梁、时间线规则、风格层抽成 `word_banks` 下的新 JSON 类别（补齐"广度"）。
- **解耦**：运行时引擎改为**消费**这些 JSON，按**角色属性/role** 索引，而非角色名字面量。作者改 JSON 即可重排视点、调整事件，无需碰 Python。

---

## 3. 新增内容类别（word_banks，纯内容，低风险，立即可补广度）

> 体量策略：风格层(3.1–3.4)可用现有扩展工具"模板×属性池"自然放大；分类/配置层(3.5–3.7)优先**质量与可配置性**，不强制凑 1MB。

### 3.1 `narrative/pov_types.json` — 视角类型目录
- 结构：`{ "first_person": {def, markers[], suited_scenes[], pitfalls[]}, "third_limited": {...}, "omniscient": {...}, "second_person": {...}, "unreliable_narrator": {...}, "deep_pov": {...}, "objective_data": {...} }`
- 对齐：百科"基本含义/类型"；为引擎选角提供类型表。

### 3.2 `narrative/pov_lenses.json` — 视角透镜（通用化 `POV_INFO_LENS`）
- 结构：按**角色属性维度**（性格/身份/知识层级/立场/情绪态）生成信息边界：
  `{ "by_role": { "protagonist": {style, adds, header_tpl, footer_tpl}, "observer": {...}, "system": {...}, "bystander": {...} }, "by_personality": { "冷峻": {...}, ... } }`
- 对齐：百科"限制读者信息获取→增强代入"；替换 `rashomon.POV_INFO_LENS` 的写死透镜。

### 3.3 `narrative/interiority.json` — 内省 / 心理活动
- 结构：`{ "soliloquy": [...], "sensory_introspection": [...], "emotion_flow": [...] }`（模板含 `{subj}`/`{mood}` 等槽位）
- 对齐：百科"深入隐秘而细腻的个人层面/展现人物心理"；注入每 POV beat。

### 3.4 `narrative/info_asymmetry.json` — 信息不对称 / 多立场解读
- 结构：`{ "same_event_stances": [ {event_anchor, stances: [{role, reading_tpl}]} ], "cognitive_gap_hooks": [...] }`
- 对齐：百科优点③"公正——读者站在当事人角度评判"；通用化 `rashomon` 的"谁知道什么"。

### 3.5 `narrative/event_spine.json` — 事件脊梁（承载"事件为线索"）
- 结构：可被多视角叙述的**事件原型**（非具体剧情），每事件建议的视点角色集合（按 role）：
  `{ "events": [ {id, name, scope, trigger_cond_tpl, suggested_viewpoints: ["protagonist","observer","system",...], convergence: true/false} ] }`
- 对齐：百科"以事件为线索串联命运"；替代 `timeline.default_timeline()` 的硬编码事件。

### 3.6 `narrative/pov_assignment.json` — 视点分配策略（承载"作者自由选角"）
- 结构：作者可配置的选角规则：
  `{ "default_pov_role_per_event_type": {...}, "switch_rules": [...], "role_pool_by_attribute": {personality_tag: [roles], knowledge_level: [roles]} }`
- 对齐：用户强调点①②；让 `storyline.pov_characters`/`pov_sequence` 由配置解析而非字面量。

### 3.7 `narrative/pov_timeline.json` — 时间线编排规则（承载"编排避免混乱+各线连贯"）
- 结构：汇聚/罗生门规则、防混乱约束、各视点故事线连贯性检查：
  `{ "convergence_rules": [...], "anti_chaos": {max_pov_switch_per_chapter, min_arc_continuity}, "arc_coherence": [...] }`
- 对齐：用户强调点④；约束 `storyline` 汇聚与 `timeline` 排布。

---

## 4. 引擎侧解耦与接入（中/高风险，需评审后执行）

> 实现前需精读对应文件确认接口；此处为方向性方案，Phase 2/3 再给具体 diff。

- **4.1 `timeline.py`**：`default_timeline()` 的硬编码事件 → 从 `event_spine.json` 读取（事件原型 + 触发条件模板），保留原万界归墟等价行为。
- **4.2 `storyline.py`**：`worlds_config` 的 `pov` 字面量、`pov_characters`、`ConvergencePoint.pov_sequence` → 改为按 `pov_assignment.json`/`event_spine.json` 的 **role** 解析，保留原产出等价性。
- **4.3 `rashomon.py`**：`RASHOMON_TRIGGERS`/`POV_INFO_LENS`/`RASHOMON_SCENES` → 外置 JSON，按角色 **role/属性** 索引（通用化复眼，不再限 5 个写死角色）。
- **4.4 `scene_director.py`**：`_VOICE_FLAVOUR_POOL` → 外置 JSON（voice flavor → 叙述口吻）；默认 `pov_char` 改为配置驱动。
- **4.5 `causal_chapter.py`**：复眼触发点保留，内容源切换为 JSON。

目标不变：**万界归墟产出与现状逐字一致（确定性）**，但作者现在能通过编辑 JSON 改变选角/事件/汇聚，而不必改 Python。

---

## 5. 分阶段执行计划与验收

| 阶段 | 内容 | 风险 | 验收标准 |
|---|---|---|---|
| Phase 0 | 调研 + 本方案（已完成） | — | 文档落地 |
| **Phase 1** | 新增 3.1–3.7 共 7 个词库（纯内容） | 低 | 7 库写入 `word_banks`；扩展工具放大风格层体量；`pytest tests/test_parameterization.py` 全过；`build_manifest.py` 重建计数正确；现有 41 库不受影响 |
| **Phase 2** | 引擎 POV 内容解耦（4.1–4.4） | 中 | 硬编码 POV 内容移出 Python；万界归墟产出与重构前 SHA-256 一致；新增回归测试 |
| **Phase 3** | 接入消费 + 作者选角配置入口（可选） | 高 | 3.1–3.7 被引擎实际选用；提供 JSON 配置入口与校验；端到端生成验证 |

---

## 6. 风险与回滚

- 项目已 `git` 跟踪：`.py` 改动可 `git checkout` 回滚；`word_banks` 有 `.backup_originals/`。
- 扩展工具与运行时引擎分离；新增词库不影响现有 41 库。
- Phase 2/3 触碰运行时引擎，必须先证明**万界归墟产出确定性不变**再合并。

---

## 7. 待用户确认

1. **范围**：仅 Phase 1（纯内容、低风险）？还是含 Phase 2/3（引擎解耦，高维护价值但高风险）？
2. **优先级**：先补风格层（3.1–3.4）还是先补架构配置层（3.5–3.7，更贴合你强调的"事件为线索+时间线编排"）？
3. **作者选角入口**：是否需要为"自由选角"做显式配置入口（JSON/YAML + 校验脚本），还是仅作为引擎内部可配置数据？
