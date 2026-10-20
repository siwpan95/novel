# Changelog

本项目所有值得注意的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [3.0.0] - 2026-10-20

### Changed（★ 破坏性：包名改名）

- **包名 `novel_generator` → `wanjie`**（目录、导入路径、`pip` 元数据同步改名）。
  原因：通用内核已以 `novel-generator` 发布到 PyPI，其导入名即为 `novel_generator`；
  本仓若继续沿用会与之撞车。按「以 PyPI 为准」的口径，`novel_generator` 归内核，
  本仓改用 `wanjie`（取自《万界归墟》，且本仓词库早已有 `world/wanjie_context.json`）。
- **实现方式改为 import**：通用内核不再自带，改为依赖 `novel-generator>=2.0.0` 并继承。
  - `wanjie.engine.word_bank.WordBank` → 继承 `novel_generator.engine.word_bank.WordBank`，
    仅保留本仓专属的三件事：词库目录指向 `wanjie/word_banks/`（含子目录递归解析）、
    术语前缀堆叠垃圾过滤 `_filter_pool`、拆分词库合并读取
    `load_world_senses` / `load_voice_helpers`；
  - `wanjie.engine.template.TemplateEngine` → 继承 `novel_generator.engine.template.TemplateEngine`，
    保留本仓模板方言 `{{bank.key[N]}}` / `{{bank.key:unique}}` / `{{bank.key,3}}`，
    并顺带获得内核的修饰符系统与状态变量。
- 控制台脚本 `novel-gen` → `wanjie`（`novel-gen` 已是内核 `novel-generator` 的入口名）。
- 日志文件 `novel_generator.log` → `wanjie.log`；`.gitignore` / `.dockerignore` /
  `Dockerfile` / `.github/workflows/ci.yml` 中的路径同步更新。
- 文档与用法示例同步为 `python -m wanjie`（原 `python -m novel_generator`）。

### Fixed

- `wanjie/__init__.py` 顶部标题原为《宇宙巨校闪级生》（另一部作品的遗留），
  与 README 的《万界归墟》矛盾，已订正。

### 刻意未改

- `deliverables/gstack/pre-launch-check-novel-2026-08-10.md`：2026-08-10 的
  **历史审计记录**，其中仍写着旧包名 `novel_generator`。按既有先例，历史审计快照
  保持原样不回溯改写（它记录的是当时的仓内事实）。

### 验证

- 测试：`pytest wanjie/tests` → **115 passed**（与改名/改造前的基线 115 passed 一致）。
- 内核解析位置确认为 `site-packages/novel_generator`（2.0.0），非本仓目录遮蔽。
- `python -m wanjie --help` 正常；`WordBank(seed=42).generate_name()` /
  `load_world_senses()` / `load_voice_helpers()` 均正常。

## [1.0.0] - 2026-08-27

### Added

- 首个发行版：便携源码 zip（剔除 .venv/构建产物/输出物，依赖见 README）。
- 发布面：gitee [siwpan/novel](https://gitee.com/siwpan/novel) release `v1.0.0`（万界归墟小说生成器 v1.0.0）。