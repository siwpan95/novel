"""《万界归墟》因果链路小说生成器 - 主入口。

⚠️ DEPRECATED — 推荐使用 python main.py（字数目标生成）或 python -m wanjie --mode causal。
  本文件中的 generate_volume_1() / run_polish_demo() 等功能应迁入 unified_engine.py。
  保留原因：向后兼容 + 独立因果链测试。
  完全移除时间：v3.0。

基于 Save the Cat! 15 节拍大纲，自动生成有因果链的章节。
每章内容基于上一章的情节状态动态决定。
"""

import warnings
warnings.warn(
    'wanjie.causal_main 已废弃，请使用 python -m wanjie --mode causal',
    DeprecationWarning,
    stacklevel=2,
)

import argparse
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wanjie.engine.word_bank import WordBank
from wanjie.engine.plot_state import PlotState
from wanjie.engine.causal_chapter import CausalChapterGenerator
from wanjie.engine.rubric_player import RubricEngine
from wanjie.engine.llm_rewrite import LLMPolishEngine, InteractiveOutline, POLISH_PROMPTS


def run_polish_demo(seed=42, output_dir=None):
    """LLM润色演示：取一个低分章节，展示润色前后对比。"""
    print('='*60)
    print('  LLM润色 + Rubric自动重写 演示')
    print('='*60)
    print()

    # 生成一个章节
    wb = WordBank(seed=seed)
    ps = PlotState()
    gen = CausalChapterGenerator(wb, ps)
    rubric = RubricEngine(seed)

    # 生成第15章（debate，通常Rubric偏低）
    entry = {'chapter': 15, 'beat': 'debate', 'sub_index': 3, 'total_in_beat': 8}
    chapter = gen.generate_chapter(15, entry)

    result_before = rubric.evaluate(chapter, 'debate')
    print(f'润色前 Rubric: {result_before["total"]:.1f}  {result_before["verdict"]}')
    for dim, score in result_before['scores'].items():
        bar = '#'*int(score) + '-'*(10-int(score))
        print(f'  {dim}: [{bar}] {score:.1f}')
    print(f'  问题: {[i["dimension"] for i in result_before.get("issues", [])]}')
    print()

    # 启动润色引擎（inline模式）
    LLMPolishEngine()
    print('润色提示词已生成（需外部LLM执行）。')
    print('在inline模式下，润色由当前对话中的LLM直接完成。')
    print()
    print('提示词预览：')
    prompt_key = 'comprehensive'
    preview = POLISH_PROMPTS[prompt_key].format(text=chapter[:200] + '...')[:300]
    print(preview)
    print()
    print('使用方式: python -m wanjie.causal_main --polish')
    print('         (润色当前使用本地占位模式；接入外部 LLM 请通过环境变量配置)')


def run_interactive(seed=42, output_dir=None):
    """交互式大纲演示。"""
    print('='*60)
    print('  交互式大纲演示')
    print('='*60)
    print()

    io = InteractiveOutline()
    for ch_num in [49, 75, 80]:
        if io.should_pause(ch_num):
            prompt = io.format_prompt(ch_num)
            print(prompt)

    print('使用方式: python -m wanjie.causal_main --interactive')
    print('         在分叉点输入A/B/C选择故事走向')




def run_full_80(seed=42, output_dir=None):
    """Step 5: 完整80章生成 + 逐章Rubric评分。"""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output')
    os.makedirs(output_dir, exist_ok=True)

    wb = WordBank(seed=seed)
    ps = PlotState()
    gen = CausalChapterGenerator(wb, ps)
    rubric = RubricEngine(seed)
    outline = gen.generate_outline(80)

    all_chapters = []
    total_chars = 0
    all_scores = []

    print('=' * 60)
    print('  《万界归墟》第一卷：80章全量生成')
    print('=' * 60)
    for entry in outline:
        ch = entry['chapter']
        text = gen.generate_chapter(ch, entry)
        all_chapters.append('\n' + '=' * 40 + '\n' + text)
        chars = len(text)
        total_chars += chars
        result = rubric.evaluate(text, entry['beat'])
        all_scores.append((ch, result['total'], result['verdict']))
        if ch % 5 == 0 or ch <= 5:
            print(f'第{ch:2d}章 [{entry["beat"]:10s}] {chars:4d}字 Rubric:{result["total"]:.1f}/{result["verdict"]}')

    full_text = '\n'.join(all_chapters)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(output_dir, f'万界归墟_第一卷_全80章_{timestamp}.txt')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f'《万界归墟》第一卷 全80章\n总字数：{total_chars:,}\n\n')
        f.write(full_text)

    avg_score = sum(s[1] for s in all_scores) / len(all_scores)
    passes = sum(1 for s in all_scores if s[2] == 'pass')
    print(f'\n完成！总字数：{total_chars:,}  平均每章：{total_chars//80:,} 字')
    print(f'Rubric均分：{avg_score:.1f}  通过率：{passes}/80')
    print(f'输出：{output_path}')
    return output_path


