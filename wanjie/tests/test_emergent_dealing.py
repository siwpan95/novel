"""EmergentOrchestrator 发牌员均匀发牌测试 —— 验证「完全由发牌员随机发牌」。

重点：
1. Dealer 无放回：单周期（包容量）内零重复；发完重洗、牌堆被真实消耗。
2. Dealer 跨包接缝防涝：任意相邻两次发牌不相同（pool>1 时）。
3. Dealer 确定性：同 seed 同输出。
4. 段落类型均匀发牌：300 次发牌 = 50 个完整包，各类型精确 50 次（bag 不变量）。
5. plan() 返回合法 PassageSpec，算子类型均来自均匀池、无未知类型。
6. 世界发牌：跨段落无紧邻重复。
"""
import random
from collections import Counter

from wanjie.engine.dealer import Dealer
from wanjie.engine.emergent_orchestrator import EmergentOrchestrator, OP_TYPE_POOL
from wanjie.engine.narrative_state import NarrativeState, PASSAGE_TYPES


def _make_orch(config_overrides: dict = None) -> EmergentOrchestrator:
    """构造一个最小 EmergentOrchestrator（无需真实 VoiceEngine）。"""
    from wanjie.engine.wordcount_director import DEFAULT_WC_CONFIG

    cfg = dict(DEFAULT_WC_CONFIG)
    if config_overrides:
        cfg.update(config_overrides)

    class _MockVoice:
        pass

    return EmergentOrchestrator(_MockVoice(), cfg, rng=random.Random(42))


def _state(**kw) -> NarrativeState:
    defaults = {
        'total_chars': 5000,
        'target_chars': 20000,
        'tension': 3,
        'pending_foreshadowing': 0,
        'arc_progress': 0.0,
        'recent_passage_types': [],
        'chars_present': ['林朔', '唐川'],
    }
    defaults.update(kw)
    return NarrativeState(**defaults)


# ---------------------------------------------------------------------------
# Dealer 不变量
# ---------------------------------------------------------------------------
def test_dealer_without_replacement():
    d = Dealer(seed=1)
    pool = ['a', 'b', 'c', 'd', 'e']
    seq = [d.deal('q', pool) for _ in range(14)]
    # 每个周期（连续 5 张）内零重复
    for start in range(0, len(seq) - 5 + 1, 5):
        assert len(set(seq[start:start + 5])) == 5, f'周期内重复: {seq[start:start+5]}'
    # 14 次、容量 5 → 剩余 1（证明发完重洗、牌堆被真实消耗）
    assert len(d._queues['q']) == 1


def test_dealer_no_immediate_repeat_across_seam():
    d = Dealer(seed=7)
    pool = ['x', 'y', 'z']
    seq = [d.deal('s', pool) for _ in range(60)]
    for a, b in zip(seq, seq[1:]):
        assert a != b, f'跨包紧邻重复: {a}|{b}'


def test_dealer_deterministic():
    pool = ['a', 'b', 'c', 'd', 'e']
    d1, d2 = Dealer(seed=42), Dealer(seed=42)
    assert [d1.deal('q', pool) for _ in range(25)] == [d2.deal('q', pool) for _ in range(25)]


def test_dealer_deal_many():
    d = Dealer(seed=3)
    pool = ['a', 'b', 'c']
    out = d.deal('m', pool, take=9)  # 3 个完整包
    assert len(out) == 9
    for i in range(0, 9, 3):
        assert len(set(out[i:i + 3])) == 3, f'deal_many 周期内重复: {out[i:i+3]}'


# ---------------------------------------------------------------------------
# 编排器：完全随机发牌
# ---------------------------------------------------------------------------
def test_passage_types_uniform_exact():
    """段落类型由 Dealer 无放回发牌：300 次 = 50 包，各类型精确 50 次。"""
    orch = _make_orch()
    counter = Counter(orch._deal_passage_type() for _ in range(300))
    assert set(counter.keys()) == set(PASSAGE_TYPES), f'类型集合异常: {counter}'
    assert all(c == 50 for c in counter.values()), f'应精确均匀(各50): {dict(counter)}'


def test_plan_returns_valid_spec():
    orch = _make_orch()
    state = _state()
    ctx = type('ctx', (), {'world_name': '归墟', 'sub_index': 1, 'total_in_beat': 1})()
    spec = orch.plan(ctx, state)
    assert spec.passage_type in PASSAGE_TYPES
    assert len(spec.ops) >= 2, f'算子数应 >= 2: {len(spec.ops)}'
    assert spec.weight_trace, '应包含发牌轨迹'


def test_plan_op_types_all_from_uniform_pool():
    orch = _make_orch()
    state = _state()
    ctx = type('ctx', (), {'world_name': '归墟', 'sub_index': 1, 'total_in_beat': 1})()
    seen = set()
    for _ in range(80):
        for op in orch.plan(ctx, state).ops:
            seen.add(op.op_type)
    from wanjie.engine.beat_orchestrator import OpType
    valid = {OpType.SCENE, OpType.ACTION, OpType.BATTLE, OpType.DIALOGUE, OpType.REVEAL}
    assert seen == valid, f'算子类型集合应为均匀池: {seen}'


def test_world_deal_no_immediate_repeat():
    orch = _make_orch()
    ctx = type('ctx', (), {'world_name': '归墟'})()
    seq = [orch._pick_world(ctx) for _ in range(40)]
    for a, b in zip(seq, seq[1:]):
        assert a != b, f'世界紧邻重复: {a}|{b}'
