# WordCountDirector：字数目标驱动循环

> 替代现有「章/卷循环」。目标不再是「写 N 章」，而是「长到 target_chars 字」。

## 1. 循环骨架

```python
def generate(self, target_chars, *, seed=None, resume=False):
    total = 0
    if resume:
        total = self.plot_state.state.get('current_chars', 0)
    buffer = []
    passage_no = self.plot_state.state.get('current_passage', 0)

    while total < target_chars:
        ctx = self._build_ctx(passage_no, resume)
        state = self._read_state(total, target_chars)
        spec = self.orchestrator.plan(ctx, state)        # 状态驱动采样
        lines = self.renderer.render(spec, ctx)          # 复用渲染管线
        text = '\n'.join(lines)
        n = len(text)

        # Passage 过薄保护：低于 min_passage_chars 时由 orchestrator 补一组 op
        if n < self.config.min_passage_chars:
            spec = self.orchestrator.plan(ctx, state, extra=True)
            text = '\n'.join(self.renderer.render(spec, ctx))
            n = len(text)

        # 字数封顶保护：单段不得超过 max_passage_chars（避免一段撑成半本书）
        # 超长则截断并标记续写，下一轮接着 state 继续
        total += n
        buffer.append(text)
        passage_no += 1

        # 持久化断点（每 K 段存一次，避免每轮 IO）
        if passage_no % self.config.save_every == 0:
            self.plot_state.state['current_chars'] = total
            self.plot_state.state['current_passage'] = passage_no
            self.plot_state.save()

    # 收尾：最后一段强制注入 hook（追读率命门），写文件
    return self._finalize(buffer, total)
```

## 2. 终止条件

- **主终止**：`total >= target_chars`。
- **安全终止**：`max_passages` 上限（防死循环，默认 `target_chars / min_passage_chars * 3`）。
- **resume**：从 `plot_state.current_chars / current_passage` 续写，不重生成已写部分。

## 3. 「章/卷」语义的取消

- 不再有「第 N 章 / 第 N 卷」标题。
- 输出分段策略（可选，由 Config 控制）：
  - `mode='natural'`：完全按 Passage 自然空行分段；
  - `mode='soft_milestone'`：每达到 target_chars 的某个比例（如 25%/50%/75%）插入一个 scene-break 分隔符（不是卷标题）。
- `volume` 若保留，仅作为**元数据标签**（如输出文件名 `万界归墟_第2卷_...txt`），不参与生成逻辑。

## 4. 进度可观测性

- 每 `log_every` 段打印：`第{passage_no}段 | {n}字 | 累计{total:,}/{target:,} | phase={phase} | pending_foreshadowing={k}`。
- 复用 `test_deal.py` 思路：可选打印每个 `queue_key` 发牌状态，证明无放回跨段生效。

## 5. 与旧 `_inject_quota` 的关系

旧 `_inject_quota` 的「配额 × 状态调制」逻辑**不删除**，而是被 `EmergentOrchestrator.plan` 吸收：
- `_QUOTA[beat]` → 退化为 `base_quota`（不分 beat，按 passage_type 给默认值）；
- `pace_hint / description_density / dialogue_ratio / prev_beat_tension` 的状态调制 → 改写为「读 NarrativeState」的增益/惩罚。