def generate_volume_1(output_dir: str = None, seed: int = 42):
    """生成《万界归墟》第一卷：归墟苏醒（第1-12章/15节拍）。"""
    if output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "output"
        )
    os.makedirs(output_dir, exist_ok=True)

    wb = WordBank(seed=seed)
    ps = PlotState()
    gen = CausalChapterGenerator(wb, ps)

    # 生成大纲
    outline = gen.generate_outline(chapters_count=80)

    # 构建大纲字典：章号 -> 完整条目
    outline_dict = {entry['chapter']: entry for entry in outline}

    # 选取关键节拍的代表性章节展示
    demo_chapters = [
        1,2,3, 4,5,6, 7,8,9,10,11,12,      # opening + theme + inciting 全展示
        21,22, 27,28, 36, 49,                # break_1, b_story, fun_games, midpoint 抽样
        54, 66, 71, 75,                      # bad_guys, all_lost, dark_night, break_2 每个1章
    ]

    all_chapters = []
    total_chars = 0

    print("=" * 60)
    print("  《万界归墟》第一卷：归墟苏醒 v2")
    print("  因果链路小说生成器（同节拍变体+对话引擎）")
    print("=" * 60)
    print()

    for ch_num in demo_chapters:
        if ch_num not in outline_dict:
            print(f"跳过第{ch_num}章（大纲外）")
            continue
        entry = outline_dict[ch_num]
        print(f"生成第{ch_num}章（{entry['beat']}·变体{entry['sub_index']}）...", end=" ")

        chapter_text = gen.generate_chapter(ch_num, entry)
        all_chapters.append(f"\n{'='*40}")
        all_chapters.append(chapter_text)

        chars = len(chapter_text)
        total_chars += chars
        print(f"{chars:,} 字")

    # 拼接整卷
    full_text = "\n".join(all_chapters)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"万界归墟_第一卷_节拍展示_{timestamp}.txt")

    # 添加小说标题页
    title_page = f"""《万界归墟》第一卷：归墟苏醒
─────────────────────────
因果链路生成器 · 节拍展示版
生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}
总字数：{total_chars:,} 字
生成章数：{len(demo_chapters)}
─────────────────────────

本卷节拍进度（Save the Cat! 15节拍）：
  第1-3章  → 开篇画面（归墟登场，系统绑定）
  第4-6章  → 主题陈述（无法逃脱，被迫接受）
  第7-12章 → 激励事件（玩家降临，被迫管理）
  第21-22章→ 第一转折（发现碎片，世界真实）
  第27-28章→ B故事（结识叶琳，建立羁绊）
  第36章   → 娱乐游戏（公会建立，玩家沙雕）
  第49章   → 中点（碎片回收，归墟解锁星图）
  第54章   → 坏人逼近（代理人现身）
  第66章   → 一切失去（叶琳重伤，碎片失控）
  第71章   → 暗夜灵魂（林朔崩溃，白夜残影）
  第75章   → 第二转折（白夜现身，真相初现）

"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(title_page)
        f.write(full_text)

    print(f"\n完成！总字数：{total_chars:,}")
    print(f"输出文件：{output_path}")
    print(f"情节状态已保存至：{ps.save_path}")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="《万界归墟》因果链路小说生成器")
    parser.add_argument("-s", "--seed", type=int, default=42, help="随机种子")
    parser.add_argument("-o", "--output", type=str, default=None, help="输出目录")
    parser.add_argument("--outline", action="store_true", help="仅生成大纲预览")
    parser.add_argument("--full", action="store_true", help="生成完整80章第一卷")
    parser.add_argument("--polish", action="store_true", help="LLM润色模式（需提供API key）")
    parser.add_argument("--interactive", action="store_true", help="交互式大纲模式（在分叉点暂停）")
    args = parser.parse_args()

    if args.outline:
        wb = WordBank(seed=args.seed)
        ps = PlotState()
        gen = CausalChapterGenerator(wb, ps)
        outline = gen.generate_outline(80)
        print("第1卷大纲预览（前25章）：")
        for entry in outline[:25]:
            print(f"  第{entry['chapter']:2d}章 [{entry['beat']:10s}] {entry.get('description', '')}")
        return

    if args.full:
        return run_full_80(args.seed, args.output)

    if args.polish:
        return run_polish_demo(args.seed, args.output)

    if args.interactive:
        return run_interactive(args.seed, args.output)

    generate_volume_1(args.output, args.seed)
    print("\n✓ 小说生成完毕。")
    print("  下一卷需等第一卷确认后续大纲后继续。")
    print("  可运行 python -m wanjie --diagnose 查看引擎诊断报告。")


if __name__ == "__main__":
    main()
