# 《万界归墟》小说生成器 v2.1.0 上线前全检报告

**日期**：2026-08-10
**项目**：`G:\novel` — 双引擎程序化中文小说生成系统
**场景**：上线前全检（代码审查 + 安全审计 + QA测试）
**参与成员**：产品官（代码审查） + 安全卫士（OWASP+STRIDE） + 质量门神（QA与发布）
**审查基线**：工作区当前状态（87 项未提交 git 变更），非 HEAD

---

## 📌 TL;DR

- **整体结论：🔴 No-Go，不具备发布条件。**
- 三位成员**独立**得出的结论一致指向同一事实：**这个仓库现在装不上、CI 从没绿过、默认引擎零测试覆盖，且工作区是一次进行到一半的 v3 范式重写。**
- **最危险的不是跑不起来，而是"报告成功却悄悄丢数据"**：`--resume` 断点续写会静默丢失已生成正文，产出「文件名写 19,941 字、实际只有 10,082 字」的伪成品。**且状态越 resume 越坏**——`scene_director.py:1113` 把累计段数覆盖为仅新段数，第二次续写比第一次错得更多。
- 阻塞项：**7 项**（🔴）；另有 8 项高、12 项中、6 项低，共 33 项。
- 一个好消息：**已提交的 HEAD 版本是健康的**，实测可正常生成 4,058 字。坏的是工作区，不是仓库历史。
- 下一步：先吊销泄露的 Tavily 密钥 → 修 pyproject → 补齐 6 个未跟踪模块 → 修 resume 数据丢失 → 再谈发布。

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| **Go / No-Go** | 🔴 **No-Go** |
| 发布就绪度 | **28 / 100**（QA 评分） |
| 严重度分布 | 🔴 7 / 🟠 8 / 🟡 12 / 🟢 6（共 33 项） |
| 三方独立交叉确认项 | 3 项（打包后端失效、依赖声明脱节、密钥明文落盘） |
| 关键行动项 | 7 条 P0 |
| 建议负责人 | 项目作者本人（单人项目） |
| 预计解除阻塞工作量 | P0 全修约 1–2 个工作日（不含 v3 测试补齐） |

---

## 1. 各成员核心结论

### 🔍 产品官（代码审查）

**核心判断：No-Go。工作区处于 v3 范式重写进行中，不是"改完待提交"。**

最致命的发现是**原子提交断裂**：`main.py:35-38` 与 `engine/beat_orchestrator.py:25` 这两个**已跟踪**文件，硬依赖 6 个**未跟踪**模块（world_state / timeline / storyline / scene_director / beat_orchestrator_legacy 等）。他做了实证——克隆 HEAD 后覆盖全部 tracked 改动，直接 `ModuleNotFoundError: novel_generator.engine.world_state`。结论是"现在 `git commit -a` 会产出一个不可运行的仓库"。

判断依据不止于此：`main.py` 的 diff 里作者自己写着「彻底摈弃大纲/节拍体系」，`beat_orchestrator.py` 砍掉 457 行。另发现 **CI 从未真正运行过**——`git remote -v` 为空，根本没有远端仓库。

**关键建议**：先把 6 个 engine 模块入库形成可运行基线，再谈其它。

> 他同时**主动纠正了两条我提供的错误线索**：print 调试残留不成立（engine/ 仅 10 处，均属 CLI 正常输出）；TODO/FIXME/XXX/HACK 全仓 **0 处**。并确认 `word_banks/` 全部 JSON 校验合法。

### 🛡️ 安全卫士（OWASP + STRIDE 审计）

**核心判断：🟠 有条件 Go（安全维度单看）。全部发现均已实机复现。**

真实资产风险只有一处但很急：`tools/wordbank_expand/tavily.key` 存着**真实密钥**，`git check-ignore` 返回未忽略，`git add --dry-run` 实测会把它加进暂存区；叠加 `Dockerfile:9` 的 `COPY . .` 且无 `.dockerignore`，密钥会焊进镜像层。

Web GUI 是第二个问题：绑 `0.0.0.0`、CORS `Access-Control-Allow-Origin: *`、六个路由零鉴权。他实测跨源打通了 `POST /api/stop` → `200 {"ok":true}`，任意恶意网页可远程中断用户的生成任务。

**关键建议**：吊销密钥 + `HOST` 改 `127.0.0.1` + 去掉 `ACAO:*`（后两项合计 2 行改动）。

> 他明确划了误报边界：**"无鉴权本身不是缺陷，缺陷是它绑了 0.0.0.0 且开了 CORS `*`，这让单机假设失效。"** 并逐项列出**已核实无风险**的 7 个攻击面（Werkzeug 调试器已关、无 pickle/eval、路径遍历实测全 404、日志与 git 历史扫描零命中、SSRF 出口硬编码、CI 无注入），没有凑数。

### ✅ 质量门神（QA 测试与发布）

