# 配置项 Schema（Config）

> 字数目标生成的所有可调参数集中在此，避免散落硬编码。

```json
{
  "target_chars": 200000,
  "min_passage_chars": 200,
  "max_passage_chars": 700,
  "max_passages": null,
  "save_every": 10,
  "log_every": 5,
  "segment_mode": "natural",
  "soft_milestones": [0.25, 0.5, 0.75],

  "phase_boundaries": {
    "establish_end": 0.30,
    "escalate_end": 0.75
  },

  "weights": {
    "phase": {
      "establish":  { "scene": 1.4, "dialogue": 1.3, "action": 0.9, "battle": 0.4, "reveal": 0.5, "hook": 0.6 },
      "escalate":   { "scene": 1.0, "dialogue": 1.0, "action": 1.3, "battle": 1.4, "reveal": 1.0, "hook": 1.0 },
      "resolve":    { "scene": 1.1, "dialogue": 1.2, "action": 1.1, "battle": 1.0, "reveal": 1.6, "hook": 1.4 }
    },
    "state": {
      "tension_high": { "action": 1.3, "battle": 1.3 },
      "pending_foreshadowing": { "reveal": 1.5, "hook": 1.4 },
      "arc_progress_high": { "dialogue": 1.3 },
      "recent_repeat_penalty": 0.4
    },
    "base_quota": { "scene": 6, "action": 5, "battle": 0, "dialogue": 0, "reveal": 0, "hook": 0 }
  },

  "rng_seed": 42,
  "volume_label": null
}
```

## 字段说明

- `target_chars`：目标总字数（**取代原 `chapters=N`**）。
- `min/max_passage_chars`：单段字数区间；过薄补写、过长截断续写。
- `phase_boundaries`：软元弧阶段切换点（按 `total/target` 比例）。**仅概率微调，不指派 beat**。
- `weights.phase`：三阶段对各 passage 类型的权重（阶段只做乘法微调）。
- `weights.state`：叙事状态增益；`recent_repeat_penalty` 对近期重复类型的惩罚系数（抗清单式重复）。
- `weights.base_quota`：原 `_QUOTA[beat]` 退化后的中性默认值。
- `volume_label`：可选元数据标签（仅用于输出文件名），不参与生成。
- `segment_mode` / `soft_milestones`：输出分段策略（见 `WordCount-Driver.md` §3）。

## 默认值建议

- 轻量演示：`target_chars=20000`，`max_passages` 不限制。
- 整书：`target_chars=200000`，约 400–1000 段。
