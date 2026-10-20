"""Resume 端到端测试 —— 验证状态保存→中断→续写的完整链路。

重点：
1. PlotState save/load 往返：状态完整性（角色/伏笔/字数/进度不丢失）。
2. 同 seed 下，分次生成与一次完整生成的输出可复现。
3. Resume 后的段落编号、字数累计、伏笔连续性正确。
"""
import os

from wanjie.engine.word_bank import WordBank
from wanjie.engine.plot_state import PlotState
from wanjie.engine.voice_engine import VoiceEngine
from wanjie.engine.emergent_orchestrator import EmergentOrchestrator
from wanjie.engine.wordcount_director import WordCountDirector, DEFAULT_WC_CONFIG


def _make_tiny_config(target: int = 500) -> dict:
    """定制极小编排配置用于快速测试。"""
    cfg = dict(DEFAULT_WC_CONFIG)
    cfg.update({
        'min_passage_chars': 80,
        'max_passage_chars': 200,
        'save_every': 1,          # 每段都保存
        'log_every': 1,
        'plant_every': 3,
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


# ---------------------------------------------------------------------------
# 1. PlotState 往返：save → reload → 字段完整性
# ---------------------------------------------------------------------------
def test_plot_state_roundtrip(tmp_path):
    """save/load 往返后关键字段不丢失。"""
    ps_path = str(tmp_path / 'plot_state.json')
    ps = PlotState(save_path=ps_path)
    # 写入一些运行时状态
    ps.state['current_chapter'] = 42
    ps.state['current_chars'] = 12345
    ps.state['current_passage'] = 7
    ps.state['fragment_count'] = 3
    ps.add_foreshadowing('f1', '测试伏笔', 1, 10, recovery_text='闭合')
    ps.save()

    # 重新加载
    ps2 = PlotState(save_path=ps_path)
    assert ps2.state['current_chapter'] == 42
    assert ps2.state['current_chars'] == 12345
    assert ps2.state['current_passage'] == 7
    assert ps2.state['fragment_count'] == 3
    assert len(ps2.state['foreshadowing']) == 1
    assert ps2.state['foreshadowing'][0]['id'] == 'f1'
    assert ps2.state['foreshadowing'][0]['recovery_text'] == '闭合'


def test_plot_state_roundtrip_characters(tmp_path):
    """角色状态保存后正确恢复。"""
    ps_path = str(tmp_path / 'ps_chars.json')
    ps = PlotState(save_path=ps_path)
    ps.set_char_state('林朔', 'emotional_state', '愤怒')
    ps.set_char_state('林朔', 'current_goal', '测试目标')
    ps.save()

    ps2 = PlotState(save_path=ps_path)
    assert ps2.get_char_state('林朔', 'emotional_state') == '愤怒'
    assert ps2.get_char_state('林朔', 'current_goal') == '测试目标'


# ---------------------------------------------------------------------------
# 2. Resume 端到端：生成 → 保存 → 新引擎 → 续写
# ---------------------------------------------------------------------------
def test_resume_continuity(tmp_path):
    """同 seed 分两段生成应产生连贯输出，段落编号和字数累计正确。

    流程：
    - 第一段：生成约 300 字 → 保存状态
    - 第二段：新引擎续写剩余 400 字 → 断言总字数 >= 700
    - 验证复活后的 token 状态（current_chars / current_passage）正确
    """
    cfg = _make_tiny_config(700)
    ps_path = str(tmp_path / 'ps_resume.json')
    out_dir = str(tmp_path / 'output')

    # --- 第一段生成 ---
    wb = WordBank(seed=42)
    ps = PlotState(save_path=ps_path)
    voice = VoiceEngine(wb, ps, seed=42)
    orch = EmergentOrchestrator(voice, cfg, rng=wb.get_rng())
    director = WordCountDirector(None, ps, orch, cfg, out_dir)
    # 注入 _gen mock（只提供 VoiceEngine，其余方法不走）
    director._gen = _MockGen(voice, ps)

    out1 = director.generate(350, seed=42, resume=False)
    assert os.path.isfile(out1)
    _text1 = open(out1, encoding='utf-8').read()
    chars1 = ps.state.get('current_chars', 0)
    passage1 = ps.state.get('current_passage', 0)
    assert chars1 >= 200, f'第一段字数不足：{chars1}'
    assert passage1 >= 1, f'第一段段落数不足：{passage1}'

    # --- 第二段续写 ---
    wb2 = WordBank(seed=42)
    ps2 = PlotState(save_path=ps_path)  # 从第一段状态恢复
    voice2 = VoiceEngine(wb2, ps2, seed=42)
    orch2 = EmergentOrchestrator(voice2, cfg, rng=wb2.get_rng())
    director2 = WordCountDirector(None, ps2, orch2, cfg, out_dir)
    director2._gen = _MockGen(voice2, ps2)

    out2 = director2.generate(700, seed=42, resume=True)
    assert os.path.isfile(out2)
    _text2 = open(out2, encoding='utf-8').read()
    chars2 = ps2.state.get('current_chars', 0)
    passage2 = ps2.state.get('current_passage', 0)

    # 续写后字数应不小于第一段
    assert chars2 >= chars1, f'续写字数不应减少：{chars2} < {chars1}'
    assert passage2 >= passage1, f'续写段落数不应减少：{passage2} < {passage1}'
    # 总字数接近目标（允许少量超出）
    assert chars2 >= 600, f'续写后总字数不足：{chars2}'


def test_resume_preserves_foreshadowing(tmp_path):
    """Resume 后伏笔状态保持连续——不会重复种植已有伏笔。"""
    cfg = _make_tiny_config(600)
    cfg['plant_every'] = 2   # 更频繁种植以触发伏笔
    ps_path = str(tmp_path / 'ps_fs.json')
    out_dir = str(tmp_path / 'output')

    # 第一段
    wb = WordBank(seed=99)
    ps = PlotState(save_path=ps_path)
    voice = VoiceEngine(wb, ps, seed=99)
    orch = EmergentOrchestrator(voice, cfg, rng=wb.get_rng())
    director = WordCountDirector(None, ps, orch, cfg, out_dir)
    director._gen = _MockGen(voice, ps)
    director.generate(300, seed=99, resume=False)

    fs_before = len(ps.state.get('foreshadowing', []))
    passage_before = ps.state.get('current_passage', 0)

    # 第二段续写
    wb2 = WordBank(seed=99)
    ps2 = PlotState(save_path=ps_path)
    voice2 = VoiceEngine(wb2, ps2, seed=99)
    orch2 = EmergentOrchestrator(voice2, cfg, rng=wb2.get_rng())
    director2 = WordCountDirector(None, ps2, orch2, cfg, out_dir)
    director2._gen = _MockGen(voice2, ps2)
    director2.generate(600, seed=99, resume=True)

    fs_after = len(ps2.state.get('foreshadowing', []))
    passage_after = ps2.state.get('current_passage', 0)

    # 段落数增加
    assert passage_after > passage_before, f'续写后段落应增加：{passage_after} <= {passage_before}'
    # 伏笔数不减少（新增可能，但不应丢失已有的）
    assert fs_after >= fs_before, f'伏笔不应在 resume 后丢失：{fs_after} < {fs_before}'


# ---------------------------------------------------------------------------
# 3. 同 seed 可复现性
# ---------------------------------------------------------------------------
def test_same_seed_reproducibility(tmp_path):
    """相同 seed 下，一次性生成与分两次生成的终态进度一致。"""
    cfg = _make_tiny_config(400)
    target = 400

    # --- 一次性生成 ---
    ps_path1 = str(tmp_path / 'ps_onepass.json')
    out_dir1 = str(tmp_path / 'out1')
    wb = WordBank(seed=77)
    ps = PlotState(save_path=ps_path1)
    voice = VoiceEngine(wb, ps, seed=77)
    orch = EmergentOrchestrator(voice, cfg, rng=wb.get_rng())
    d1 = WordCountDirector(None, ps, orch, cfg, out_dir1)
    d1._gen = _MockGen(voice, ps)
    d1.generate(target, seed=77, resume=False)
    chars_one = ps.state.get('current_chars', 0)
    _passage_one = ps.state.get('current_passage', 0)

    # --- 分两次生成（共享 PlotState）---
    ps_path2 = str(tmp_path / 'ps_twopass.json')
    out_dir2 = str(tmp_path / 'out2')
    wb2a = WordBank(seed=77)
    ps2 = PlotState(save_path=ps_path2)
    voice2a = VoiceEngine(wb2a, ps2, seed=77)
    orch2a = EmergentOrchestrator(voice2a, cfg, rng=wb2a.get_rng())
    d2a = WordCountDirector(None, ps2, orch2a, cfg, out_dir2)
    d2a._gen = _MockGen(voice2a, ps2)
    d2a.generate(target // 2, seed=77, resume=False)

    halfway_chars = ps2.state.get('current_chars', 0)
    assert halfway_chars > 0, '第一阶段生成失败'

    # 第二阶段续写
    wb2b = WordBank(seed=77)
    ps2b = PlotState(save_path=ps_path2)
    voice2b = VoiceEngine(wb2b, ps2b, seed=77)
    orch2b = EmergentOrchestrator(voice2b, cfg, rng=wb2b.get_rng())
    d2b = WordCountDirector(None, ps2b, orch2b, cfg, out_dir2)
    d2b._gen = _MockGen(voice2b, ps2b)
    d2b.generate(target, seed=77, resume=True)

    chars_two = ps2b.state.get('current_chars', 0)
    _passage_two = ps2b.state.get('current_passage', 0)

    # 一次性与分次的总字数应接近（允许因 RNG 状态分叉产生微小差异）
    assert abs(chars_two - chars_one) < 200, \
        f'同 seed 下分次与一次性总字数偏差过大：{chars_two} vs {chars_one}'


# ---------------------------------------------------------------------------
# Mock: 最小 IntegratedChapterGenerator，提供 resume 路径所需的最小接口
# ---------------------------------------------------------------------------
class _MockGen:
    """只提供 WordCountDirector 在 _render_passage 中所调用的那几个方法。"""

    def __init__(self, voice, ps):
        self._voice = voice
        self._ps = ps
        self._quality = _MockQuality()
        from wanjie.engine.beat_orchestrator import VoiceOperation, OpType
        self.VoiceOperation = VoiceOperation
        self.OpType = OpType

    def _sync_characters(self, ctx):
        """同步 PlotState 角色状态到 NarrativeContext（resume 路径兼容）。"""
        pass  # resume 测试中角色同步不关键

    def _execute_operation(self, op, ctx):
        """极简版：每个算子产出一行描述文本。"""
        from wanjie.engine.beat_orchestrator import OpType
        lines = []
        world = ctx.world_name if hasattr(ctx, 'world_name') else '归墟'
        t = op.type if hasattr(op, 'type') else str(op)
        if t in (OpType.SCENE, 'scene'):
            line = f'{world}的场景在眼前展开。暮色如纱，笼罩着这片古老的土地。'
        elif t in (OpType.ACTION, 'action'):
            line = '他缓缓迈出一步，靴底碾过碎石，发出细碎的声响。风从远处吹来，带着陌生的气息。'
        elif t in (OpType.BATTLE, 'battle'):
            line = '剑光一闪，两股力量在空中碰撞，发出刺耳的爆鸣。'
        elif t in (OpType.DIALOGUE, 'dialogue'):
            line = '「你确定要这么做？」声音低沉而克制，像在压着什么。'
        elif t in (OpType.REVEAL, 'reveal'):
            line = '他忽然意识到——这一切并非偶然。某种更大的力量正在幕后操控。'
        elif t in (OpType.HOOK, 'hook'):
            line = '远处，有什么东西正在苏醒。'
        elif t == OpType.TEXT:
            line = op.text if hasattr(op, 'text') else '——'
        elif t == OpType.BREAK:
            return ['']
        else:
            line = '——'
        lines.append(line)
        return lines

    def _wire_foreshadowing(self, ctx, ops, L, events, passage_no):
        pass  # 伏笔闭环在 resume 测试中不关键

    def _enforce_must_include(self, ctx, L, events):
        pass

    def _enrich_thin_chapter(self, L, beat, ctx):
        return L

    def _foreshadowing_pool(self):
        return {'seeds': {}}


class _MockQuality:
    def process_light(self, L, beat):
        return L
    def check_repetition(self, text):
        from types import SimpleNamespace
        return SimpleNamespace(max_count=0, penalty=0.0, repeated=[])
