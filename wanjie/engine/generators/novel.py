"""小说生成器：最顶层生成器，生成完整小说。

多层嵌套循环结构：
Layer 1 (最外层): 部 → 卷 (例如 111部)
Layer 2: 卷 → 章 (每卷7章)
Layer 3: 章 → 角色+打斗+对话 (章内循环)
Layer 4 (最内层): 模板 → 词库随机填充 (句子级)

这是 ASP 风格"多层嵌套循环中替换关键字"写法的完整实现。
"""

import os
import time
from typing import Optional
from ..word_bank import WordBank
from .chapter import VolumeGenerator, ChapterGenerator


class NovelGenerator:
    """小说生成器主控。"""

    # 预设巨校类型（可根据需要扩展）
    DEFAULT_SCHOOL_TYPES = [
        "厨艺巨校", "包装巨校", "保镖巨校", "编辑巨校", "表演巨校",
        "勇士巨校", "税收巨校", "采矿巨校", "导演巨校", "储藏巨校",
        "博物巨校", "创意巨校", "地理巨校", "艺术巨校", "能源巨校",
        "赌博巨校", "雕塑巨校", "魔术巨校", "动物巨校", "毒药巨校",
    ]

    def __init__(self, seed: Optional[int] = None):
        self._wb = WordBank(seed=seed)
        self._vol_gen = VolumeGenerator(self._wb)
        self._chap_gen = ChapterGenerator(self._wb)

    def generate(
        self,
        volumes: int = 20,
        chapters_per_volume: int = 7,
        opponents_per_chapter: int = 4,
        school_types: list[str] = None,
        output_dir: str = None,
        seed: int = None,
    ) -> str:
        """生成完整小说。

        Args:
            volumes: 卷（部）数
            chapters_per_volume: 每卷章数
            opponents_per_chapter: 每章对手数量
            school_types: 巨校类型列表
            output_dir: 输出目录
            seed: 随机种子

        Returns:
            完整小说文本。
        """
        if seed is not None:
            self._wb.get_rng().seed(seed)

        if school_types is None:
            school_types = self.DEFAULT_SCHOOL_TYPES[:volumes]

        if output_dir is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "output"
            )

        os.makedirs(output_dir, exist_ok=True)

        self._wb.get_rng()
        all_text = []
        total_chapters = volumes * chapters_per_volume

        # === 小说前言 ===
        all_text.append(self._generate_preface(volumes, total_chapters))
        all_text.append("")

        # === 最外层循环：遍历每一卷（部） ===
        for vol_idx, school_type in enumerate(school_types, 1):
            print(f"正在生成第{vol_idx}部《{school_type}的故事》...")

            # 生成卷标题
            adj1 = self._wb.pick("adjectives", "appearance")
            adj2 = self._wb.pick("adjectives", "appearance")
            noun = self._wb.pick("locations", "terrain_type")
            volume_title = f"《{adj1}{adj2}的{noun}》"

            # 生成此卷的7章（每章主角和搭档复用）
            volume_text = self._vol_gen.generate(
                volume_num=vol_idx,
                volume_title=f"{school_type}的故事 之 {volume_title}",
                chapters=chapters_per_volume,
                opponents_per_chapter=opponents_per_chapter,
            )

            all_text.append(f"\n{'='*60}")
            all_text.append(f"第{vol_idx}部 {school_type}的故事")
            all_text.append(f"{'='*60}\n")
            all_text.append(volume_text)

            # 每卷之间的小结
            all_text.append(f"\n（第{vol_idx}部完。总进度：{vol_idx}/{volumes}）\n")

        # === 小说尾声 ===
        all_text.append(self._generate_epilogue(volumes, total_chapters))

        full_novel = "\n".join(all_text)

        # 写入文件
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(output_dir, f"novel_{timestamp}.txt")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_novel)

        # 统计
        char_count = len(full_novel)
        print("\n小说生成完毕！")
        print(f"  总卷（部）数：{volumes}")
        print(f"  总章数：{total_chapters}")
        print(f"  总字数：{char_count:,} 字")
        print(f"  输出文件：{output_path}")

        return full_novel

    def _generate_preface(self, volumes: int, total_chapters: int) -> str:
        """生成小说前言。"""
        return f"""本书说明

本书是用Python语言编写的魔幻神侠小说程序自动生成的作品。
全书共有{volumes}部，分为{total_chapters}章。
本书的写作过程由程序全自动完成，是一部实验性文学作品。

本书至少描写了数千个有着不同姓名、不同容貌、不同特长的人物，
以及数千种造型新奇、行为怪异的怪物。
从理论上说：本程序可以随机生成的各种不同人物、怪物和景物，
每种至少也在万亿级别以上。

本程序的设计理念基于"框架先于内容"的原则：
先建立完整的模板结构，再通过多层嵌套循环从词库中随机替换关键字，
实现"注水风格"的批量文本生成。

需要说明的是：用程序编写本书的主要目的并不单纯是为了炫技，
而是为了探求一种新的写作方式，研究程序化文本生成的边界与可能性。

（本作品为实验性质，保留所有权利。）
"""

    def _generate_epilogue(self, volumes: int, total_chapters: int) -> str:
        """生成小说尾声。"""
        adj1 = self._wb.pick("adjectives", "quality")
        adj2 = self._wb.pick("adjectives", "quality")
        return f"""
{'='*60}
                          全 书 完
{'='*60}

本书共{volumes}部，{total_chapters}章。

这是一部{adj1}的、{adj2}的作品。

感谢您的阅读。

（全书完）
"""
