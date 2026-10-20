"""章节生成器：多层嵌套循环的核心实现。

结构（模仿《宇宙巨校闪级生》）：
Layer 4: 身体部位词库 → 外貌描述句子（最内层循环）
Layer 3: 4个角色 × 外貌模板 → 4000-6000字角色介绍
Layer 2: 主角+搭档 vs 4个对手 → 打斗+对话交替
Layer 1: 章前引语 + 场景描写 + 角色介绍 + 战斗序列 → 完整章节

每章约 6000-10000 字。
"""

from ..word_bank import WordBank
from .character import CharacterGenerator
from .battle import BattleGenerator, SceneGenerator
from .dialogue import DialogueGenerator


class ChapterGenerator:
    """章节生成器：多层嵌套循环生成完整一章。"""

    def __init__(self, wb: WordBank):
        self._wb = wb
        self._char_gen = CharacterGenerator(wb)
        self._scene_gen = SceneGenerator(wb)
        self._battle_gen = BattleGenerator(wb)
        self._dialog_gen = DialogueGenerator(wb)

    def generate(
        self,
        chapter_num: int,
        volume_title: str,
        hero: dict = None,
        partner: dict = None,
        opponent_count: int = 4,
        battle_rounds_per_pair: int = 3,
        seed: int = None
    ) -> str:
        """生成完整一章。

        Args:
            chapter_num: 章序号
            volume_title: 所属卷的标题（用于章标题生成）
            hero: 主角设定（dict），可复用跨章角色
            partner: 搭档设定（dict），可复用跨章角色
            opponent_count: 本章对手数量（默认4个）
            battle_rounds_per_pair: 每对对阵打斗回合数
            seed: 随机种子

        Returns:
            完整章节文本。
        """
        if seed is not None:
            self._wb.get_rng().seed(seed)

        rng = self._wb.get_rng()
        lines = []

        # === 章标题 ===
        chapter_title = self._generate_chapter_title(chapter_num, volume_title)
        lines.append(chapter_title)
        lines.append("")
        lines.append("=" * 40)
        lines.append("")

        # === 主角和搭档（如果未传入则生成） ===
        if hero is None:
            hero = self._char_gen.generate(surname=rng.choice(["蘑菇", "蓝光"]))
        if partner is None:
            partner = self._char_gen.generate()

        # === 场景描写（~500字） ===
        scene_text = self._scene_gen.generate_scene()
        lines.append("【场景】")
        lines.append(scene_text)
        lines.append("")

        # === 对四个对手的详细描述（每对手~1500字 = 合计~6000字）===
        lines.append("【本章主角与搭档】")
        lines.append(self._char_gen.format_character_intro(hero))
        lines.append("")
        lines.append(self._char_gen.format_character_intro(partner))
        lines.append("")

        opponents = []
        lines.append("【本章登场对手】")
        for i in range(opponent_count):
            opponent = self._char_gen.generate()
            opponents.append(opponent)
            lines.append(f"--- 对手 {i+1} ---")
            lines.append(self._char_gen.format_character_intro(opponent))
            lines.append("")

        # === 战斗序列 (主角和搭档轮流对阵四个对手) ===
        lines.append(f"【{hero['name']}与{partner['name']}的挑战】")
        lines.append("")

        terrain_name = f"闪{self._wb.pick('locations', 'terrain_type')}"

        # 交替对战：主角和搭档轮流对阵各个对手
        fighters = []
        for i in range(opponent_count):
            current_attacker = hero if i % 2 == 0 else partner
            fighters.append((current_attacker, opponents[i]))

        battle_rounds_per_pair * len(fighters)
        round_counter = 1

        for idx, (attacker, defender) in enumerate(fighters):
            lines.append(f"———— 第{idx+1}场：{attacker['name']} VS {defender['name']} ————")
            lines.append("")

            # 打斗（多轮）
            battle_text = self._battle_gen.generate_battle(
                char_a=attacker,
                char_b=defender,
                rounds=battle_rounds_per_pair,
                terrain=terrain_name
            )
            lines.append(battle_text)
            lines.append("")

            # 对话
            dialogue = self._dialog_gen.generate_exchange(
                name_a=attacker['name'],
                name_b=defender['name'],
                skill_a=attacker['skill'],
                skill_b=defender['skill'],
                weapon_a=attacker['weapon'],
                weapon_b=defender['weapon'],
                treasure_a=attacker['treasure'],
                treasure_b=defender['treasure'],
                terrain=terrain_name
            )
            lines.append(dialogue)
            lines.append("")

            round_counter += battle_rounds_per_pair

        # === 章尾收束 ===
        endings = [
            f"就这样，{hero['name']}与{partner['name']}一路过关斩将，向着更深的{volume_title}进发。",
            f"{hero['name']}收起{hero['weapon'].strip('☆')}，望向远方的下一片战场。",
            f"这一章的挑战虽然结束，但{hero['name']}知道，真正的大战，还在后面。",
            f"{partner['name']}拍了拍{hero['name']}的肩膀：\"走吧，还有更多对手在等着我们。\"",
        ]
        lines.append(rng.choice(endings))

        return "\n".join(lines)

    def _generate_chapter_title(self, chapter_num: int, volume_title: str) -> str:
        """生成章标题。"""
        adj = self._wb.pick("adjectives", "appearance")
        noun = self._wb.pick("locations", "terrain_type")
        return f"第{chapter_num}章 {adj}{noun}"


class VolumeGenerator:
    """卷生成器：一卷包含N章，每章复用主角和搭档设定。"""

    def __init__(self, wb: WordBank):
        self._wb = wb
        self._chapter_gen = ChapterGenerator(wb)

    def generate(self, volume_num: int, volume_title: str,
                 chapters: int = 7, opponents_per_chapter: int = 4) -> str:
        """生成完整一卷。

        Args:
            volume_num: 卷序号
            volume_title: 卷标题
            chapters: 本卷包含章数（默认7章）
            opponents_per_chapter: 每章对手数量

        Returns:
            完整卷文本。
        """
        rng = self._wb.get_rng()
        lines = []

        # 卷标题
        lines.append(f"第{volume_num}卷 {volume_title}")
        lines.append("=" * 60)
        lines.append("")

        # 生成本卷主角和搭档（跨章复用）
        hero = CharacterGenerator(self._wb).generate(surname="蘑菇")
        partner = CharacterGenerator(self._wb).generate(surname="月光")

        for ch in range(1, chapters + 1):
            chapter_num = (volume_num - 1) * chapters + ch
            chapter_text = self._chapter_gen.generate(
                chapter_num=chapter_num,
                volume_title=volume_title,
                hero=hero,
                partner=partner,
                opponent_count=opponents_per_chapter,
                battle_rounds_per_pair=3,
                seed=rng.randint(1, 999999)
            )
            lines.append(chapter_text)
            lines.append("")
            lines.append("-" * 50)
            lines.append("")

        return "\n".join(lines)
