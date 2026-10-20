"""主入口（已废弃）：v1.0 兼容入口，实际已整合到 UnifiedNovelEngine。

⚠️ DEPRECATED — 推荐使用 python -m wanjie 启动统一的 v2.1 入口。
  本文件中的 demo_single_chapter() / demo_single_character() 仍可通过
  __main__.py 的交互式菜单（选项 6）访问，但不应作为独立入口使用。

保留原因：向后兼容 + __main__.py 的 demo 功能仍依赖本文件的辅助函数。
完全移除时间：v3.0。
"""

# 旧版入口（已废弃），仅保留 demo 功能供 __main__.py 交互菜单选项 6 调用。
# 不在导入时发出 DeprecationWarning，避免每次进入交互菜单或导入本模块即刷屏告警；
# 如需提示，可在显式调用 demo_* 函数时另行打印。

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wanjie.engine.generators.novel import NovelGenerator
from wanjie.engine.generators.character import CharacterGenerator
from wanjie.engine.generators.chapter import ChapterGenerator
from wanjie.engine.word_bank import WordBank


def demo_single_chapter():
    """演示：生成单章样本。"""
    print("=" * 60)
    print("  单章样本生成")
    print("=" * 60)

    wb = WordBank(seed=42)
    chap_gen = ChapterGenerator(wb)

    chapter = chap_gen.generate(
        chapter_num=1,
        volume_title="《厨艺巨校的故事 之 冷峻奇特的面条》",
        opponent_count=2,  # 减少对手数以便快速预览
        battle_rounds_per_pair=2,
        seed=42,
    )

    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "output", "sample_chapter.txt"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(chapter)

    print(f"\n样本章节已生成，共 {len(chapter):,} 字")
    print(f"输出文件：{output_path}")
    print("\n前500字预览：")
    print("-" * 40)
    print(chapter[:500])
    print("...")


def demo_single_character():
    """演示：生成单个角色描写。"""
    print("=" * 60)
    print("  单角色生成演示")
    print("=" * 60)

    wb = WordBank(seed=42)
    char_gen = CharacterGenerator(wb)

    # 生成3个角色
    for i in range(3):
        char = char_gen.generate()
        intro = char_gen.format_character_intro(char)
        print(f"\n--- 角色 {i+1}：{char['name']} ---")
        print(intro[:400])
        print(f"...(总计 {len(intro):,} 字)")

    print("\n" + "=" * 60)


def interactive_prompt():
    """交互式生成。"""
    print("\n" + "=" * 60)
    print("  《宇宙巨校闪级生》风格小说生成器 v1.0")
    print("=" * 60)
    print()
    print("基于 ASP 多层嵌套循环 + 词库随机替换的注水风格写作程序。")
    print()
    print("可选模式：")
    print("  1. 演示：生成单章样本")
    print("  2. 演示：生成角色描写")
    print("  3. 完整生成：多部小说")
    print("  4. 自定义参数生成")
    print()

    choice = input("请选择模式 [1/2/3/4] (默认1): ").strip() or "1"

    if choice == "1":
        demo_single_chapter()
    elif choice == "2":
        demo_single_character()
    elif choice == "3":
        volumes = input("部数 [默认3]: ").strip() or "3"
        gen = NovelGenerator(seed=42)
        gen.generate(volumes=int(volumes))
    elif choice == "4":
        volumes = int(input("部数 [默认3]: ").strip() or "3")
        chapters = int(input("每部章数 [默认7]: ").strip() or "7")
        opponents = int(input("每章对手数 [默认4]: ").strip() or "4")
        seed = int(input("随机种子 [默认42]: ").strip() or "42")
        gen = NovelGenerator(seed=seed)
        gen.generate(
            volumes=volumes,
            chapters_per_volume=chapters,
            opponents_per_chapter=opponents,
        )
    else:
        print("无效选择。")
        return


def main():
    parser = argparse.ArgumentParser(
        description="《宇宙巨校闪级生》风格小说生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python -m wanjie.main --demo-chapter    # 生成单章样本
  python -m wanjie.main --demo-character   # 演示角色生成
  python -m wanjie.main -v 3 -c 7 -o 4    # 生成3部小说
  python -m wanjie.main                    # 交互式菜单
        """,
    )

    parser.add_argument("--demo-chapter", action="store_true", help="生成单章样本")
    parser.add_argument("--demo-character", action="store_true", help="演示角色生成")
    parser.add_argument("-v", "--volumes", type=int, default=3, help="部数 (默认3)")
    parser.add_argument("-c", "--chapters", type=int, default=7, help="每部章数 (默认7)")
    parser.add_argument("-o", "--opponents", type=int, default=4, help="每章对手数 (默认4)")
    parser.add_argument("-s", "--seed", type=int, default=42, help="随机种子 (默认42)")
    parser.add_argument("--output", type=str, default=None, help="输出目录")

    args = parser.parse_args()

    if args.demo_chapter:
        demo_single_chapter()
    elif args.demo_character:
        demo_single_character()
    elif len(sys.argv) == 1:
        # 无参数：交互式菜单
        interactive_prompt()
    else:
        # 命令行参数模式
        gen = NovelGenerator(seed=args.seed)
        gen.generate(
            volumes=args.volumes,
            chapters_per_volume=args.chapters,
            opponents_per_chapter=args.opponents,
            output_dir=args.output,
        )


if __name__ == "__main__":
    main()
