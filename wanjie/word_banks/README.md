# 内容库（Content Library）

双引擎小说生成器《万界归墟》的全部**数据驱动素材**集中于此目录。所有可被随机选取、
洗牌发牌（见 `engine/dealer.py` 的发牌员三层增强）、轮询去重的叙事/词汇/术语/世界观
素材，都以外置 JSON 形式放在这里——引擎代码只做"编排"，不做"硬编码文本"。

> 设计承诺：任何叙事/描写文本都应在本库里找到对应变体池，而非写死在 `engine/*.py`。
> `tests/test_parameterization.py` 持续锁定这一承诺。

---

## 目录结构（5 大分类）

```
word_banks/
├── vocab/          词汇：形容词 / 身体部位 / 兵器装备 / 地貌地点 / 姓名用字
├── genre_terms/    题材术语：修仙 / 武侠 / 科幻 / 赛博朋克 / 末日废土 / 克苏鲁
├── narrative/      叙事：节拍叙事 / 场景节拍 / 章节润色 / 伏笔 / 钩子 / 真相揭示 / 玩家乱入 / 高质量片段
├── world/          世界观：归墟设定 / 各世界开篇 / 各世界场景地点
│   └── senses/     世界五感拆分：world_senses_ambient（环境五感 worlds）/ world_senses_battle（战场地形 battlefields）
├── voice/          声音·性格：性格标签 / 性格声音
│   └── voice_helpers_*.json   体感五感辅助拆分：body_reaction / body_parts / sensations / sense_fallbacks
├── content_manifest.json   自动生成的清单（条目数统计）
└── build_manifest.py       清单生成器（可重跑）
```

各分类条目数见 `content_manifest.json` 的 `summary`（当前合计约 2.1 万条）。

> **特殊合并词库**：`world_senses` 与 `voice_helpers` 体量较大，已升格拆为子文件，
> 引擎不再直接 `load('world_senses')` / `load('voice_helpers')`，而是通过
> `WordBank.load_world_senses()` / `load_voice_helpers()` 合并取回与旧结构兼容的字典。
> 详见 `engine/word_bank.py`。

---

## 加载机制

`engine/word_bank.py` 的 `WordBank` 通过 `resolve_bank_path(bank_name)` 解析路径：

1. 优先取扁平路径 `word_banks/<bank_name>.json`（向后兼容）；
2. 若不存在，递归搜索 `word_banks/` 下首个同名文件（即本分类子目录结构）。

因此**新增/移动词库到任意子目录都能被自动发现**，引擎无需改代码。

---

## Schema 约定

每个 JSON 文件是一组"键 → 内容"的映射，值分三类：

| 形态 | 说明 | 示例 |
|---|---|---|
| `键 → 字符串列表` | 最常见。列表项即随机抽取的变体/术语/片段 | `adjectives.json` 的 `appearance` |
| `键 → 字典` | 嵌套分组，内部再是列表 | `scene_locations.json`（世界名→地点列表）、`voice_helpers_body_reaction.json`（情绪→描写） |
| `description` 元信息 | 单个字符串，描述本库用途；**必须保持为字符串** | 各题材术语库 |

规则：
- **保留所有现有顶层键名与值类型**，扩充时只往列表里追加条目。
- 列表内**不得有完全重复条目**（去重）。
- 含 `{world}` / `{sub}` / `{pct}` 等占位符的模板句，追加新模板时**必须保留占位符**。
- 内容须为中文、虚构/题材向、不涉政敏。

---

## 如何新增一个词库

1. 在合适的分类子目录下新建 `<name>.json`，形如 `{"description": "...", "key1": [...], ...}`。
2. 引擎侧用 `WordBank.load("<name>")` / `pick("<name>", "key1")` 消费即可，无需改加载器。
3. 若需为某引擎模块提供固定文件名引用，用 `from wanjie.engine.word_bank import resolve_bank_path`
   取路径（不要写死子目录）。

## 如何扩充一个词库

1. 读现有文件，搞清 schema。
2. 追加新条目（联网搜真实题材术语 + 创作均可），保持去重与占位符。
3. 写回后用 UTF-8、中文直读（`ensure_ascii=False`）保存。
4. 校验：`python -c "import json; json.load(open('路径', encoding='utf-8')); print('OK')"`。

## 重新生成清单

```bash
python wanjie/word_banks/build_manifest.py
```

会刷新 `content_manifest.json`（自动排除自身，可重复运行）。

---

## 硬约束

本库遵循项目四条硬约束：**确定性 / 零依赖 / 可复现 / 速度**。
- 池大小只影响多样性，不影响随机选取的确定性（同 seed 同输出）。
- 纯 JSON + 标准库，无第三方依赖。
