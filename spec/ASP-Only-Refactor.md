# ASP 唯一引擎重构计划（拆硬编码 → 词库 · 废大纲/因果链 · 强化 ASP 模板流）

> 目标：让《万界归墟》生成器回归**纯 ASP 模板流**（`generators/` + `template.py` + `word_bank.py`），
> 所有 SCENE 内容来自词库 + 发牌员（bag 无放回）驱动，废除大纲/因果链/事件驱动等全部并行架构。
> 决策已确认：**因果链 + 事件驱动都废**；**ASP 强化为唯一引擎**。

---

## 一、现状（4 套架构并存，需收敛为 1 套）

| 架构 | 模块 | 处置 |
|---|---|---|
| ASP 模板流（保留） | `generators/`(novel·chapter·character·battle·dialogue) + `template.py` + `word_bank.py` + `dealer.py` | 保留并强化 |
| 因果链（废） | `causal_chapter.py` `beat_orchestrator.py` `beat_orchestrator_legacy.py` `beat_constants.py` `beat_narratives.py` `causal_dialogue.py` | 废除 |
| 字数/涌现（废） | `wordcount_director.py` `emergent_orchestrator.py` `narrative_state.py` | 废除 |
| 事件驱动（废） | `scene_director.py` `storyline.py` `timeline.py` `world_state.py` `knowledge_graph.py` | 废除 |
| 融合/质量管线（废，随因果链） | `integrated_chapter_generator.py` `voice_engine.py` `plot_state.py` `narrative_context.py` `rashomon.py` `expansion.py` `rhythm_engine.py` `rubric_player.py` `text_quality.py` `llm_rewrite.py` `fusion_generator.py` `interactive_nlp.py` | 废除（其硬编码场景文本先提取进词库） |

## 二、硬编码内容分布（提取目标）

- `voice_engine.py`：**416 处**（开场场景 `_render_guixu_opening`/`_render_generic_opening`、`render_scene_beat` 等）→ 主要提取源
- `causal_chapter.py`：334 处 → 整模块废除，其中有价值场景句择取进词库
- `beat_orchestrator.py`：142 处硬编码 TEXT 拍点文本 → 提取进 `narrative/` 词库（部分已由 beat_narratives.json 承载）
- `scene_director.py` / `storyline.py`：158 / 115 → 废除

## 三、分阶段执行

### Phase 1 —— 提取 SCENE 硬编码 → 词库（不破坏现有）
1. 读 `voice_engine.py` 全量场景渲染方法，逐条拆出硬编码散文。
2. 写入对应词库：
   - 开场场景 → `world/world_openings.json`（按世界 key）
   - 场景节拍散文 → `narrative/scene_beats.json`
   - 感官氛围句 → `world/senses/*`
3. 每次写入用 Python json.load/dump，写后校验；保留可复现。

### Phase 2 —— 强化 ASP（唯一引擎）
1. 新建/升级 `generators/scene.py`：场景段落由 `world_openings + scene_locations + world_senses + adjectives` 经模板 + 发牌员组装。
2. 接入 `Dealer`（bag 无放回）到 ASP 词库选择，替换 `WordBank.pick` 的 `random.choice`（有放回）。
3. 世界专属词库注入（genre_terms/*、wuxia_terms 等）。
4. `generators/chapter.py` 改用新的场景生成器。

### Phase 3 —— 废除相关逻辑
1. 删除因果链 + 事件驱动 + 融合/质量管线各模块文件。
2. 简化 `unified_engine.py` 为 ASP-only 入口（`generate(mode='asp', ...)`），删 `words/causal/integrated/asp 废弃` 分支。
3. 简化 `main.py` / `__main__.py` CLI。

### Phase 4 —— 测试收敛
1. 删除/重写依赖被废模块的测试（`test_parameterization.py` 测 BeatOrchestrator、`test_wordcount.py`、`test_resume_e2e.py`、`test_emergent_dealing.py`、`test_deal.py` 中集成部分）。
2. 新增：ASP 场景生成测试、Dealer 集成测试、模板流端到端测试。
3. 全套 pytest 绿。

## 四、风险与护栏
- **可复现**：同 seed 同输出；发牌员确定性。
- **零依赖**：不引入重依赖。
- **词库原子写**：Python json 写 + 回读校验；失败不动原文件。
- **渐进提交**：每阶段跑 pytest，不跨阶段混改。