**核心判断：🔴 No-Go，发布就绪度 38/100。全部结论基于双 Python 版本实测。**

测试套件在 3.14.6 与 3.13.14 下均为 **114 通过 / 1 失败**。他把那个失败追到了根：`test_deal.py:410 test_stress_30_chapters` 是**测试缺陷而非产品 bug**——用探针跑了多组种子证明（seed=5 恰好 exhausted=0，其余 seed 均为 4~6），断言硬编码依赖 RNG 路径，只差一次发牌。

**最严重的是 B1**：`SceneDirector.generate(resume=True)` 只恢复计数器、不恢复已生成文本，`_finalize(buffer)` 只写新增段落。实测模拟 50% 中断后 resume，产出文件页眉声称「实得字数 19,941」，实际只有 10,082 字，**前 9,941 字永久丢失**；对已完成任务 resume 则产出 130 字节空壳。

**关键建议**：B1 是硬门槛——默认引擎 0% 覆盖叠加静默数据丢失，不修不能发。

> 他还给出了**已验证可用**的 B2 修复方案（不是猜的）：`build-backend="setuptools.build_meta"` + `[tool.setuptools.packages.find] include=["novel_generator*"]`，改完实测安装成功且 `novel-gen --diagnose` 可用。

---

## 2. 综合审查发现（去重合并，按严重度排序）

### 🔴 阻塞上线（7 项）

| # | 类别 | 位置 | 问题描述 | 建议 | 来源 |
|---|------|------|---------|------|------|
| 1 | 数据安全 | `engine/scene_director.py:281-282, 285, 319, 1103, 1110-1113` | **`--resume` 静默丢失正文 + 状态持续腐蚀**。详见下方专项分析。产出「页眉 19,941 字 / 实际 10,082 字」的伪成品；已完成态 resume 产出 130 字节空壳；**且每 resume 一次状态就更坏一次** | 恢复时载入已有正文再续写；修 `:1113` 段数覆盖；补 resume 回归测试；修好前 README 显著标注禁用 | QA 实测 + 代码审查源码复核 |
| 2 | 可分发性 | `pyproject.toml:3` | **打包后端根本不存在**。`build-backend="setuptools.backends._legacy:_Backend"` 在 setuptools 84 实测 `ModuleNotFoundError`，该私有模块从未存在 → `pip install .` / `-e .` / `python -m build` 全炸，v2.1.0 无法分发 | 改 `setuptools.build_meta`，并补 `[tool.setuptools.packages.find] include=["novel_generator*"]`（已验证可用） | **三方共同确认** |
| 3 | 版本控制 | 25 个 untracked `.py`；入口 `main.py:35-38`、`engine/beat_orchestrator.py:25` | 🔺**已升级为最高优先级**。**默认 v3.0 引擎的全部核心模块从未进过版本控制**——tracked 48 个 .py / **untracked 25 个**，含 `scene_director.py`(1115行) `storyline.py`(595) `world_state.py`(256) `timeline.py`(194) `knowledge_graph.py`(374) `beat_orchestrator_legacy.py`(475)、两套 GUI、9 个测试里的 3 个。详见下方专项 | **发布前第一件事**：`git add` 全部核心文件；CI 加「干净 clone 后跑冒烟」防复发 | 代码审查发现 + QA 量化升级 |
| 4 | 密钥泄露 | `tools/wordbank_expand/tavily.key` | **真实 Tavily 密钥明文落盘且未被 ignore**。`git add --dry-run` 实测会加入暂存区；`Dockerfile:9 COPY . .` 无 `.dockerignore` → 焊进镜像层 | **立即吊销该 key**；`.gitignore` 加 `*.key`/`.env`；新建 `.dockerignore`；仅保留环境变量读取 | 安全 + 代码审查 |
| 5 | CI/质量门禁 | `.github/workflows/ci.yml` | **CI 从未运行过且必红**。`git remote -v` 为空无远端仓库；`ruff check` 实测 **621 errors**（硬门禁，无 `\|\| true`）；`pytest` 1 failed；四个矩阵版本的 `pip install -e ".[dev]"` 全因 #2 失败 | 修 #2 → `ruff --fix` 清理 + per-file-ignores → 修 test_deal.py:410 → 接上远端 | 代码审查 + QA |
| 6 | 测试覆盖 | `novel_generator/tests/` | **v3 主路径零测试**。默认引擎全链路 0% 覆盖：scene_director(568 语句) / storyline(282) / world_state(155) / timeline(115) / knowledge_graph+llm_rewrite+interactive_nlp(372) 均 **0%**；115 个测试全在测 v2 legacy 路径。总覆盖 30.54%，距门禁 30 仅剩 0.54pp。**注意：这些 0% 模块不是死代码**——其中 llm_rewrite/interactive_nlp/knowledge_graph 挂在用户可直接调用的 `--polish`/`--interactive` 开关下（详见 🟡#25），属「可达路径盲区」而非单纯测试缺口 | 补 v3 冒烟 + resume 回归测试；提高 `fail_under`；下线或补测 `--polish`/`--interactive` | 代码审查 + QA |
| 7 | Web 安全 | `gui/app.py:30`、`gui/config.py:8`、`app.py:308-314` | **Web GUI 绑 0.0.0.0 + CORS `*` + 零鉴权**。跨源实测 `POST /api/stop` → 200 成功中断任务；`/api/health` 泄露磁盘容量与输出路径 | `HOST` 改 `127.0.0.1`；删 `ACAO:*` 或白名单；`/api/stop`、`/api/generate` 加 CSRF token | 安全 |

