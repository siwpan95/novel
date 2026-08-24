# 词库自定义指南

项目核心价值之一是**词库驱动**——16 个 JSON 词库提供角色外貌、场景描写、对话语气等多维度随机化能力。本文档说明如何扩展和自定义词库。

## 词库文件结构

所有词库存放在 `novel_generator/word_banks/` 目录，JSON 格式：

```json
{
  "key_1": ["选项A", "选项B", "选项C"],
  "key_2": [
    "选项1",
    "选项2"
  ],
  "_meta": {
    "description": "词库说明（可选）"
  }
}
```

## 现有词库一览

| 文件 | 用途 | 条目数 |
|------|------|:---:|
| `adjectives.json` | 外貌/场景/品质/尺寸形容词 | ~200 |
| `body_parts.json` | 24 个身体部位描写短语 | ~50 |
| `names.json` | 姓氏 + 名字用字 | ~300 |
| `locations.json` | 地形/地标/场景描写 | ~80 |
| `equipment.json` | 兵器/武功/魔法/法宝名称 | ~100 |
| `personality_tags.json` | 性格标签系统 | ~60 |
| `world/senses/world_senses_ambient.json` + `world_senses_battle.json` | 世界五感（环境/战场），合并为 `world_senses` | 611+ |
| `cultivation_terms.json` | 东方修仙术语 | ~80 |
| `wuxia_terms.json` | 武侠术语 | ~60 |
| `scifi_terms.json` | 科幻术语 | ~60 |
| `cyberpunk_terms.json` | 赛博朋克术语 | ~50 |
| `cthulhu_terms.json` | 克苏鲁深渊术语 | ~40 |
| `post_apocalyptic_terms.json` | 末日废土术语 | ~50 |
| `wanjie_context.json` | 万界归墟世界观专用词库 | ~100 |
| `hook_templates.json` | 章末钩子模板（悬念/爽点预告/关系三类型） | 30 |

## 如何添加新条目

### 1. 扩展现有词库

编辑对应的 JSON 文件，在数组中添加新条目：

```json
{
  "兵器": ["青冥剑", "紫电刀", "破风枪", "你新加的兵器名"]
}
```

**注意**：JSON 文件必须是有效的 UTF-8 编码。格式错误会导致词库加载失败。

### 2. 创建新词库

1. 在 `novel_generator/word_banks/` 下创建新的 `.json` 文件
2. 使用标准词库结构（key → array of strings）
3. 在 `novel_generator/engine/word_bank.py` 的 `WORD_BANK_DIR` 中确认路径设置正确

### 3. 在代码中使用新词库

```python
from novel_generator.engine.word_bank import WordBank

wb = WordBank(seed=42)

# 随机选取一条
item = wb.pick('your_bank_name', 'your_key')
print(item)

# 获取多条
items = wb.pick_multi('your_bank_name', 'your_key', count=3)
```

## 词库与引擎的绑定方式

### ASP 模板流（引擎 1）

词库通过模板占位符绑定。在 `generators/chapter.py`、`generators/battle.py` 中：

```python
# 模板中使用 [bank_name.key] 引用词库
template = "他手持[equipment.兵器]，步入了[locations.地标]。"
```

`TemplateEngine` 负责解析这些占位符并从词库随机选取。

### 融合引擎（引擎 2 + ASP）

`VoiceEngine` 通过 `render_*()` 方法绑定词库。添加新世界或新术语时，需要在 `voice_engine.py` 的对应渲染方法中引用新词库的 key。

### 世界五感签名

`world_senses` 是特殊合并词库——由 `world/senses/world_senses_ambient.json`（环境五感 `worlds`）与 `world_senses_battle.json`（战场地形 `battlefields`）合并而成，引擎经 `WordBank.load_world_senses()` 取回。每个世界包含五感描写短语：

```json
{
  "东方修仙": {
    "视觉": ["仙气缭绕", "符文闪烁", ...],
    "听觉": ["钟声悠远", "剑鸣清越", ...],
    ...
  }
}
```

添加新世界时，需要在此文件中定义对应的五感签名，然后在 `voice_engine.py` 的 `_sense()` 方法中注册新世界。

## 最佳实践

1. **随机种子固定** — 调试时使用固定 seed (`WordBank(seed=42)`)，确保输出可复现
2. **条目数量平衡** — 每个 key 至少 5 个候选项，避免重复明显
3. **不重复原则** — 同一 key 下的条目语义不要过于相似
4. **验证 JSON** — 修改后运行 `python -c "import json; json.load(open('word_banks/xxx.json'))"` 确认格式正确
5. **编码** — 确保使用 UTF-8 编码保存文件

## 故障排查

| 症状 | 原因 | 解决方案 |
|------|------|---------|
| 所有输出相同 | seed 固定 + 词库条目太少 | 增加词库条目或更换 seed |
| 加载词库失败 | JSON 格式错误 | 用 JSON 验证器检查 |
| 某些 key 无输出 | key 名称拼写错误或不存在 | 检查代码中的 key 引用是否匹配 JSON |

---

> 更多细节见 `novel_generator/ARCHITECTURE.md` 和 `spec/Research-Report-Enhancement-Plan.md`。
