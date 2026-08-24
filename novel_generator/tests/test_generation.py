"""生成管线测试 —— 覆盖 P0 修复后的实际产出与重复检测。

重点：
1. TextQualityPipeline.check_repetition 能识别章节内逐字重复句，对干净文本返回 0。
2. 集成生成产出不再出现 P0 的占位重复句（「看了三遍」/「翻了翻之前的记录」）。
3. 生成的章节内，无 >=15 字的长句逐字重复超过 2 次（安全网 + 情绪池去重的回归保障）。
"""
import os

from novel_generator.unified_engine import UnifiedNovelEngine
from novel_generator.engine.text_quality import TextQualityPipeline


# ---------------------------------------------------------------------------
# 单元：重复检测
# ---------------------------------------------------------------------------
def test_check_repetition_detects_long_repeat():
    tp = TextQualityPipeline(seed=1)
    repeated = "林朔把同一行数据看了三遍，不是因为没看懂而是因为看懂了但不敢相信。"
    text = repeated * 3
    r = tp.check_repetition(text)
    assert r['max_count'] == 3, r
    assert r['penalty'] > 0, r


def test_check_repetition_clean_text():
    tp = TextQualityPipeline(seed=1)
    clean = "第一段完全不同的内容。第二段也是全新的。第三段依旧独特且彼此无关。"
    r = tp.check_repetition(clean)
    assert r['max_count'] == 0, r
    assert r['penalty'] == 0.0, r


def test_check_repetition_ignores_short_fragments():
    tp = TextQualityPipeline(seed=1)
    # 短句（<15字）即便重复也不计入
    text = "他愣住。他愣住。他愣住。"
    r = tp.check_repetition(text)
    assert r['max_count'] == 0, r


# ---------------------------------------------------------------------------
# 集成：真实生成产出质量（P0 回归）
# ---------------------------------------------------------------------------
def test_integrated_generation_no_placeholder_repeat(tmp_path):
    """integrated 模式生成 3 章，断言 P0 占位句已消失且无长句逐字重复。"""
    engine = UnifiedNovelEngine(seed=42, output_dir=str(tmp_path))
    # 把 PlotState 持久化重定向到临时目录，避免污染项目的 spec/tracking/plot_state.json
    engine.plot_state.save_path = str(tmp_path / 'plot_state.json')

    out_path = engine.generate(mode='integrated', chapters=3, skip_rubric=True)
    assert os.path.isfile(out_path)
    text = open(out_path, encoding='utf-8').read()

    # P0 回归：两条调试占位句不得再出现
    assert '看了三遍' not in text, 'P0 占位句「看了三遍」仍未清除'
    assert '翻了翻之前的记录' not in text, 'P0 占位句「翻了翻之前的记录」仍未清除'

    # 安全网 + 情绪池去重：章节内无 >=15 字长句逐字重复超过 2 次
    rep = engine.quality.check_repetition(text)
    assert rep['max_count'] <= 2, f"检测到逐字重复句: {rep['repeated'][:3]}"


# ---------------------------------------------------------------------------
# 单元：去AI腔（AI 连接词检测 / 清理）
# ---------------------------------------------------------------------------
def test_ai_tell_scrub():
    tp = TextQualityPipeline(seed=1)
    dirty = '首先，他推开门。其次，房间里没有人。最后，他意识到自己来晚了。'
    tells = tp.detect_ai_tells(dirty)
    assert ('首先', 1) in tells
    assert ('最后', 1) in tells
    clean = tp.scrub_ai_tells(dirty)
    assert '首先' not in clean and '其次' not in clean and '最后' not in clean
    # 正常叙事文本不应被检出 AI 腔
    assert tp.detect_ai_tells('他推开门，房间里没有人。他意识到自己来晚了。') == []


# ---------------------------------------------------------------------------
# 单元：章末钩子生成（研究驱动多类型 + 去重）
# ---------------------------------------------------------------------------
def _hook_pool():
    from novel_generator.engine.word_bank import resolve_bank_path
    import json
    data = json.loads(resolve_bank_path('hook_templates').read_text(encoding='utf-8'))
    pool = set()
    for v in data.values():
        if isinstance(v, list):
            pool.update(v)
    return data, pool