> **#7 适用范围**：若本次仅发 CLI 且 GUI 标注「实验性 / 仅本机」，#7 可降级 P1。

#### 🔬 专项：#3 为什么是全部阻塞项里的第一顺位

**核心事实：你本机跑得好好的东西，别人拿不到。**

| 证据 | 实测结果 |
|------|---------|
| HEAD 的 `main.py` 引用 `scene_director` | **0 次**（工作区引用 1 次）→ 已提交的是 v2.x legacy，工作区才是 v3.0 |
| 干净 clone 跑 `main.py` | 走 legacy 引擎，输出 `万界归墟_字数目标_2060字`，**不是要发布的 v3.0** |
| 模拟最常见发布动作 `git commit -am "release v2.1.0"` 后跑默认命令 | `ModuleNotFoundError: No module named 'novel_generator.engine.world_state'`（`main.py:35`） |

**四条发布路径全崩**：`git commit -am` / `git archive` / sdist 打包 / 用户 `git clone` —— 都会静默漏掉 untracked 文件，产出**开箱即崩**的包。而作者本机一切正常，完全无感。

**为什么排在 🔴#1（resume 丢数据）之前**：#1 得用户主动加 `--resume` 才踩得到；#3 是**第一条命令就死**。且 #3 是其他一切的前提——代码没入库，连回滚基线都不存在。

> 教科书级的「本地能跑 ≠ 能发布」。现有 CI 用 `actions/checkout`，本来恰好能测出这个问题，但因 🔴#2 装不上，这一步从没真正跑到过——**两个缺陷互相掩护**。

#### 🔬 专项：#1 resume 数据丢失的完整链路（QA 实测 + 代码审查源码复核）

`novel_generator/engine/scene_director.py`：

| 行号 | 代码行为 | 后果 |
|------|---------|------|
| `:281-282` | resume 仅恢复 `_total_chars` / `_passage_no` 两个**计数器** | 旧正文未载入 |
| `:285` | `buffer=[]` 从空开始 | 缓冲区不含历史内容 |
| `:319` | 只 append 新段落 | 同上 |
| `:1103` | `full='\n\n'.join(buffer)` | 只拼新内容 |
| `:1111` | `f.write(full)` | **旧文本被永久覆盖丢失** |
| `:1110` | 页眉写恢复后的 `_total_chars`（含旧字数）却配 `len(buffer)`（仅新段） | 字数与段数来自两个不同真相源 → 伪成品 |
| `:1113` | `self._ps.state['current_passage']=len(buffer)` 把**累计段数覆盖为仅新段数** | 🔥 **第二次 resume 比第一次更错，状态越修越坏** |

**根因**：状态持久化了**计数器**却没持久化**产物**，形成两个真相源。这是核心宣传功能（README 与 `main.py --resume` 均明确宣传断点续写）带静默数据丢失，无降级空间。

> `:1113` 这条是**代码审查在 QA 实测结果基础上回头复核时新发现的**——QA 只测了单次 resume，没暴露出多次 resume 的累积腐蚀。两人的方法论在此互补：运行时观测发现症状，静态复核找到病灶并预测了更坏的场景。

### 🟠 高（8 项）

