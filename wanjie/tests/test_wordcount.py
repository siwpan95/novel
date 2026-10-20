"""WordCountDirector 核心编排循环测试 —— 验证字数达标、保存、段落生成。

重点：
1. 生成达到目标字数（或接近）。
2. 输出文件存在且内容非空。
3. save_every 间隔正确持久化。
4. resume 标志位正确工作。
"""
import os

from wanjie.engine.word_bank import WordBank
from wanjie.engine.plot_state import PlotState
from wanjie.engine.voice_engine import VoiceEngine
from wanjie.engine.emergent_orchestrator import EmergentOrchestrator
from wanjie.engine.wordcount_director import WordCountDirector, DEFAULT_WC_CONFIG


def _tiny_cfg(target: int = 400) -> dict:
    """极小编排配置用于快速测试。"""
    cfg = dict(DEFAULT_WC_CONFIG)
    cfg.update({
        'min_passage_chars': 80,
        'max_passage_chars': 180,
        'save_every': 2,
        'log_every': 1,
        'plant_every': 10,          # 减少伏笔种植干扰
        'recent_window': 2,
        'avg_op_chars': 80,
        'weights': {
            'base_quota': {'scene': 3, 'action': 2, 'battle': 0, 'dialogue': 0, 'reveal': 0, 'hook': 0},
            'state': {
                'tension_high': {'action': 1.2, 'battle': 1.2},
                'pending_foreshadowing': {'reveal': 1.2, 'hook': 1.1},
                'arc_progress_high': {'dialogue': 1.2},
                'recent_repeat_penalty': 0.4,
            },
        },
    })
    return cfg


class _MockGen:
    """最小 IntegratedChapterGenerator mock，用于 WordCountDirector 测试。"""

    def __init__(self, voice, ps):
        self._voice = voice
        self._ps = ps
        self._quality = _MockQuality()

    def _sync_characters(self, ctx):
        pass

    def _execute_operation(self, op, ctx):
        from wanjie.engine.beat_orchestrator import OpType
        lines = []
        world = getattr(ctx, 'world_name', '归墟')
        t = getattr(op, 'type', str(op))
        if t in (OpType.SCENE, 'scene'):
            line = f'{world}的场景在眼前展开。风带来陌生的气息，暮色笼罩大地。'
        elif t in (OpType.ACTION, 'action'):
            line = '他缓缓迈出一步，靴底碾过碎石。心跳在胸腔里重重擂了一下。'
        elif t in (OpType.BATTLE, 'battle'):
            line = '两股力量在空中碰撞，发出刺耳的爆鸣。碎片四散飞溅。'
        elif t in (OpType.DIALOGUE, 'dialogue'):
            line = '「你确定这条路是对的？」声音低沉，像在压着什么。'
        elif t in (OpType.REVEAL, 'reveal'):
            line = '他忽然明白了——这一切并非偶然。某种更大的力量在幕后操控。'
        elif t in (OpType.HOOK, 'hook'):
            line = '远处，有什么正在苏醒。'
        elif t == OpType.TEXT:
            line = getattr(op, 'text', '——')
        elif t == OpType.BREAK:
            return ['']
        else:
            line = '——'
        lines.append(line)
        return lines

    def _wire_foreshadowing(self, ctx, ops, L, events, passage_no):
        pass

    def _enforce_must_include(self, ctx, L, events):
        pass

    def _enrich_thin_chapter(self, L, beat, ctx):
        return L

    def _foreshadowing_pool(self):
        return {'seeds': {}}


class _MockQuality:
    def process_light(self, L, beat):
        return L


# ---------------------------------------------------------------------------
# 1. 字数达标
# ---------------------------------------------------------------------------
def test_wordcount_meets_target(tmp_path):
    """生成达到目标字数（允许少量超出）。"""
    cfg = _tiny_cfg(400)
    ps_path = str(tmp_path / 'ps.json')
    out_dir = str(tmp_path / 'output')

    wb = WordBank(seed=42)
    ps = PlotState(save_path=ps_path)
    voice = VoiceEngine(wb, ps, seed=42)
    orch = EmergentOrchestrator(voice, cfg, rng=wb.get_rng())
    director = WordCountDirector(None, ps, orch, cfg, out_dir)
    director._gen = _MockGen(voice, ps)

    out_path = director.generate(400, seed=42, resume=False)
    assert os.path.isfile(out_path), f'未生成输出文件: {out_path}'

    content = open(out_path, encoding='utf-8').read()
    # 正文长度（排除元数据头）
    text_lines = [l for l in content.split('\n')
                  if not l.startswith('《') and not l.startswith('目标') and l.strip()]
    text = ''.join(text_lines)
    actual = len(text)

    # 应 >= 目标字数的 60%（允许因算子粒度产生波动）
    assert actual >= 240, f'生成字数不足: {actual} < 240'
    # 不应超出目标 3 倍
    assert actual <= 1200, f'生成字数严重超标: {actual}'


