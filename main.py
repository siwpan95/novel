#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《万界归墟》事件驱动生成器 — 主入口（v2.1 重构）。

范式变更（v2.1）：
  彻底摈弃大纲/节拍/算子配额体系。生成完全由以下三者驱动：
    1. 世界地图（WorldState）—— 空间连续性，区域连通图，势力分布
    2. 时间轴（Timeline）   —— 条件触发事件，世界解锁，节奏分层
    3. 角色模拟（CharacterSim）—— 位置/目标/精力/自主决策

  不再有「第X章该写什么」——角色在地图上移动，事件在时间轴上触发，
  文本是角色在特定时间/地点/情境下的自然反应。

用法：
  python main.py                          # 默认 tiny（2 万字）
  python main.py --preset small           # 中篇 5 万字
  python main.py --preset book            # 整书 20 万字
  python main.py --target-chars 80000     # 自定义字数
  python main.py --seed 42                # 固定种子可复现
  python main.py --resume                 # 断点续写
  python main.py --mode words             # 向后兼容：旧版字数驱动（Legacy）
"""
import argparse
import json
import os
import sys
import time
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _print_safe(text: str) -> None:
    """编码安全打印：Windows 默认 GBK 终端无法编码 ✓/✗/○ 等符号，
    先尝试按终端编码输出，失败则降级为 ASCII 等价符，避免 UnicodeEncodeError。
    """
    try:
        sys.stdout.write(text + '\n')
        sys.stdout.flush()
    except UnicodeEncodeError:
        table = {
            '\u2713': '[OK]',   # ✓
            '\u2717': '[X]',    # ✗
            '\u25cb': '[~]',    # ○
            '\u2605': '*',      # ★
            '\u251c': '|-',     # ├
            '\u2514': '+-',     # └
            '\u2500': '-',      # ─
        }
        out = text
        for k, v in table.items():
            out = out.replace(k, v)
        sys.stdout.write(out.encode(
            sys.stdout.encoding or 'utf-8', errors='replace').decode(
            sys.stdout.encoding or 'utf-8') + '\n')
        sys.stdout.flush()

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from novel_generator.engine.word_bank import WordBank
from novel_generator.engine.plot_state import PlotState
from novel_generator.engine.world_state import WorldStateManager
from novel_generator.engine.timeline import Timeline
from novel_generator.engine.storyline import StoryBoard
from novel_generator.engine.scene_director import SceneDirector
from novel_generator.engine.integrated_chapter_generator import IntegratedChapterGenerator
from novel_generator.engine.wordcount_director import PRESETS, PRESET_CN, DEFAULT_WC_CONFIG
from novel_generator.engine.voice_engine import VoiceEngine

# 保留旧版入口以向后兼容
from novel_generator.unified_engine import UnifiedNovelEngine

_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        import logging
        _logger = logging.getLogger('novel.main')
        _logger.setLevel(logging.DEBUG)
        if not _logger.handlers:
            _fh = logging.FileHandler('novel_generator.log', encoding='utf-8')
            _fh.setLevel(logging.DEBUG)
            _fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
            _logger.addHandler(_fh)
            _ch = logging.StreamHandler()
            _ch.setLevel(logging.INFO)
            _ch.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
            _logger.addHandler(_ch)
    return _logger


def main():
    parser = argparse.ArgumentParser(
        description='《万界归墟》事件驱动生成器（世界地图 / 时间轴 / 角色自主）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            '示例:\n'
            '  python main.py                             # 默认 tiny（2 万字）\n'
            '  python main.py --preset book               # 整书 20 万字\n'
            '  python main.py --target-chars 80000        # 自定义字数\n'
            '  python main.py --seed 42 --resume          # 固定种子并断点续写\n'
            '  python main.py --mode words --preset tiny  # 旧版字数驱动模式\n'
        ),
    )
    parser.add_argument('--target-chars', type=int, default=None)
    parser.add_argument('--preset', type=str, default='短篇',
                        choices=['短篇', '中篇', '长篇', 'tiny', 'small', 'book'],
                        help='预设规模（默认 短篇=2万字 / 中篇=5万字 / 长篇=20万字）')
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--output', type=str, default=None)
    parser.add_argument('--diagnose', action='store_true')
    parser.add_argument('--tasks', action='store_true', help='审计任务事件日志（<output>/pipeline.log）')
    parser.add_argument('--limit', type=int, default=100, help='--tasks 显示条数')
    parser.add_argument('--json', action='store_true', help='--tasks JSON 输出')
    parser.add_argument('--mode', type=str, default='scene',
                        choices=['scene', 'words'],
                        help='scene=事件驱动（v2.1, 默认）/ words=旧版字数驱动')
    args = parser.parse_args()

    t0 = time.time()
    log = _get_logger()

    # 种子
    actual_seed = args.seed if args.seed is not None else int(time.time() * 1000) % (2 ** 31)
    target = args.target_chars if args.target_chars is not None else PRESETS[args.preset]

    # --tasks 审计任务日志（零重依赖）
    if args.tasks:
        from novellog import PipelineLog
        _out_dir = args.output or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
        _log_path = os.path.join(_out_dir, 'pipeline.log')
        if not os.path.isfile(_log_path):
            print(f'[tasks] 无任务日志: {_log_path}')
            return
        _entries = PipelineLog(_log_path).read(limit=args.limit)
        if args.json:
            print(json.dumps(_entries, ensure_ascii=False, indent=2))
            return
        print(f'任务日志 {_log_path}（最近 {len(_entries)} 条）：')
        for _e in _entries:
            _stage = _e.get('stage', '-')
            _extra = ' '.join(f'{k}={v}' for k, v in _e.items()
                              if k not in ('seq', 'ts', 'type', 'stage', 'run_id'))
            print(f"  #{_e['seq']} {_e['ts']} [{_e['type']}] 阶段{_stage} {_extra}")
        _runs = sorted({_e.get('run_id') for _e in _entries if _e.get('run_id')})
        _errs = [_e for _e in _entries if _e['type'] == 'stage_error']
        print(f'  涉及运行 {len(_runs)} 次，阶段错误 {len(_errs)} 条')
        return

    # --diagnose 适用于所有模式：打印诊断信息后退出
    if args.diagnose:
        engine = UnifiedNovelEngine(seed=actual_seed, output_dir=args.output)
        _print_safe(engine.diagnostic_report())
        return

    # ================================================================
    # Legacy 模式：旧版字数驱动（向后兼容）
    # ================================================================
    if args.mode == 'words':
        from novellog import PipelineLog
        _od = args.output or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
        _tl = PipelineLog(os.path.join(_od, 'pipeline.log'))
        _rid = PipelineLog.new_run_id()
        _tl.append('run_start', run_id=_rid, mode='words', target_chars=target, seed=actual_seed)
        engine = UnifiedNovelEngine(seed=actual_seed, output_dir=args.output)
        try:
            result = engine.generate_by_words(target_chars=target, resume=args.resume)
        except Exception as _exc:
            _tl.append('stage_error', stage='words', run_id=_rid, error=str(_exc))
            _tl.append('run_end', run_id=_rid, ok=False, errors=1)
            raise
        _tl.append('stage_done', stage='words', run_id=_rid, output=str(result))
        _tl.append('run_end', run_id=_rid, ok=True, errors=0)
        print(f'\n输出: {os.path.abspath(result)}')
        print(f'总耗时 {time.time() - t0:.0f}s')
        return

    # ================================================================
    # v3.0 场景驱动模式
    # ================================================================
    print(f'\n{"=" * 60}')
    print(f'  《万界归墟》v2.1 — 事件驱动生成')
    print(f'  驱动: 世界地图 / 时间轴 / 角色自主')
    print(f'  目标: {target:,} 字 | 种子: {actual_seed}')
    print(f'  续写: {args.resume}')
    print(f'{"=" * 60}')

    output_dir = args.output or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')

    # ── 任务事件日志（日志即事实源，<output>/pipeline.log） ──
    from novellog import PipelineLog
    tasklog = PipelineLog(os.path.join(output_dir, 'pipeline.log'))
    run_id = PipelineLog.new_run_id()
    tasklog.append('run_start', run_id=run_id, mode='scene', target_chars=target,
                   seed=actual_seed, resume=args.resume)

    def _stage(name, fn, *a, **kw):
        _t = time.time()
        tasklog.append('stage_start', stage=name, run_id=run_id)
        try:
            value = fn(*a, **kw)
        except Exception as _exc:
            tasklog.append('stage_error', stage=name, run_id=run_id, error=str(_exc))
            raise
        tasklog.append('stage_done', stage=name, run_id=run_id,
                       duration_s=round(time.time() - _t, 2))
        return value

    # 1. 初始化核心基础设施
    wb = _stage('init', WordBank, seed=actual_seed)
    ps = _stage('plot_state', PlotState)
    voice = _stage('voice', VoiceEngine, wb, ps, seed=actual_seed)

    # 2. 世界状态管理器（空间模型）
    wm = _stage('world', WorldStateManager, wb, seed=actual_seed)
    # 预加载初始世界的多个世界
    for world_name in ['归墟', '武侠·苍云之殇', '末日废土']:
        wm.load_world(world_name)

    # 3. 时间轴（事件调度）
    timeline = _stage('timeline', Timeline.default_timeline, seed=actual_seed)

    # 4. 棋盘布局（多线叙事调度）
    storyboard = _stage('storyboard', StoryBoard.default_board, seed=actual_seed)

    # 5. 整合生成器（保留渲染管线）
    integrated_gen = _stage('integrated_gen', IntegratedChapterGenerator, wb, ps, seed=actual_seed)

    # 6. 场景导演
    config = dict(DEFAULT_WC_CONFIG)
    config['save_every'] = 10
    config['log_every'] = 5
    config['min_passage_chars'] = 200
    config['max_passage_chars'] = 1200

    director = _stage('director', SceneDirector,
                      integrated_gen, ps, wm, timeline, storyboard, config, output_dir, seed=actual_seed)

    # 7. 生成
    try:
        result = director.generate(target_chars=target, resume=args.resume)
    except Exception as _exc:
        tasklog.append('stage_error', stage='generate', run_id=run_id, error=str(_exc))
        tasklog.append('run_end', run_id=run_id, ok=False, errors=1)
        raise
    tasklog.append('stage_done', stage='generate', run_id=run_id, output=str(result))
    tasklog.append('run_end', run_id=run_id, ok=True, errors=0)

    elapsed = time.time() - t0
    print(f'\n输出: {os.path.abspath(result)}')
    print(f'总耗时 {elapsed:.0f}s | 平均 {target / elapsed:.0f} 字/秒')
    print(f'活跃世界: {len(wm._unlocked_worlds)} 个')
    print(f'时间轴事件: {len(timeline._fired_ids)} 次触发')


if __name__ == '__main__':
    main()