| # | 类别 | 位置 | 问题 | 来源 |
|---|------|------|------|------|
| 8 | **产品质量** | 生成正文；根因 `engine/scene_director.py:273` | **正文重复率 28.8% / 34.1% / 34.9%**（seed 777/12345/999）。同一 87 字设定段落复现 31–39 次，`如果当时…林朔把这句话咽了回去。`×12。**约 1/3 输出是重复文本**。根因：`self._long_counter` 的跨段去重机制**对整段插入无效**。⚠️ 这直接打脸项目「抗罐头味」的核心卖点 | QA 实测 + 代码审查定位 |
| 9 | 产品质量 | `tools/wordbank_expand/_gen_pov_banks.py:123,125` | **模板槽位填充错误**：`{line}` 被填成 `{pov}` → 正文出现「林朔在心里对自己说：林朔」。跨 3 种子稳定复现 15–17 行/次 | QA |
| 10 | 用户体验 | `README.md:12` vs `gui/app.py:26`、`gui_qt.py:18`、`gui_tk.py:34` | **「纯标准库零外部依赖」是错的**。实际硬依赖 flask/waitress/PyQt5，`pyproject` 无 `[project.dependencies]`。干净环境实测双双 `ModuleNotFoundError`，新用户必踩 | 三方共同确认 |
| 11 | 可分发性 | `pyproject.toml` | **wheel 缺词库**。无 `MANIFEST.in`、无 package-data → 修好 #2 后安装仍缺 `word_banks/*.json` | 代码审查 |
| 12 | 一致性 | `__init__.py:16` / `pyproject:9` / `main.py:117` | **版本号三重矛盾**：1.0.0 / 2.1.0 / v3.0 | 代码审查 |
| 13 | 可用性 | `main.py:105` | `--diagnose` 在默认 scene 模式被**静默忽略**（分支嵌在 `if args.mode=='words'` 内），直接开跑 2 万字 | QA |
| 14 | DoS | `gui/app.py:133`、`:189` | `target` 参数无上限且 buffer 全量驻留内存。实测 `target=100000000` 被接受并开跑 → CPU/内存/磁盘三重耗尽 | 安全 |
| 15 | 版本控制 | `.gitignore:15` | **行尾注释导致规则失效**（git 不支持 `#` 尾注），实测 `extract_beat_texts.py` 未被忽略；`.coverage.*`、`*.zip`、`*.key` 均未覆盖 | 安全 + 代码审查 |

> **一条被推翻的推测**：安全官曾建议「`--polish` 污染状态与 🔴#1 resume 数据丢失是同一根因，应合并排查」。QA 实测**否定**——两者代码路径完全不同（`plot_state.py:211-213` 裸 append vs `scene_director.generate(resume=True)` 只恢复计数器），共性仅是「共用同一个无隔离的全局 state 文件」。故该项未升级为 🟠，降为 🟡#26/#27 分列。

### 🟡 中（12 项）

| # | 位置 | 问题 | 来源 |
|---|------|------|------|
| 16 | `expand_engine.py:123-138` → `templates/index.html:301,367` | **XSS 链路**：Tavily 抓取内容仅做中文病句过滤无 HTML 清洗 → 落盘词库 → `innerHTML +=`。实测 `<svg/onload=alert()>` 可穿透 `polluted()` | 安全 |
| 17 | 全仓 | **双架构并存**：v2 `UnifiedNovelEngine`（`__main__.py`+全部测试）与 v3 `SceneDirector`（main.py+3 套 GUI）靠多继承 Legacy 保兼容 | 代码审查 |
| 18 | `KeShiLuGangBiHeTi/`、`gui/static/`、`tools/wordbank_expand/` | **待入库垃圾约 62MB**：同一 13MB TTF 存了**四份**、7.9MB zip、`engine.py.bak`、`_dbg*/_probe*`。当前 `.git` 才 2.3MB | 代码审查 |
| 19 | 19 个文件 | **mypy 63 errors 被 CI `\|\| true` 静默**（如 `wordcount_director.py:284` 声明返回 str 实返 None） | 代码审查 |
| 20 | `engine/` | **29 处 `except Exception` + 7 处静默 `pass`**，会吞掉生成失败 | 代码审查 |
| 21 | 生成正文 | `。。` 连续句号 26–29 行/次；破碎比喻「苦涩断柱如沉重。」；孤立残句「星辰重剑戟」 | QA |
| 22 | `voice_engine.py`(1186行)、`scene_director.py`(1115行) | 单文件职责过载 | 代码审查 |
| 23 | 全仓 | 无 `.gitattributes`，LF↔CRLF 抖动（git 对 11 个文件告警） | 代码审查 |
| 24 | `novel_generator/causal_main.py:68` vs `:229-234` | **`--api-key` 是幽灵参数**。`:68` 向用户打印用法 `--polish --api-key YOUR_KEY`，但 argparse 从未注册 `--api-key`。**执行实证**：`SystemExit(code=2)` / `error: unrecognized arguments: --api-key TESTKEY`，已注册项仅 `['-h','--help','-s','--seed','-o','--output','--outline','--full','--polish','--interactive']`。`--polish` 的 help 还写着「需提供API key」，指引用户走一条不存在的路 | QA + 安全（执行实证） |
| 25 | `engine/llm_rewrite.py`(111语句) / `interactive_nlp.py`(93) / `knowledge_graph.py`(168) | **0% 覆盖 ≠ 死代码，而是「可达但未测的用户路径」**。`causal_main.py:30` 导入、`:59` 实例化、`:233` 注册 `--polish`、`:250-251` 分发 → 这是**已注册、用户可直接调用的 CLI 开关**，背后 `run_polish_demo()`/`run_interactive()` 全程零覆盖。当前状态是「可点、没测过、文档还教错用法」。**处置二选一**：补测，或在 v2.1.0 明确下线这两个开关 | QA（推翻安全侧初判，安全侧已复核认可） |
| 26 | `causal_main.py --polish` → `spec/tracking/plot_state.json`；根因 `plot_state.py:211-213`、调用方 `causal_chapter.py:139,152` | **名为 demo 的只读命令有持久化写副作用**。安全官发现（哈希 `4189E365…`→`246D54E7…`），QA 独立复现 `MUTATED=True`。**实测澄清危害边界**：resume 三个关键计数器 `current_chars/current_passage/current_chapter` **均未变**，实际变的是 `chapter_summaries` 追加 1 条 + 时间戳 → **不会直接破坏断点续写**，但会污染共享状态文件 | 安全发现 + QA 复核定级 |
| 27 | `plot_state.py:211-213` `add_chapter_summary()` | **`chapter_summaries` 无去重无上限，单调增长**。裸 `.append()` → 当前 **1647 条摘要只对应 71 个不同章号**（第 7 章重复 82 次），**23 倍冗余**，文件 312 KB。性能影响实测可忽略（`PlotState()` 构造 4.9 ms），且唯一读取方 `interactive_nlp.py` 非主路径 | QA（执行实证 + 量化） |

