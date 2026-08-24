# 《万界归墟》小说生成器

双引擎程序化中文小说生成系统——融合 ASP 模板流（词库驱动多层嵌套循环）与因果链流（Save the Cat! 15 节拍叙事结构），自动生成莲花式地图诸天无限流长篇小说。

## 🚀 快速开始

```bash
# 环境要求：Python >= 3.10
git clone <repo-url>
cd novel

# 安装并运行
pip install -e "."
python main.py                                      # 默认 tiny（2 万字）快速验证
python main.py --preset book                        # 整书 20 万字
python main.py --target-chars 80000                 # 自定义目标字数
python -m novel_generator                           # 交互式菜单（含 asp / causal）
python -m novel_generator --diagnose                # 诊断报告
```

## 🧠 核心架构

| 组件 | 角色 | 描述 |
|------|------|------|
| **引擎1 (ASP)** | 声音 | 多层嵌套循环 + 15 个 JSON 词库随机替换 |
| **引擎2 (因果)** | 大脑 | Save the Cat! 15 节拍 + 千层饼 6 层揭秘 |
| **融合层** | 编排 | `NarrativeContext` 共享总线 → `VoiceEngine` 词库渲染 |

```
                 NarrativeContext（共享总线）
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    BeatOrchestrator  VoiceEngine  TextQualityPipeline
    （节拍→操作序列）  （词库渲染）   （去AI味质检）
```

## 📖 文档导航

| 文档 | 内容 |
|------|------|
| [ARCHITECTURE.md](novel_generator/ARCHITECTURE.md) | 引擎架构详解 |
| [spec/Novel-Bible.md](spec/Novel-Bible.md) | 万界归墟世界观设计圣经 |
| [spec/Research-Report-Enhancement-Plan.md](spec/Research-Report-Enhancement-Plan.md) | 调研报告与强化方案 |
| [spec/Volume-2-3-Expansion-Plan.md](spec/Volume-2-3-Expansion-Plan.md) | 多卷展开方案 |

## ⚙️ 命令行参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--target-chars` | int | (无) | 目标字数（优先级高于 --preset） |
| `--preset` | str | tiny | tiny=2万 / small=5万 / book=20万 |
| `--seed` | int | 随机 | 随机种子（留空则每次不同） |
| `--output` | str | output/ | 输出目录 |
| `--resume` | flag | false | 从 plot_state.json 断点续写 |
| `--diagnose` | flag | false | 引擎诊断报告 |

## 🧪 开发

```bash
pip install -e ".[dev]"
pytest --cov=novel_generator
ruff check novel_generator/
mypy novel_generator/
```

## 📄 许可证

MIT License — 详见 [LICENSE](LICENSE)
