# 《万界归墟》小说生成器

## 仓库角色定位（投资组合分级 ②）

> 本仓在 siwpan 投资组合（D:/projects/repos，共 133 仓）中定级为 **② 精选旗舰**，领域 **小说/网文**。
> **角色**：小说生成旗舰。
> **维护策略**：② 旗舰 / 枢纽仓库打磨保留，作为能力展示或收敛点；② 保留类仓库低优先维持、不主动扩张。
> 投资组合统一分级索引：`D:/projects/repos/PORTFOLIO_TIERING.md`。

> 仓库：<https://gitee.com/siwpan/novel> ｜ 许可：MIT（见 [LICENSE](LICENSE)）

双引擎程序化中文小说生成系统——融合 ASP 模板流（词库驱动多层嵌套循环）与因果链流（Save the Cat! 15 节拍叙事结构），自动生成莲花式地图诸天无限流长篇小说。

## 📦 包名与内核依赖

本项目**服务于《万界归墟》这一部特定作品**（世界观、词库、节拍全部绑定），
因此**不发布到 PyPI**——完成度再高，通用性也有限。通用内核单独拆出并已发布：

| | 发行名（PyPI） | 导入名 | 定位 |
|---|---|---|---|
| **内核**（已发布） | [`novel-generator`](https://pypi.org/project/novel-generator/) | `novel_generator` | 通用 ASP 模板流引擎 |
| **本项目**（不发布） | — | `wanjie` | 《万界归墟》专属内容层 |

`wanjie` 以**依赖 + 继承**的方式复用内核，不再自带通用实现：

```python
from novel_generator.engine.word_bank import WordBank      # 内核基类
from wanjie.engine.word_bank import WordBank                # 本仓子类
```

- `wanjie.engine.word_bank.WordBank` 继承内核 `WordBank`，只覆写三件事：
  词库目录指向本仓 `wanjie/word_banks/`、术语前缀堆叠垃圾过滤、拆分词库合并读取；
- `wanjie.engine.template.TemplateEngine` 继承内核 `TemplateEngine`，
  保留本仓模板方言（`{{bank.key[N]}}` / `{{bank.key:unique}}` / `{{bank.key,3}}`），
  同时获得内核的修饰符系统与状态变量。

> **3.0.0 之前本仓的包名也叫 `novel_generator`**。内核发布后两者导入名撞车，
> 按「以 PyPI 为准」的口径：`novel_generator` 归内核，本仓改为 `wanjie`
> （取自《万界归墟》，且本仓词库早已有 `world/wanjie_context.json`）。

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
python -m wanjie                                   # 交互式菜单（含 asp / causal）
python -m wanjie --diagnose                        # 诊断报告
```

> `pip install -e "."` 会自动拉入内核依赖 `novel-generator>=2.0.0`。

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
| [ARCHITECTURE.md](wanjie/ARCHITECTURE.md) | 引擎架构详解 |
| [docs/WORD_BANK_GUIDE.md](docs/WORD_BANK_GUIDE.md) | 词库结构与扩词指南 |
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
pytest --cov=wanjie
ruff check wanjie/
mypy wanjie/
```

## 📄 许可证

MIT License — 详见 [LICENSE](LICENSE)