### 🟢 低（6 项）

| # | 位置 | 问题 | 来源 |
|---|------|------|------|
| 28 | `gui/app.py` | CSP / X-Frame-Options / X-Content-Type-Options / Referrer-Policy 全缺失 | 安全 |
| 29 | `gui/app.py:133` | `target=abc` → HTTP 500（无堆栈泄露） | 安全 |
| 30 | `.coverage.siwpan.pid20664.*` | 暴露主机名与 PID，未被 `.coverage` 规则匹配 | 安全 |
| 31 | `word_bank.py:57`、`plot_state.py:33` | `json.load` 无 try/except，畸形 JSON 崩溃 | 安全 |
| 32 | `main.py:132` | 「活跃世界 2 个」但预加载 3 个；场景标签仅 2 种。**经源码复核：非 bug**——是 timeline 事件门控未触发（tiny 预设跑不到解锁点），定性为「世界地图深度低于宣称」，实为 🟡 而非缺陷 | QA 发现 + 代码审查澄清 |
| 33 | `causal_main.py:68` | **密钥传参反模式（CWE-214）**。该行教用户 `--api-key YOUR_KEY`——CLI 参数会进入 shell history、`ps`/任务管理器进程列表、CI 日志。当前无害（参数未实现，见 🟡#24），但这是未来接线的**设计指引**，会把开发者引向错误模式 | 安全 F-10 |

> #33 与 🟡#24 是同一行代码的两个视角：#24 看**功能契约破裂**（照抄必报错），#33 看**安全反模式**（教人用错误方式传密钥）。修的时候一起处理：删掉这行；未来实装 LLM 走环境变量或配置文件，**别重蹈 `tavily.key` 的覆辙**。

---

## 3. 三方交叉印证（可信度最高的三条）

同一问题被**独立**发现三次，说明不是误判：

| 问题 | 产品官 | 安全卫士 | 质量门神 |
|------|--------|---------|---------|
| `pyproject` build-backend 不存在 | #2 `BackendUnavailable` | F-03 `ModuleNotFoundError` | B2 且**给出已验证修复方案** |
| README「零依赖」与实际脱节 | #6 | F-06 | 干净环境实测复现 |
| Tavily 密钥明文未 ignore | #5 | F-01（`git add --dry-run` 实证） | — |

---

## 4. OWASP Top 10 (2021) 检查表

| 项 | 结论 |
|---|---|
| A01 失效访问控制 | ❌ 命中 — `gui/app.py` 6 个路由零鉴权 |
| A02 加密失败 | ✅ 无密码/加密逻辑；`secret_key=os.urandom(24)` 用法正确 |
| A03 注入 | ✅ 无 SQL/命令/模板注入（无 DB、无 subprocess、Jinja 自动转义）；⚠️ DOM 侧见 #16 |
| A04 不安全设计 | ❌ 命中 — 无速率限制/资源配额 |
| A05 安全配置错误 | ❌ 命中 — `0.0.0.0` + `ACAO:*` + 无安全头；✅ debug 已关 |
| A06 过时组件 | ⚠️ 依赖未声明未固定；无已知 CVE 组件 |
| A07 认证失败 | ➖ 不适用（无用户体系），但 A01 使「无认证」成为问题 |
| A08 完整性失败 | ❌ 命中 — 构建后端无效 + Dockerfile 无 `.dockerignore`；✅ 无不安全反序列化 |
| A09 日志监控失败 | ⚠️ 低 — 仅记录异常，无访问审计（本地工具可接受） |
| A10 SSRF | ✅ 已核实无风险（出口硬编码常量） |

## 5. STRIDE 威胁模型