def test_render_hook_returns_pool_and_dedups():
    from novel_generator.engine.voice_engine import VoiceEngine
    from novel_generator.engine.narrative_context import NarrativeContext
    from novel_generator.engine.word_bank import WordBank
    from novel_generator.engine.plot_state import PlotState
    import tempfile
    tmp = tempfile.mkdtemp()
    ve = VoiceEngine(WordBank(seed=3), PlotState(save_path=tmp + '/ps.json'), seed=3)
    ctx = NarrativeContext()
    ctx.volume = 1
    ctx.beat = 'dark_night'      # 高张力节拍 → suspense 池（12 条）
    ctx.tension_level = 8

    _, pool = _hook_pool()
    data, _ = _hook_pool()
    data['suspense']
    picks = [ve.render_hook(ctx) for _ in range(24)]
    # 全部来自钩子池
    assert all(p in pool for p in picks), picks
    # 前 12 次（池大小）应全部不重复
    assert len(set(picks[:12])) == 12, picks[:12]
    # 24 次（池耗尽重置一次）单句最多出现 2 次
    from collections import Counter
    assert max(Counter(picks).values()) <= 2


def test_render_hook_context_type_selection():
    from novel_generator.engine.voice_engine import VoiceEngine
    from novel_generator.engine.narrative_context import NarrativeContext
    from novel_generator.engine.word_bank import WordBank
    from novel_generator.engine.plot_state import PlotState
    import tempfile
    tmp = tempfile.mkdtemp()
    ve = VoiceEngine(WordBank(seed=5), PlotState(save_path=tmp + '/ps.json'), seed=5)
    data, _ = _hook_pool()

    # 高张力危机节拍 → suspense
    c1 = NarrativeContext(); c1.volume = 1; c1.beat = 'dark_night'; c1.tension_level = 9
    assert ve.render_hook(c1) in data['suspense']

    # 羁绊/支线节拍 → relationship
    c2 = NarrativeContext(); c2.volume = 1; c2.beat = 'fun_games'; c2.tension_level = 3
    assert ve.render_hook(c2) in data['relationship']

    # 中段/终局前节拍 → payoff_tease
    c3 = NarrativeContext(); c3.volume = 1; c3.beat = 'midpoint'; c3.tension_level = 3
    assert ve.render_hook(c3) in data['payoff_tease']


def test_render_world_entry_injects_genre_atmosphere():
    """render_world_entry 从各世界专用词库（全键合并）抽取氛围描写——不再限于单一 atmosphere 键。"""
    from novel_generator.engine.voice_engine import VoiceEngine
    from novel_generator.engine.word_bank import WordBank
    from novel_generator.engine.plot_state import PlotState
    from novel_generator.engine.word_bank import resolve_bank_path
    import json
    import tempfile
    tmp = tempfile.mkdtemp()
    ve = VoiceEngine(WordBank(seed=2), PlotState(save_path=tmp + '/ps.json'), seed=2)

    # 东方修仙：词条应来自 cultivation_terms.json 的任意键
    cult = json.loads(resolve_bank_path('cultivation_terms').read_text(encoding='utf-8'))
    cult_pool = []
    for v in cult.values():
        if isinstance(v, list):
            cult_pool.extend(v)
    lines = ve.render_world_entry('东方修仙')
    assert lines[-1] in cult_pool, f'{lines[-1]} 不在 cultivation_terms 全键合并池中'

    # 武侠：词条应来自 wuxia_terms.json 的任意键
    wuxia = json.loads(resolve_bank_path('wuxia_terms').read_text(encoding='utf-8'))
    wuxia_pool = []
    for v in wuxia.values():
        if isinstance(v, list):
            wuxia_pool.extend(v)
    lines2 = ve.render_world_entry('武侠·苍云之殇')
    assert lines2[-1] in wuxia_pool, f'{lines2[-1]} 不在 wuxia_terms 全键合并池中'


# ---------------------------------------------------------------------------
# 集成：章末钩子注入（研究驱动）
# ---------------------------------------------------------------------------
def test_hook_appended_to_generated_chapter(tmp_path):
    """集成生成 3 章，断言章末钩子（来自 hook_templates 池）已被注入且末章以钩子收束。"""
    engine = UnifiedNovelEngine(seed=7, output_dir=str(tmp_path))
    engine.plot_state.save_path = str(tmp_path / 'plot_state.json')

    out_path = engine.generate(mode='integrated', chapters=3, skip_rubric=True)
    text = open(out_path, encoding='utf-8').read()

    _, hook_pool = _hook_pool()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # 至少出现一条完整钩子模板（证明章末钩子已注入）
    assert any(l in hook_pool for l in lines), '章末钩子未注入'
    # 末章（opening 节拍无编排层 HOOK，必为追加钩子）最后一行即钩子
    assert lines[-1] in hook_pool, f'末章结尾非钩子: {lines[-1][:30]}'
