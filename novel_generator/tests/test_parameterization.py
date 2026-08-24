# -*- coding: utf-8 -*-
"""参数化回归测试 — 锁定「硬编码叙事全部外置到 JSON 词库」这一承诺。

覆盖：
1. beat_orchestrator 中每个 self._t('key', ...) 调用都必须有对应的 JSON 变体池
   （证明是数据驱动，而非仅靠硬编码 fallback）；
2. BeatOrchestrator._t() 的 round-robin 选择不会塌缩为单一变体（修复跨章逐字重复）；
3. 6 个新增叙事词库均为合法 JSON 且含预期顶层键。
"""
import json
import os
import re
import types

import pytest

from novel_generator.engine.beat_orchestrator import BeatOrchestrator
from novel_generator.engine.beat_narratives import BeatNarrativeLoader
from novel_generator.engine.word_bank import resolve_bank_path

NARR_PATH = resolve_bank_path('beat_narratives')


def _load_json(name):
    with open(resolve_bank_path(name), encoding='utf-8') as f:
        return json.load(f)


def _make_orchestrator():
    # _t() 只依赖 self._narrative / self._text_idx，voice 仅占位
    fake_voice = types.SimpleNamespace()
    return BeatOrchestrator(fake_voice)


def _collect_t_keys():
    """从 beat_orchestrator.py 源码提取所有 self._t('key', ...) 的字面 key。"""
    src_path = os.path.join(os.path.dirname(__file__), '..', 'engine', 'beat_orchestrator.py')
    with open(src_path, encoding='utf-8') as f:
        src = f.read()
    keys = []
    for m in re.finditer(r"self\._t\(\s*['\"]([^'\"]+)['\"]", src):
        literal = m.group(1)
        # 与 _t() 内部逻辑一致：未以 _ 开头的 key 会自动加前缀
        json_key = literal if literal.startswith('_') else '_' + literal
        keys.append(json_key)
    return keys


def _collect_tf_keys():
    """提取所有 self._tf('key', ...) 的字面 key（f-string 模板路径）。"""
    src_path = os.path.join(os.path.dirname(__file__), '..', 'engine', 'beat_orchestrator.py')
    with open(src_path, encoding='utf-8') as f:
        src = f.read()
    keys = []
    for m in re.finditer(r"self\._tf\(\s*['\"]([^'\"]+)['\"]", src):
        literal = m.group(1)
        json_key = literal if literal.startswith('_') else '_' + literal
        keys.append(json_key)
    return keys


def test_every_t_call_backed_by_json_variant():
    """每个 self._t() 调用都必须有非空的 JSON 变体池（真·参数化，不只靠 fallback）。"""
    narrative = _load_json('beat_narratives.json')
    keys = _collect_t_keys()
    assert keys, "beat_orchestrator.py 中应当存在 self._t() 调用"
    missing = [k for k in keys if not narrative.get(k)]
    assert not missing, f"以下 key 在 beat_narratives.json 中缺失或为空：{missing}"


def test_every_tf_call_backed_by_json_template():
    """每个 self._tf() 调用都必须有对应的 JSON 模板（f-string 已外置，非仅靠 fallback）。"""
    narrative = _load_json('beat_narratives.json')
    keys = _collect_tf_keys()
    assert keys, "beat_orchestrator.py 中应当存在 self._tf() 调用"
    missing = [k for k in keys if not narrative.get(k)]
    assert not missing, f"以下 _tf key 在 beat_narratives.json 中缺失或为空：{missing}"


def test_tf_formats_placeholders():
    """_tf() 必须正确填充 {sub}/{world}/{pct} 占位符。"""
    orch = _make_orchestrator()
    # 选一个含占位符的模板 key（来自 _fwrap 生成的 _t 系列模板）
    narrative = _load_json('beat_narratives.json')
    tf_keys = _collect_tf_keys()
    sample = tf_keys[0]
    tpl = narrative[sample][0]
    out = orch._tf(sample, tpl, sub=12, world='归墟', pct=9)
    assert '{sub}' not in out and '{world}' not in out and '{pct}' not in out
    # 占位符应被实际值替换
    assert '12' in out or '归墟' in out or '9' in out


def test_t_round_robin_no_collapse():
    """同一节拍跨章复用时，_t() 应轮询遍历所有变体，而非塌缩为单一值。"""
    narrative = _load_json('beat_narratives.json')
    multi_keys = [k for k, v in narrative.items() if isinstance(v, list) and len(v) > 1]
    assert multi_keys, "beat_narratives.json 应存在多变体 key 用于验证 round-robin"

    for key in multi_keys:
        orch = _make_orchestrator()
        variants = narrative[key]
        # 调用次数 >= 变体数，足以覆盖一轮完整轮询
        out = [orch._t(key, 'FALLBACK') for _ in range(len(variants))]
        assert len(set(out)) == len(variants), (
            f"key={key}: 期望轮询覆盖全部 {len(variants)} 个变体，"
            f"实际仅出现 {len(set(out))} 个不同值（已塌缩）"
        )
        # 首次调用固定取变体[0]，与原硬编码逐字一致
        assert out[0] == variants[0]


def test_narrative_loader_get_all_round_robin():
    """BeatNarrativeLoader.get_all 配合 _t 的轮询一致性。"""
    loader = BeatNarrativeLoader()
    key = '_beat_opening'
    variants = loader.get_all(key)
    assert variants, f"{key} 应至少有一项变体"
    orch = _make_orchestrator()
    first = orch._t(key, 'FB')
    assert first == variants[0]


@pytest.mark.parametrize("bank,expected_keys", [
    ('world_openings.json', None),       # 8 个世界，键为世界名
    ('truth_reveals.json', None),        # 层 2..6
    ('player_chaos.json', {'player_names', 'chaos_templates'}),
    ('voice_helpers_body_reaction.json', {'body_reaction'}),
    ('voice_helpers_body_parts.json', {'body_parts'}),
    ('voice_helpers_sensations.json', {'sensations'}),
    ('voice_helpers_sense_fallbacks.json', {'sense_fallbacks'}),
    ('quality_fragments.json', {
        'short_patterns', 'single_char_lines', 'long_sentence_connectors',
        'incomplete_sentence_templates', 'self_correction_templates',
        'physical_sensations', 'sense_fragments',
    }),
    ('chapter_enrichments.json', {'default'}),
])
def test_narrative_banks_valid(bank, expected_keys):
    """6 个新增词库均为合法 JSON，且含预期顶层键。"""
    data = _load_json(bank)
    assert isinstance(data, dict)
    if expected_keys is not None:
        assert expected_keys.issubset(set(data.keys())), (
            f"{bank} 缺少预期顶层键：{expected_keys - set(data.keys())}"
        )


def test_chapter_enrichments_format_placeholders():
    """chapter_enrichments 中的占位符能被正确 format（{world}/{sub}）。"""
    data = _load_json('chapter_enrichments.json')
    default = data['default']
    # default 含占位符，应能 format 而不抛错
    formatted = default.format(world='归墟', sub=3)
    assert '{world}' not in formatted and '{sub}' not in formatted