| 信任边界 | S 仿冒 | T 篡改 | R 抵赖 | I 泄露 | D 拒服 | E 提权 |
|---|---|---|---|---|---|---|
| **本地 CLI** | — | 🟢 低 | — | 🟢 低 | 🟢 低 | ✅ 无（无 eval/subprocess） |
| **Web GUI** | 🔴 无身份概念，局域网任意主机=管理员 | 🟡 恶意词库→XSS | 🟢 无访问日志 | 🔴 `ACAO:*` 跨源读磁盘/状态 | 🟠 无界 target 三重耗尽 | 🟢 无可提权路径 |
| **外部 API (Tavily)** | 🟢 HTTPS 校验默认开 | 🟡 返回内容零清洗入库 | — | 🔴 key 明文可被 git/docker 带出 | 🟢 timeout=30 已设 | — |
| **文件系统** | — | ✅ mkstemp+os.replace 原子写，实现正确 | — | 🟢 输出路径服务端固定 | 🟢 | ✅ 无路径遍历（实测全 404） |

---

## 6. 已核实无风险（避免重复排查）

以下攻击面经实证**确认安全**，不必再查：

- **Werkzeug 调试器 RCE** — `app.py:342 debug=False`，启动日志 `Debug mode: off`
- **代码注入 / 反序列化** — 全仓 75 个 .py 扫 `eval|exec|os.system|subprocess|pickle|marshal|yaml.load`，仅 1 处无害常量；状态文件走 `json.load` 非 pickle
- **路径遍历** — `/static/../app.py`、`%2e%2e` 等 4 种绕过实测**全 404**；全仓无 `os.path.join(用户输入)`
- **日志泄密** — 89KB `novel_generator.log` 与 `gui_server.log` 扫密钥/绝对路径**零命中**，且已被 gitignore 覆盖
- **git 历史** — 25 次提交全历史文件名扫描无 `.key/.env/.pem/secret`
- **CI 供应链** — 无 `pull_request_target`、无 `secrets.*`、无 shell 注入，action 用 v4/v5
- **调试残留** — print 仅 10 处均属 CLI 正常输出；TODO/FIXME 全仓 0 处
- **数据完整性** — `word_banks/` 全部 JSON 校验合法；测试套件不污染 `output/`（实测 4→4）
- **可复现性** — 同种子跑两次输出**字节完全一致**
- **HEAD 版本可用性** — 已提交代码实测可正常生成（4,058 字）
- **LLM 模块无出网攻击面** — 该模块经 `causal_main.py:30` 导入、`:59` 实例化，挂在已注册的 `--polish` 开关（`:233/:250-251`）上，**属可达代码**。但 `__init__(call_fn=None)` 是依赖注入设计，唯一实例化点为**无参构造** → `_call_fn = None` → `polish()`（`llm_rewrite.py:98-102`）走 else 本地占位分支，返回 `'[需外部LLM调用] …'`。
  **运行时实证**（给 `socket.connect`/`connect_ex`/`getaddrinfo` 及密钥类 `os.environ.get` 装探针后真实执行 `causal_main --polish`）：`EGRESS attempts: NONE`（无连接、无 DNS）、`secret env reads: NONE`、`_call_fn is None -> True`、`polish() 返回占位串 -> True`。全仓无 `openai/anthropic/requests/httpx` 导入。
  **结论：外部 LLM 接线从未落地，不出网、不读密钥、不外发正文。**
  > ⚠️ 此条曾被误述为「零引用死代码」，已撤回——正确理由是「**唯一实例化点未注入 `call_fn`**」。修正后结论反而更强：从静态推断升级为执行证据。

---

## 7. ⛔ 阻塞项清单（发布前必须清零）

| 序 | 阻塞项 | 判定依据 | 解除条件 |
|---|--------|---------|---------|
| **P0-1** | Tavily 密钥泄露风险 | `git add --dry-run` 实证 | 密钥已吊销 + `.gitignore`/`.dockerignore` 就位 |
| **P0-2** | 包无法安装 | 三方独立复现 | `pip install .` 成功且 `novel-gen` 可用 |
| **P0-3** | 提交即产出不可运行仓库 | 模拟提交实证 | 6 个 engine 模块入库，克隆后可跑通 |
| **P0-4** | `--resume` 静默丢数据 + 状态持续腐蚀 | 中断实测丢失 9,941 字；`:1113` 源码复核确认多次 resume 累积恶化 | 修复三处 + **多次连续 resume** 回归测试通过 |
| **P0-5** | CI 全红 / 从未运行 | ruff 621 errors、pytest 1 failed | CI 接上远端并转绿 |
| **P0-6** | v3 主路径零覆盖 | 5 个核心模块 0% | 补默认引擎冒烟测试 |
| **P0-7** | Web GUI 无边界暴露 | 跨源实测打通 `/api/stop` | 改 `127.0.0.1` + 去 `ACAO:*`（若发 GUI） |

---

## ✅ 行动清单

