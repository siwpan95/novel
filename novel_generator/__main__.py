# -*- coding: utf-8 -*-
"""《万界归墟》小说生成器 — 统一入口（python -m novel_generator）。

注意：字数目标生成的主入口已迁移到仓库根目录的 main.py（即 `python main.py`）。
本文件保留为统一的模块入口与交互式菜单，兼容 asp / causal 旧引擎。

模式：
  python -m novel_generator --mode words --preset small   # 字数目标生成（★推荐）
  python -m novel_generator --mode asp -v 3 -c 7 -o 4      # ASP模板流
  python -m novel_generator --mode causal --chapters 80    # 因果链流（旧版兼容）
  python -m novel_generator --diagnose                     # 诊断报告
  python -m novel_generator                                # 交互式菜单
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from novel_generator.unified_engine import UnifiedNovelEngine
from novel_generator.engine.wordcount_director import PRESETS


def interactive_menu():
    """交互式菜单。"""
    print()
    print('=' * 60)
    print('  《万界归墟》双引擎小说生成器 v2.2')
    print('  ★ 字数目标生成（弱化大纲 / 状态驱动 / 抗罐头）')
    print('=' * 60)
    print()
    print('可选模式：')
    print('  1. 字数目标生成 — words（★推荐，--preset tiny/small/book）')
    print('  2. ASP模板流    — 多层嵌套循环+词库替换')
    print('  3. 因果链流     — 旧版硬编码文本（向后兼容）')
    print('  4. 诊断报告     — 引擎状态')
    print('  5. ASP演示      — 生成单章/角色样本')
    print()

    choice = input('请选择模式 [1/2/3/4/5] (默认1): ').strip() or '1'

    if choice == '1':
        preset = input(f'规模 [{"/".join(PRESETS.keys())}，默认 tiny]: ').strip() or 'tiny'
        seed_s = input('随机种子（留空=随机）: ').strip()
        seed = int(seed_s) if seed_s else None
        engine = UnifiedNovelEngine(seed=seed or 42)
        engine.generate_by_words(
            target_chars=PRESETS.get(preset, PRESETS['tiny']),
            resume=False,
        )
    elif choice == '2':
        v = input('部数 [默认3]: ').strip() or '3'
        c = input('每部章数 [默认7]: ').strip() or '7'
        o = input('每章对手数 [默认4]: ').strip() or '4'
        engine = UnifiedNovelEngine(seed=42)
        engine.generate(mode='asp', volumes=int(v),
                        chapters_per_volume=int(c),
                        opponents_per_chapter=int(o))
    elif choice == '3':
        ch = input('章数 [默认80]: ').strip() or '80'
        engine = UnifiedNovelEngine(seed=42)
        engine.generate(mode='causal', chapters=int(ch))
    elif choice == '4':
        engine = UnifiedNovelEngine(seed=42)
        print(engine.diagnostic_report())
    elif choice == '5':
        from novel_generator.main import demo_single_chapter, demo_single_character
        sub = input('  1.单章样本 / 2.角色样本 [默认1]: ').strip() or '1'
        if sub == '1':
            demo_single_chapter()
        else:
            demo_single_character()
    else:
        print('无效选择。')


def main():
    parser = argparse.ArgumentParser(
        description='《万界归墟》小说生成器 v2.2（字数目标 / asp / causal）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            '示例：\n'
            '  python -m novel_generator --mode words --preset small\n'
            '  python -m novel_generator --mode asp -v 3 -c 7 -o 4\n'
            '  python -m novel_generator --mode causal --chapters 80\n'
            '  python -m novel_generator --diagnose\n'
        ),
    )
    parser.add_argument('--mode', type=str, default=None,
                        choices=['words', 'asp', 'causal'],
                        help='引擎模式（默认 words）')
    parser.add_argument('--preset', type=str, default='tiny',
                        choices=list(PRESETS.keys()),
                        help='字数规模（words 模式）：' + ' / '.join(
                            f'{k}={v:,}' for k, v in PRESETS.items()))
    parser.add_argument('--target-chars', type=int, default=None,
                        help='自定义目标字数（words 模式，覆盖 --preset）')
    parser.add_argument('--chapters', type=int, default=80,
                        help='章数（causal 模式，默认80）')
    parser.add_argument('-v', '--volumes', type=int, default=3,
                        help='部数（asp 模式，默认3）')
    parser.add_argument('-c', '--chapters-per-volume', type=int, default=7,
                        help='每部章数（asp 模式，默认7）')
    parser.add_argument('-o', '--opponents', type=int, default=4,
                        help='每章对手数（asp 模式，默认4）')
    parser.add_argument('-s', '--seed', type=int, default=42,
                        help='随机种子')
    parser.add_argument('--output', type=str, default=None,
                        help='输出目录')
    parser.add_argument('--resume', action='store_true',
                        help='从 plot_state.json 断点续写（words 模式）')
    parser.add_argument('--no-rubric', action='store_true',
                        help='跳过 Rubric 评分（causal 模式加速）')
    parser.add_argument('--diagnose', action='store_true',
                        help='输出诊断报告')
    args = parser.parse_args()

    engine = UnifiedNovelEngine(seed=args.seed, output_dir=args.output)

    if args.diagnose:
        print(engine.diagnostic_report())
        return

    if args.mode is None:
        interactive_menu()
        return

    if args.mode == 'words':
        target = args.target_chars if args.target_chars is not None else PRESETS[args.preset]
        engine.generate_by_words(target_chars=target, resume=args.resume)
    elif args.mode == 'asp':
        engine.generate(mode='asp', volumes=args.volumes,
                        chapters_per_volume=args.chapters_per_volume,
                        opponents_per_chapter=args.opponents)
    elif args.mode == 'causal':
        engine.generate(mode='causal', chapters=args.chapters,
                        skip_rubric=args.no_rubric)


if __name__ == '__main__':
    main()
