"""角色生成器：半随机生成角色（姓名、外貌、装备、武功）。

基于《宇宙巨校闪级生》的经典模式：
- 姓名半随机（指定姓氏或完全随机）
- 外貌描写按身体部位逐项随机填充
- 兵器名 = 随机前缀 + 随机类型 + 可选后缀
- 武功名 = 随机前缀 + 随机动作 + 可选后缀
- 法/宝物名 = 随机前缀 + 随机类型
"""

from ..word_bank import WordBank


class CharacterGenerator:
    """角色生成器。"""

    def __init__(self, wb: WordBank):
        self._wb = wb
        # 模板挖掘流水线：人物出场模板 + 槽位值池从 templates/ 词库加载
        self._intro_templates = self._load_intro_templates()
        self._char_slots = self._load_character_slots()

    def _load_intro_templates(self):
        try:
            data = self._wb.load("character_intro")
            return data.get("templates", [])
        except Exception:
            return []

    def _load_character_slots(self):
        pools = {
            "aura": ["帝威浩荡", "杀气凛然", "气度不凡", "锋芒毕露", "深不可测", "温润如玉"],
            "scope": ["万古诸天", "整个广场", "一山众人", "四方观者", "满堂宾客"],
            "modifier": ["虚空", "长空", "山门", "天际", "夜色"],
            "visual": ["眸光如电", "衣袂无风自动", "周身气机流转", "眸光淡漠"],
        }
        try:
            data = self._wb.load("character_slots")
            for k, v in data.items():
                if isinstance(v, list) and v:
                    pools[k] = v
        except Exception:
            pass
        return pools

    def render_entrance(self, char: dict) -> str:
        """从 templates/character_intro 词库发牌渲染「人物出场」段落。

        与 format_character_intro（外貌介绍）互补：本方法产出的是「登场亮相」的
        一句式亮相描写，模板骨架 + 槽位值均来自词库。
        """
        rng = self._wb.get_rng()
        if not self._intro_templates:
            return ""
        tpl = rng.choice(self._intro_templates)
        vars_ = {"name": char.get("name", "?"), "char": char.get("name", "?")}
        for k, pool in self._char_slots.items():
            vars_[k] = rng.choice(pool)
        for k, v in vars_.items():
            tpl = tpl.replace("{" + k + "}", v)
        return tpl

    def generate(self, name: str = None, surname: str = None, title: str = None,
                 assign_personality: bool = False) -> dict:
        """生成一个完整角色。

        Returns:
            dict with keys: name, title, age, height, weight, weapon, skill, magic, treasure,
                           appearance (list of body-part descriptions),
                           personality (dict: tag/dialogue_style/battle_pref/quirk — 仅当 assign_personality=True)
        """
        rng = self._wb.get_rng()

        if name is None:
            # 半随机名字：随机姓氏 + 随机2个名字用字
            name = self._wb.generate_name(2, surname)

        # 基本属性
        age = rng.randint(10, 60)
        height = round(1.3 + rng.random() * 0.7, 2)  # 1.3-2.0米
        weight = round(30 + rng.random() * 60, 1)  # 30-90kg

        # 装备和技能
        weapon = self._gen_weapon()
        skill = self._gen_skill()
        magic = self._gen_magic()
        treasure = self._gen_treasure()

        # 外貌描写的身体部位列表
        body_order = [
            "head", "neck", "face", "nose", "eyes", "ears", "mouth",
            "teeth", "tongue", "chest", "shoulders", "arms", "hands",
            "fingers", "legs", "feet", "buttocks", "waist", "bones",
            "eyebrows", "beard", "voice", "smell", "figure"
        ]
        appearance = []
        for part in body_order:
            try:
                desc = self._wb.pick("body_parts", part)
                appearance.append(desc)
            except KeyError:
                pass

        return {
            "name": name,
            "title": title or "",
            "age": age,
            "height": height,
            "weight": weight,
            "weapon": weapon,
            "skill": skill,
            "magic": magic,
            "treasure": treasure,
            "appearance": appearance,
            "personality": self._gen_personality() if assign_personality else None,
        }

    def _gen_personality(self) -> dict:
        """从性格标签词库中随机分配性格、对话风格、战斗偏好和小动作。"""
        try:
            data = self._wb.load("personality_tags")
        except Exception:
            return {}
        tag = self._wb.get_rng().choice(data["personality_tags"])
        return {
            "tag": tag,
            "dialogue_style": data["dialogue_styles"].get(tag, {}),
            "battle_preference": data["battle_preferences"].get(tag, {}),
            "quirk": self._wb.get_rng().choice(data["quirks"].get(tag, ["无特殊小动作"])),
        }

    def _gen_weapon(self) -> str:
        prefix = self._wb.pick("equipment", "weapon_prefix")
        wtype = self._wb.pick("equipment", "weapon_type")
        # 50%概率加后缀
        if self._wb.get_rng().random() < 0.5:
            suffix = self._wb.pick("equipment", "weapon_suffix")
            return f"☆{prefix}{wtype}{suffix}☆"
        return f"☆{prefix}{wtype}☆"

    # 术语前缀词表：拼接招式名时，body/suffix 开头若带任意前缀词则剥离，
    # 避免「远古X远古Y远古Z」式前缀堆砌（缺陷 #4 根因 B）。
    _PREFIX_TOKENS = ('远古', '浩渺', '渊深', '杳冥', '太古', '赤红', '凤羽', '断罪',
                      '混元', '归墟', '九幽', '混沌', '寂灭', '焚天', '孤绝')

    @classmethod
    def _strip_all_prefixes(cls, text: str) -> str:
        """删除 text 中所有术语前缀词（出现即删），避免招式全称里前缀堆砌。"""
        for tok in cls._PREFIX_TOKENS:
            text = text.replace(tok, '')
        return text

    @classmethod
    def _compress_prefix(cls, text: str) -> str:
        """压缩 text 中的术语前缀：仅保留首个前缀词，其后所有前缀词（不论是否连续）全部删除。

        例：远古太古混沌X -> 远古X；远古蚀月远古 -> 远古蚀月。避免多前缀堆砌。
        """
        first_end = None
        for tok in cls._PREFIX_TOKENS:
            if text.startswith(tok):
                first_end = len(tok)
                break
        if first_end is None:
            return text
        head = text[:first_end]
        tail = text[first_end:]
        # 删除 tail 中所有术语前缀词
        for tok in cls._PREFIX_TOKENS:
            tail = tail.replace(tok, '')
        return head + tail

    @classmethod
    def _compose_skill(cls, prefix: str, body: str, suffix: str = '') -> str:
        prefix = cls._compress_prefix(prefix)
        # body / suffix 中所有前缀词删除，使全名只保留 prefix 一处前缀修饰
        body = cls._strip_all_prefixes(body)
        if suffix:
            suffix = cls._strip_all_prefixes(suffix)
        return f"☆{prefix}{body}{suffix}☆"

    def _gen_skill(self) -> str:
        prefix = self._wb.pick("equipment", "skill_prefix")
        body = self._wb.pick("equipment", "skill_body")
        if self._wb.get_rng().random() < 0.4:
            suffix = self._wb.pick("equipment", "skill_suffix")
            return CharacterGenerator._compose_skill(prefix, body, suffix)
        return CharacterGenerator._compose_skill(prefix, body)

    def _gen_magic(self) -> str:
        prefix = self._wb.pick("equipment", "skill_prefix")
        body = self._wb.pick("equipment", "skill_body")
        if self._wb.get_rng().random() < 0.4:
            suffix = self._wb.pick("equipment", "skill_suffix")
            return CharacterGenerator._compose_skill(prefix, body, suffix)
        return CharacterGenerator._compose_skill(prefix, body)

    def _gen_treasure(self) -> str:
        prefix = self._wb.pick("equipment", "treasure_prefix")
        ttype = self._wb.pick("equipment", "treasure_type")
        return f"☆{prefix}{ttype}☆"

    def format_character_intro(self, char: dict, use_template: bool = True) -> str:
        """将角色数据格式化为《宇宙巨校闪级生》风格的人物介绍段落。

        经典格式参考：
        "[名字]的年龄看上去有[年龄]岁，身高约[身高]米，体重[体重]多公斤。
        他最善使用的兵器是[武器]，有一身奇特的武功[武功]，看家的魔法是[法术]，
        另外还身上带着一件奇异的法宝[法宝]。"
        然后逐项描述外貌。
        """
        lines = []

        # 基本信息段
        age_str = "十三四岁" if char["age"] < 15 else f"{char['age']}岁"
        title_prefix = f"{char['title']}" if char['title'] else char['name']
        lines.append(
            f"{title_prefix}的年龄看上去有{age_str}的样子，"
            f"身高约一米{int((char['height'] % 1) * 100)}，"
            f"体重{int(char['weight'])}多公斤。"
        )
        lines.append(
            f"他最善使用的兵器是{char['weapon']}，"
            f"有一身奇特的武功{char['skill']}，"
            f"看家的魔法是{char['magic']}，"
            f"另外还身上带着一件奇异的法宝{char['treasure']}。"
        )

        # 外貌描述段（分段输出，避免一段太长）
        appearance = char["appearance"]
        # 头面部
        head_parts = appearance[:9]  # head, neck, face, nose, eyes, ears, mouth, teeth, tongue
        lines.append(f"{char['name']}长着{'、'.join(head_parts[:4])}，最出奇的是一张{head_parts[2]}，配着一只{head_parts[3]}。")
        lines.append(f"鼻子上面是一对{head_parts[4]}，两边是{head_parts[5]}，鼻子下面是{head_parts[6]}。")
        lines.append(f"说话时露出{head_parts[7]}，一条{head_parts[8]}确实绝无仅有的精妙同时还有着几分奇妙。")

        # 身体段
        body_parts = appearance[9:16]  # chest, shoulders, arms, hands, fingers, legs, feet
        lines.append(f"他那{body_parts[0]}，{body_parts[1]}，肩膀下面是{body_parts[2]}，他{body_parts[3]}的确十分典雅而又风光。")
        lines.append(f"他那{body_parts[4]}显得十分珍奇却又透着一丝诡异，{body_parts[5]}，{body_parts[6]}真的十分酷野而又有些超脱。")

        # 剩余部分
        if len(appearance) > 16:
            remaining = appearance[16:]
            lines.append(f"他那{'、'.join(remaining[:3])}，加上{remaining[3] if len(remaining) > 3 else ''}，整体显得{self._wb.pick('adjectives', 'quality')}。")

        # 结尾句
        lines.append(f"他微笑时有种{appearance[-3] if len(appearance) > 19 else '独特而难以描述'}的声音，兴奋时会散发出{appearance[-2] if len(appearance) > 20 else '一股神秘而诱人'}的气息。")
        lines.append(f"他那{appearance[-4] if len(appearance) > 18 else '与众不同的'}骨骼仿佛十分帅气却又透着一丝豪迈，那种{self._wb.pick('adjectives', 'appearance')}的神态真的十分酷野又和谐。")

        return "\n".join(lines)