| # | 行动 | 紧急度 | 预计成本 | 验收标准 |
|---|------|--------|---------|---------|
| 1 | **去 Tavily 后台吊销现有 key**，改环境变量读取；`.gitignore` 加 `*.key`/`.env`/`.coverage.*`/`*.zip`（注释独立成行）；新建 `.dockerignore` | **P0 · 立即** | 15 分钟 | `git check-ignore tavily.key` 返回已忽略 |
| 2 | `pyproject.toml:3` 改 `setuptools.build_meta`，补 `[tool.setuptools.packages.find] include=["novel_generator*"]` 与 package-data 词库 | **P0** | 20 分钟 | `pip install .` 成功 + wheel 内含 `word_banks/*.json` |
| 3 | 清理 62MB 垃圾（字体去重留一份、删 `_dbg*`/`_probe*`/`engine.py.bak`/zip）后，`git add` 6 个 engine 模块 + tools/ + GUI，提交出可运行基线 | **P0** | 1 小时 | 全新克隆后 `python main.py` 跑通 |
| 4 | 修 `SceneDirector` resume 三处：①`:281-285` 恢复时载入已有正文再续写（消除"两个真相源"）②`:1113` 段数改为累计而非 `len(buffer)` ③`:1110` 页眉字数/段数取同一来源；加 `--reset-state` 与写前 `.bak`；补 **多次连续 resume** 回归测试。**一并梳理 `plot_state.json` 的写权限**——`--polish` 目前会静默改写它（🟠#16） | **P0** | 4–5 小时 | 50% 中断后 resume，最终字数=页眉字数；**连续 resume 两次结果仍正确**；跑过 `--polish` 后 resume 不受影响 |
| 5 | 修 `test_deal.py:410`（改 `dealt/deck_size` 阈值或参数化多种子）；`ruff --fix` 清理 621 项，剩余加 per-file-ignores；接上远端仓库让 CI 真跑 | **P0** | 3–4 小时 | CI 绿灯，非 `\|\| true` 伪绿 |
| 6 | GUI `HOST` 改 `127.0.0.1`、删 `ACAO:*`、`target` 上限 20 万字；`/api/stop` 加 CSRF token | **P0**（发 GUI 时） | 30 分钟 | 跨源请求被拒 |
| 7 | 补 `[project.dependencies]`（flask>=3.0, waitress>=3.0）与 `[gui]` extras（PyQt5）；**改掉 README:12「纯标准库零外部依赖」** | **P1** | 30 分钟 | 干净环境按 README 装完 GUI 可启动 |
| 8 | 修模板槽位 `{line}`→`{pov}` 错填（`_gen_pov_banks.py:123,125`）；治理 34% 正文重复率 | **P1** | 半天+ | 重复率降至 15% 以下 |
| 9 | 统一版本号为单一来源；`--diagnose` 移出 `mode=='words'` 分支 | **P1** | 30 分钟 | 三处版本一致 |
| 9b | 删掉 `causal_main.py:68` 的 `--api-key` 用法串（**不要改成注册该参数**——CLI 传密钥属 CWE-214 反模式，见 🟢#32；未来接线走环境变量/配置文件）；对 `--polish`/`--interactive` 二选一：补测 or 在 v2.1.0 下线 | **P1** | 1 小时 | 文档所示命令可直接跑通，无 `unrecognized arguments`；密钥不经 CLI 传递 |
| 10 | 手工清理 QA 残留：`tmp/qa_out/`、`tmp/qa_probe_deal.py` | P2 | 1 分钟 | 目录干净 |

---

## 8. 🔄 回滚预案

> ### 🚨 撤回一条有害建议（本报告初版曾给出，请勿采用）
>
> 初版写的是：`回退 git checkout <tag> -- novel_generator/ main.py pyproject.toml`。
> **这条错了，且危险**：
> - `git checkout` 对 **untracked 文件无效**——25 个核心模块根本不在版本控制里，回滚命令碰不到它们
> - 更糟的是，若有人配套执行 `git clean -fd`，会**永久删除** `scene_director.py` 等 **2534 行无任何备份的核心代码**（无 git 副本、无远端副本，仓库连 remote 都没有）
>
> QA 在补遗中主动纠正了自己给出的这条建议。以下是更正后的版本。

1. **先建立基线，再谈回滚**：当前状态下**不存在任何可回滚基线**，谈回滚是空谈。
   - 第一步：把 25 个 untracked 文件 `git add` 并提交（即 🔴#3）
   - 第二步：提交后打 `v2.1.0` tag，回滚才有意义
   - **在此之前严禁**：`git clean -fd`、`git stash -u`、`git reset --hard` —— 前两个会带走未跟踪的核心代码
