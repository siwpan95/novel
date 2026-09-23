# 每日自动化流水线配置（待应用）

> 目标：把「词库扩充 + 模板挖掘 + 批量拆槽」三条流水线并入每日调度。
> 当前宿主侧 `automation_update` 工具在本会话不可用（宿主自动化存在 SQLite，不可直接改），
> 故先把最终配置固化在此，待工具可用时按此一键更新 `automation-1786318733060`。

## 更新后的 prompt（覆盖原 prompt）

> 下列命令的工作目录为仓库内的 `novel_generator/`（即下方 `cwds`），解释器用 PATH 中的 `python`；
> 脚本根目录由脚本自身位置推导（`Path(__file__).parents[2]`），无需再传绝对路径。

```
你是「万界归墟·棋盘生成器」的每日联网维护调度器，负责词库与模板库两条流水线。按顺序执行并输出中文简报：

## 1. 词库扩充（量）
python tools/wordbank_expand/expand_engine.py --cap=200 --results=12
引擎内置：Tavily 联网检索真实语料 → 按各库 schema 安全追加 → 去重 → 旋转词污染护栏 → 原子写（写前 json.load 校验）→ 滚动健康校验 → 追加写 docs/wordbank_growth_log.md。

## 2. 模板挖掘（骨架）
python tools/wordbank_expand/template_miner.py --results=8
联网搜网文写作公式 → 种子模板骨架落盘 word_banks/templates/*.json；联网捞到的原始候选存 _mined_raw.json（供 LLM 二次拆槽，不混入槽位模板）。

## 3. 批量拆槽落盘（幂等）
python tools/wordbank_expand/curate_templates.py
把人工提炼的带 {slot} 槽位模板并入 templates/ 词库（去重、幂等，可每日重复跑）。

## 汇报（中文简报）
- 词库：处理库数 / 检索失败数 / 总新增条目 / 体积变化 / 健康校验结论（去重异常·旋转词污染）。
- 模板库：battle_action/battle_reaction/battle_effect/scene_frame/character_intro/emotion_beat/dialogue_exchange 各文件条数。
- 若 Tavily 连接超时（WinError 10060），跳过并在简报标注，次日自动重试。

## 护栏（勿越界）
- 三条流水线都只追加、不删库、不改生成器/池代码、不重置任何基线或校验哈希。
- 密钥在 tools/wordbank_expand/tavily.key，切勿写入本 prompt 或提交仓库。
```

## 更新字段
- automation_id：`automation-1786318733060`
- name：`词库扩充+模板挖掘（每日 · 双流水线）`
- prompt：如上
- status / rrule / cwds 保持不变（rrule 当前为 `FREQ=HOURLY;INTERVAL=1`，若无需如此频繁可改回 `FREQ=DAILY;BYHOUR=3;BYMINUTE=0`；cwds=`<仓库根>\novel_generator`，即上面命令的工作目录）。

## 流水线脚本清单（均已就位）
| 脚本 | 职责 |
|---|---|
| `tools/wordbank_expand/expand_engine.py` | 词库每日联网扩充（量） |
| `tools/wordbank_expand/template_miner.py` | 模板挖掘：种子骨架 + 联网捞候选（骨架） |
| `tools/wordbank_expand/curate_templates.py` | 批量拆槽：人工提炼模板并入词库（幂等） |
| `tools/wordbank_expand/tavily_search.py` + `tavily.key` | Tavily 检索助手 + 密钥 |
