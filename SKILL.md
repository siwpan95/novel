---
name: novel-generator
description: Maintain the 《万界归墟》 event-driven novel generator (G:/ai/novel). World map + timeline + character simulation driven generation with task log.
agent_created: true
---

# novel 《万界归墟》生成器维护

## 概述
事件驱动小说生成（v2.1）：世界地图（WorldState）+ 时间轴（Timeline）+ 角色模拟（CharacterSim）驱动，文本是角色在地图/时间轴上的自然反应。旧版字数驱动（--mode words）保留兼容。

## 结构
- main.py：CLI 入口（--preset/--target-chars/--seed/--resume/--mode/--diagnose/--tasks）
- novel_generator/engine/：word_bank/plot_state/world_state/timeline/storyline/scene_director/integrated_chapter_generator/voice_engine
- novellog.py：任务事件日志（<output>/pipeline.log，7 阶段事件）
- verify_*.py：验证脚本族

## 常用命令
- 生成：python main.py --preset tiny --seed 42（--resume 断点续写）
- 审计：python main.py --tasks [--limit N] [--json]
- 诊断：python main.py --diagnose
- 日志测试：python -m pytest tests/test_novellog.py -q（3/3）

## 已知陷阱
- 步骤 1-6 用 _stage() 包装（阶段事件+耗时），新增阶段沿用该助手
- --tasks 必须在 parse_args 后立即处理（先于引擎导入的重活）
- main() 顶部有 GBK 安全打印 _print_safe，新增符号输出走它