2. **state 文件损坏**（P0-4 高发）：`spec/tracking/plot_state.json` 是未跟踪的运行时产物，**直接删除即可全新开始**。建议发布版加 `--reset-state` 与写前自动 `.bak`。
3. **输出污染**：产物带时间戳不覆盖，但 resume 会产出「文件名说 2 万字、实际 1 万字」的伪成品，用户难以辨别。**P0-4 修复前，README 应显著标注禁用 `--resume`。**
4. **安装回滚**：`pip uninstall novel-generator`。因 P0-2 从未成功发过包，无存量污染。

---

## 🔬 证据等级说明（采信时请区分）

本报告的发现分两类取证等级，**不要混为一谈**：

| 等级 | 范围 | 说明 |
|------|------|------|
| **执行实证** | 🔴#1~#7、🟠#8~#16、🟢#27~#31、全部安全发现（F-01~F-10）、覆盖率与测试数据、端到端冒烟、🟡#25 | 均附真实命令输出/实机复现。含双 Python 版本测试、跨源 HTTP 实测、模拟提交实证、socket/env 探针注入 |
| **源码实证** | 🔬 专项中 `:1113` 状态腐蚀（静态复核预测）、🟡#26 可达路径判定（Grep 追踪） | 逻辑链完整但**未取执行输出**，建议修复时顺带验证 |

### ⚠️ 过程中的一次工具故障（已界定影响半径）

审计中途，两位成员的 **Bash/PowerShell 输出捕获同时静默失效**——连 `echo "test"` 都返回空。安全官定位了这个坑的真正危险之处：

> **他把"空输出"误当成了"grep 零命中"**，据此得出 `llm_rewrite.py` 是「零引用死代码」的错误结论。命令形如 `echo "标题" && grep ... && echo "[done]"`，返回结果里**连标题都没打印**——真·零命中的话标题必然出现。这个矛盾当时没被察觉。

QA 用 Grep 工具复核后推翻了该结论，安全官复核确认并**主动撤回**，同时给出了修正后的更强论据（见「已核实无风险」章节）。

**处置**：
- 影响半径已界定——故障仅发生在安全官最后两条命令；此前所有命令的 echo 标题均正常打印，输出真实
- 那两条命令涉及的**每一条否定性结论均已用 Grep 工具重跑**：`openai/anthropic/requests/httpx` 导入、`urlopen/socket/smtplib`、`eval/exec/pickle/subprocess`、`api_key/Bearer` → **F-01~F-09 全部维持原判，无一条改动**
- 有效绕法：改用 Grep 工具，或将输出重定向到 `C:\tmp\*.txt` 再读取

> **给未来的教训**：工具静默失败 ≠ 否定性证据。任何"我搜了没找到"的结论，都应当有一个能证明命令真的跑过的锚点（如哨兵字符串）。这次是同伴交叉复核兜住了。

---

## ⚠️ 待完善 / 已知局限

- **审查基线是工作区未提交状态**（87 项变更），非 HEAD。若你决定放弃 v3 重写、以 HEAD 发布，本报告 🔴#3 / #6 及部分 🟠 项需重新评估——HEAD 实测是可跑通的。
- **未验证项**：GUI 图形界面未真跑（无头环境，仅做导入检查，3.14 下 `gui_qt.py`/`gui_tk.py` 导入均通过）；Docker 构建未测；Linux/macOS 未测，全部结论仅覆盖 Windows。
- **正文重复率 34%** 只做了 3 个种子的统计，样本偏小，但三次结果高度一致（28.8/34.1/34.9），趋势可信。
- 环境卫生：安全审计在 `C:\tmp\_secdeps` 装依赖做实证，未污染项目；实测 `--polish` 导致 `spec/tracking/plot_state.json` 被改写，**已从备份还原并哈希校验**（`RESTORED_HASH=4189E365…`、`MATCHES_PRE=True`）。QA 已还原 `output/` 与 `pyproject.toml`（diff 校验字节一致），残留 `tmp/qa_out/`、`tmp/qa_probe_deal.py` 待手工清理。
- **本报告经历 3 轮交叉修订**：QA 补运行数据 → 代码审查回头源码复核（发现 `:1113` 状态腐蚀）→ QA 推翻安全侧误判 → 安全侧撤回并升级为运行时实证。期间发生一次工具静默故障并被同伴兜住（详见证据等级章节）。结论始终稳定在 🔴 No-Go / 7 项阻塞。

---

## 📚 成员产出索引

- **gstack-product-reviewer（产品官）** — 代码审查，7 项阻塞 + 最小放行路径，含模拟提交实证目录 `C:\Users\13122\_revtmp\simcommit`
- **gstack-security-officer（安全卫士）** — OWASP+STRIDE 审计，F-01~F-09 共 9 项发现 + 7 项已核实无风险清单
- **gstack-qa-lead（质量门神）** — 双 Python 版本测试、覆盖率、端到端冒烟、安装验证、回滚预案，B1~B3 阻塞项

---

> 本报告由软件工坊 AI 协作生成，三位成员均独立取证、结论交叉印证。关键决策请由工程负责人复核。