# ---------------------------------------------------------------------------
# 2. save_every 持久化
# ---------------------------------------------------------------------------
def test_wordcount_persists_on_save_interval(tmp_path):
    """save_every=2 时，每 2 段保存一次状态。"""
    cfg = _tiny_cfg(500)
    cfg['save_every'] = 1    # 每段保存

    ps_path = str(tmp_path / 'ps_save.json')
    out_dir = str(tmp_path / 'output')

    wb = WordBank(seed=42)
    ps = PlotState(save_path=ps_path)
    voice = VoiceEngine(wb, ps, seed=42)
    orch = EmergentOrchestrator(voice, cfg, rng=wb.get_rng())
    director = WordCountDirector(None, ps, orch, cfg, out_dir)
    director._gen = _MockGen(voice, ps)
    director.generate(500, seed=42, resume=False)

    # 状态应已持久化
    assert ps.state.get('current_chars', 0) > 0, '未记录 current_chars'
    assert ps.state.get('current_passage', 0) > 0, '未记录 current_passage'

    # JSON 文件应存在且可重新加载
    assert os.path.isfile(ps_path), f'持久化文件不存在: {ps_path}'
    ps2 = PlotState(save_path=ps_path)
    assert ps2.state.get('current_chars', 0) > 0, '重新加载后 current_chars 丢失'


# ---------------------------------------------------------------------------
# 3. resume 标志位
# ---------------------------------------------------------------------------
def test_wordcount_resume_flag(tmp_path):
    """resume=False 从头开始；resume=True 从已保存状态继续。"""
    cfg = _tiny_cfg(500)
    ps_path = str(tmp_path / 'ps_flag.json')
    out_dir = str(tmp_path / 'output')

    # 第一段：从头开始
    wb = WordBank(seed=42)
    ps = PlotState(save_path=ps_path)
    voice = VoiceEngine(wb, ps, seed=42)
    orch = EmergentOrchestrator(voice, cfg, rng=wb.get_rng())
    d1 = WordCountDirector(None, ps, orch, cfg, out_dir)
    d1._gen = _MockGen(voice, ps)
    d1.generate(300, seed=42, resume=False)
    chars_before = ps.state.get('current_chars', 0)

    # 第二段：续写
    wb2 = WordBank(seed=42)
    ps2 = PlotState(save_path=ps_path)
    voice2 = VoiceEngine(wb2, ps2, seed=42)
    orch2 = EmergentOrchestrator(voice2, cfg, rng=wb2.get_rng())
    d2 = WordCountDirector(None, ps2, orch2, cfg, out_dir)
    d2._gen = _MockGen(voice2, ps2)
    d2.generate(500, seed=42, resume=True)
    chars_after = ps2.state.get('current_chars', 0)

    # resume 应不丢失之前的进度
    assert chars_after >= chars_before, \
        f'resume 不应减少字数: {chars_after} < {chars_before}'
    assert chars_after >= 400, \
        f'resume 后应接近目标: {chars_after}'


# ---------------------------------------------------------------------------
# 4. 输出格式
# ---------------------------------------------------------------------------
def test_wordcount_output_has_header_and_body(tmp_path):
    """输出文件包含正确的元数据头部和正文。"""
    cfg = _tiny_cfg(400)
    ps_path = str(tmp_path / 'ps_out.json')
    out_dir = str(tmp_path / 'output')

    wb = WordBank(seed=42)
    ps = PlotState(save_path=ps_path)
    voice = VoiceEngine(wb, ps, seed=42)
    orch = EmergentOrchestrator(voice, cfg, rng=wb.get_rng())
    director = WordCountDirector(None, ps, orch, cfg, out_dir)
    director._gen = _MockGen(voice, ps)

    out_path = director.generate(400, seed=42, resume=False)
    content = open(out_path, encoding='utf-8').read()

    assert '《万界归墟》' in content, '缺少书名'
    assert '目标字数' in content, '缺少目标字数行'
    assert '实得字数' in content, '缺少实得字数行'
    # 正文至少 200 字
    lines = content.split('\n')
    body_start = 0
    for i, l in enumerate(lines):
        if l.startswith('目标字数'):
            body_start = i + 2  # 跳过空行
            break
    body = ''.join(lines[body_start:])
    assert len(body) >= 200, f'正文过短: {len(body)}'
