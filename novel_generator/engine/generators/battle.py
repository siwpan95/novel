"""场景生成器与战斗生成器。

场景：生成《宇宙巨校闪级生》风格的场地描写。
战斗：生成随机的打斗段落（武功招式名+动作描述随机组合）。
"""

from ..word_bank import WordBank
import random


class SceneGenerator:
    """场景/场地生成器。"""

    def __init__(self, wb: WordBank):
        self._wb = wb
        # 模板挖掘流水线：方位列表从 templates/scene_slots 词库加载（fallback 硬编码）
        self._directions = self._load_directions()

    def _load_directions(self):
        try:
            data = self._wb.load("scene_slots")
            d = data.get("directions", [])
            if d:
                return d
        except Exception:
            pass
        return ["南方", "北方", "东方", "西方", "东南方", "西北方", "西南方", "东北方"]

    def generate_scene(self, scene_name: str = None, flavor: str = "mystical") -> str:
        """生成一段场景描写。

        经典格式：
        "[巨校类型][级别]创意表演考场的实习场地——[场地名]就在前面。
        [场景形容词]的[地形名]极似一个[比喻]。
        极目远方，在[地形名]的[方位]，隐蔽着[若有若无的/光芒四射的][地标]，
        凝目看去，那里的风光非常像[比喻]，那里的风貌[品质描述]，[秘密暗示]。"
        """
        lines = []

        # 第一句：场地引入
        terrain = self._wb.pick("locations", "terrain_type")
        scene_name = scene_name or terrain
        lines.append(f"{scene_name}就在前面。")

        # 第二句：地形比喻
        adj = self._wb.pick("locations", "terrain_prefix")
        simile = self._wb.pick("locations", "scene_like")
        lines.append(f"{adj}的{terrain}{simile}。")

        # 第三句：地标出现
        direction = self._wb.get_rng().choice(self._directions)
        landmark_adj = self._wb.pick("locations", "landmark_prefix")
        landmark = self._wb.pick("locations", "landmark_type")
        landmark_simile = self._wb.pick("locations", "scene_like")
        lines.append(
            f"极目远方，在{terrain}的{direction}，"
            f"隐蔽着{landmark_adj}的{landmark}，"
            f"凝目看去，那里的风光{landmark_simile}，"
        )

        # 第四句：品质描述
        quality = self._wb.pick("locations", "scene_quality")
        secret = self._wb.pick("locations", "secrets_hint")
        lines.append(f"那里的风貌{quality}，{secret}。")

        return "\n".join(lines)


class BattleGenerator:
    """战斗/打斗场景生成器。

    核心逻辑：用多层嵌套循环将招式名、动作词、效果词随机组合。
    每一轮打斗 = 攻击方动作 + 防守方反应 + 效果描述。
    """

    # 动作模板池（15种战术模式，每类3-5个模板）
    ACTION_PATTERNS = [
        # 类型1：标准对攻（原有3种）
        "{attacker}猛然施展{skill}，{action}，直取{defender}的要害！",
        "{attacker}一个翻身，手中的{weapon}化作{num}道{color}光芒，{action}！",
        "{attacker}周身{color}气劲暴涨，那招{skill}已经{action}。",
        # 类型2：环境互动型（新增）
        "{attacker}脚尖在{terrain}上一点，借力跃至半空，{skill}自上而下{action}！",
        "{attacker}一掌拍在{terrain}边的石壁上，碎石纷飞中，{weapon}已从烟雾里{action}。",
        "利用{terrain}的地形优势，{attacker}身形忽左忽右，{skill}从最刁钻的角度{action}。",
        # 类型3：心理博弈型——假装露出破绽（新增）
        "{attacker}故意卖出破绽，中门大开。{defender}的攻势刚至，{attacker}却诡异地一转，{skill}反手{action}！",
        "{attacker}的动作突然慢了半拍——不是力竭，是诱敌。在{defender}抢攻的瞬间，{weapon}已经封住了所有退路。",
        "他看起来像是要后退——但脚后跟刚离地，整个人就像{spring}一样{lunge}了过来。假动作。",
        # 类型4：兵器克制型（新增）
        "一寸长一寸强——{attacker}的{weapon}在距离上完全压制了{defender}，{skill}如影随形，{action}。",
        "一寸短一寸险——{attacker}不退反进，欺入{defender}的{weapon}攻击死角，{skill}贴身{action}。",
        "{attacker}突然弃了{weapon}——不对，是兵刃脱手飞向{defender}面门，而他本人已赤手{action}！",
        # 类型5：流派对抗型——刚猛 vs 柔韧（新增）
        "{attacker}的攻势如狂风暴雨，一招接一招，不给{defender}任何喘息之机。{skill}连环{action}！",
        "{attacker}的身法柔若无骨，{defender}的每一击都像是打在了棉花上——而他的反击却如毒蛇吐信，{action}。",
        "一刚一柔的两种武学正面碰撞——{attacker}的{skill}大开大合，{action}，而{defender}的{def_skill}以柔克刚。",
        # 类型6：对话打断型（新增）
        "「你的招式——」{defender}的话还没说完，{attacker}的{skill}已经{lunge}到了咽喉前！战斗中说话是致命的。",
        "{attacker}在出招的同时冷笑了一声：「你师父没教过你——」后半句话和{weapon}一起{action}。",
        "两人交错而过的瞬间，{attacker}在{defender}耳边说了一句话。没人听清内容——但{defender}的脸色瞬间变了。分神的一刹那，{skill}已至。",
        # 类型7：连击链型（新增）
        "第一招——{skill}；第二招——{weapon}回旋{action}；第三招——借着回旋的力道，整个人如陀螺般{action2}。三招一气呵成！",
        "连环七击！{attacker}的{weapon}在空中织出一张密不透风的网——第一击{action}，第二击封退路，第三击、第四击、第五击如潮水般涌来！",
    ]

    REACTION_PATTERNS = [
        # 原有5种
        "{defender}丝毫不慌，{def_skill}迎上，两股力量轰然相撞！",
        "{defender}面色微变，急使{def_skill}，堪堪{verb}住了这致命一击。",
        "{defender}早有防备，{treasure}光华一闪，竟将那{thing}尽数{verb}。",
        "{defender}大喝一声，{def_skill}全力施展，与{attacker}的攻势正面硬撼。",
        "{defender}身形急退，同时{def_skill}化作一道屏障，勉强{verb}。",
        # 新增6种
        "{defender}不退反进——不是硬接，而是侧身一让，{attacker}的攻势落空，而他自己的{def_skill}已从侧面{action}。",
        "{defender}似乎早已看穿了{skill}的破绽。他甚至没有用{def_skill}——只是微微侧头，{weapon}贴着他的耳朵擦过。然后他的反击开始了。",
        "{defender}一脚跺在{terrain}上——不是借力，是制造障碍。{debris}里，{attacker}的视线被挡了{moment}。就在这{moment}，{defender}的{def_skill}已经{action}。",
        "{defender}避无可避——但他没有想避。他双手交叉护在胸前，硬吃了这一记{skill}。骨骼发出令人牙酸的声音——但距离被他压进了{num2}尺之内。",
        "{defender}的应对漂亮得不像临时反应——仿佛他等这一记{skill}已经等了很久。{treasure}的光芒精准地刺入了{skill}最薄弱的那一点。",
        "{defender}忽然闭上了眼睛。不是放弃——是以耳代目。{attacker}的{skill}带着风声呼啸而至，而他仅凭听觉判断方位，{action}。",
    ]

    EFFECT_PATTERNS = [
        # 原有5种
        "两股力量相撞之处，爆发出{color}的光芒，整片{terrain}都被震得{shake}。",
        "轰然巨响中，{defender}被震退了{num}步，脸上露出{expression}之色。",
        "但见{color}光芒一闪，{attacker}的攻势竟被{defender}的{def_skill}尽数化解。",
        "这一招余波所及，{terrain}上的{thing}纷纷{verb}，景象{adj}至极。",
        "两股力量在空中僵持了{num}息的功夫，终于轰然炸开，{thing}四散飞溅。",
        # 新增效果模板（所有长句均已参数化，避免高频调用下逐字复读）
        "两人各退数步。{attacker}低头看了一眼自己的{gear}——那里多了{damage}。{defender}的嘴角渗出了血丝。这一回合，谁都没占到便宜。",
        "碰撞的中心安静了{moment}——然后冲击波才{belated}地扩散开来。{terrain}上的{thing}像被无形的手扫过，齐齐{verb}。",
        "没有爆炸，没有巨响。两股力量在{terrain}上方无声地抵消了——{attacker}和{defender}都清楚，越安静的对撞越凶险。",
        "{defender}单膝跪地，{weapon}插在{terrain}上支撑着身体。他抬起头，眼神里没有{lack}——只有更浓的{gaze}。",
        "烟雾散去后，两人脚下的{terrain}已经面目全非。但{attacker}连看都没看一眼——他的注意力全锁在{focus}上。",
    ]

    def __init__(self, wb: WordBank):
        self._wb = wb
        # 模板挖掘流水线（template_miner.py）：从 templates/ 词库加载额外模板骨架 + 槽位值池。
        # 词库是权威来源，硬编码只作 fallback（词库缺失时行为与改造前一致）。
        self.ACTION_PATTERNS = self._load_extra("battle_action", self.ACTION_PATTERNS)
        self.REACTION_PATTERNS = self._load_extra("battle_reaction", self.REACTION_PATTERNS)
        self.EFFECT_PATTERNS = self._load_extra("battle_effect", self.EFFECT_PATTERNS)
        self._slot_pools = self._load_slots()
        # 洗牌发牌：模板按池无放回发牌，牌用完才重新洗牌。
        # BattleGenerator 在整次生成中是单实例复用，队列跨场持续 →
        # 不同战斗天然错峰，单个模板不会因 rng.choice 的抽样方差被连抽。
        self._deal_rng = random.Random(20260805)
        self._deal_queues: dict = {}

    def _load_extra(self, bank_name: str, base: list) -> list:
        """从 templates/ 词库加载模板骨架，去重后追加到硬编码池。"""
        try:
            data = self._wb.load(bank_name)
            extra = data.get("templates", [])
            have = set(base)
            return base + [t for t in extra if t not in have]
        except Exception:
            return base

    def _load_slots(self) -> dict:
        """从 templates/battle_slots 词库加载槽位值池（fallback 到硬编码列表）。"""
        pools = {
            "color": ["金", "银", "红", "蓝", "紫", "青", "白", "黑", "七彩", "混沌"],
            "thing": ["闪电", "狂风", "烈焰", "寒冰", "雷霆", "飞剑", "巨石", "星辰"],
            "action": ["呼啸而出", "疾射而去", "翻涌而至", "狂卷而来",
                        "劈头盖脸砸下", "铺天盖地涌来", "排山倒海压下"],
            "action2": ["横扫而出", "反卷回来", "倒撞而下", "斜切而入",
                         "自下而上挑起", "贴地扫过"],
            "verb": ["抵挡", "化解", "格挡", "避开", "硬接", "弹开", "消融"],
            "shout": ["大喝", "怒吼", "长啸", "猛喝", "厉啸", "暴喝"],
            "expression": ["惊骇", "凝重", "苍白", "难看", "难以置信", "铁青", "恐惧"],
            "adj": ["壮观", "恐怖", "绚烂", "惨烈", "激烈", "震撼"],
            "spring": ["弹簧", "离弦的箭", "绷断的弓弦", "被松开的机括", "挣脱锁链的兽"],
            "lunge": ["撞", "扑", "欺", "蹿", "劈", "刺", "顶"],
            "shake": ["嗡嗡作响", "微微开裂", "碎屑纷落", "晃了一下",
                       "扬起一层灰", "低低震了很久"],
            "debris": ["碎石飞溅", "尘土腾起", "碎屑打着旋", "一片扬灰",
                        "崩开的渣子四散", "地面炸开的粉末"],
            "gear": ["袖口", "衣襟", "护腕", "肩甲", "下摆", "手背", "领口"],
            "damage": ["一道口子", "一片焦痕", "一层白霜", "几缕裂纹",
                        "一道血痕", "半个焦黑的掌印"],
            "moment": ["一秒", "半息", "一瞬", "两个呼吸", "一刹那", "小半个弹指"],
            "belated": ["后知后觉", "迟了半拍", "慢了一步", "姗姗来迟",
                         "不情不愿", "沉闷"],
            "lack": ["恐惧", "犹豫", "退意", "慌乱", "半分服软"],
            "gaze": ["战意", "杀意", "冷静", "疯狂", "执拗", "兴奋"],
            "focus": ["对方的下一个动作", "彼此的呼吸节奏", "对手握兵器的那只手",
                       "对方脚下的重心", "对面那双眼睛"],
        }
        try:
            data = self._wb.load("battle_slots")
            for k, v in data.items():
                if isinstance(v, list) and v:
                    pools[k] = v
        except Exception:
            pass
        return pools

    def _deal(self, key: str, pool: list):
        """从 pool 无放回发一张牌；发空才重新洗牌。

        队列里存的是**下标**而不是内容，因此同一个 key 也能安全复用于
        内容随角色/场地变化的动态池（如战斗开场白），不会把上一场的
        句子漏进这一场。
        """
        if not pool:
            return None
        n = len(pool)
        queue = self._deal_queues.get(key)
        if not queue or max(queue) >= n:
            queue = list(range(n))
            self._deal_rng.shuffle(queue)
            # 重洗时若下一张与刚发出的那张相同，往后挪一位，避免衔接处撞牌
            last = self._deal_queues.get(f'{key}::last')
            if n > 1 and queue[-1] == last:
                queue[-1], queue[-2] = queue[-2], queue[-1]
            self._deal_queues[key] = queue
        idx = queue.pop()
        self._deal_queues[f'{key}::last'] = idx
        return pool[idx]

    def _from_arsenal(self, char: dict, pool_key: str, single_key: str) -> str:
        """从角色自己的装备库里发一件；没有库就退回单件字段。

        角色档案被缓存以保住人设之后，单件字段会让 {skill} 在全书里恒定，
        含它的模板便退化成同一句。按角色维护独立队列，人设与变化兼得。
        """
        pool = char.get(pool_key)
        if not pool:
            return char[single_key]
        return self._deal(f'{pool_key}::{char.get("name", "?")}', pool)

    def generate_round(self, attacker: str, defender: str,
                       att_weapon: str, att_skill: str, att_magic: str,
                       def_skill: str, def_treasure: str,
                       terrain: str) -> str:
        """生成一轮打斗（攻击+反应+效果）。

        Returns:
            三段合成的打斗描述文本。
        """
        rng = self._wb.get_rng()

        # 准备替换变量（槽位值从 templates/battle_slots 词库发牌；字符段直接来自角色档案）
        vars_ = {
            "attacker": attacker,
            "defender": defender,
            "weapon": att_weapon.strip("☆"),
            "skill": att_skill.strip("☆"),
            "magic": att_magic.strip("☆"),
            "def_skill": def_skill.strip("☆"),
            "treasure": def_treasure.strip("☆"),
            "terrain": terrain,
            "num": str(rng.randint(3, 999)),
            "num2": str(rng.randint(2, 99)),
        }
        for slot_key, pool in self._slot_pools.items():
            vars_[slot_key] = rng.choice(pool)

        # 挑选模板：洗牌发牌，同一池内的模板轮转用尽才重洗
        action_tmpl = self._deal("action", self.ACTION_PATTERNS)
        reaction_tmpl = self._deal("reaction", self.REACTION_PATTERNS)
        effect_tmpl = self._deal("effect", self.EFFECT_PATTERNS)

        # 填充模板（简单字符串替换）
        for key, val in vars_.items():
            action_tmpl = action_tmpl.replace("{" + key + "}", val)
            reaction_tmpl = reaction_tmpl.replace("{" + key + "}", val)
            effect_tmpl = effect_tmpl.replace("{" + key + "}", val)

        return f"{action_tmpl}\n\n{reaction_tmpl}\n\n{effect_tmpl}"

    def generate_battle(self, char_a: dict, char_b: dict,
                        rounds: int = 3, terrain: str = "闪排骨溪") -> str:
        """生成一场完整战斗（多轮打斗）。

        Args:
            char_a, char_b: 两个角色的生成字典
            rounds: 打斗轮数
            terrain: 战斗场地名

        Returns:
            完整战斗段落文本。
        """
        lines = []

        # 战斗开场
        a, b = char_a['name'], char_b['name']
        # ☆ 是词库里的装饰标记，必须在进正文前剥掉——否则会输出
        # 「林朔的☆玉光如幻腿·三变☆直接压了上去」。generate_round 里做了 strip，
        # 开场/收尾此前直接取原字段，是同一个坑的另一处。
        a_weapon = char_a['weapon'].strip('☆')
        a_skill = char_a['skill'].strip('☆')
        openings = [
            f"两人对峙片刻，{a}率先出手！",
            f"战斗一触即发！{a}与{b}同时发动攻击！",
            f"{a}眼中精光一闪，{a_weapon}已在手中！",
            f"{terrain}上的空气先绷紧了半息——然后{a}动了。",
            f"没有喊话，没有试探。{a}的{a_skill}直接压了上去。",
            f"{b}后撤半步，把{terrain}的地形让给了对手。{a}没有客气。",
            f"{a}把重心压低到几乎贴地。下一个呼吸，{a_weapon}已经出鞘。",
            f"谁都没有先说话。{a}和{b}同时判断出了彼此的距离——然后同时踏了出去。",
        ]
        lines.append(self._deal("opening", openings))
        lines.append("")

        # 多轮打斗
        for i in range(rounds):
            if i % 2 == 0:
                att, att_name = char_a, char_a['name']
                defe, def_name = char_b, char_b['name']
            else:
                att, att_name = char_b, char_b['name']
                defe, def_name = char_a, char_a['name']

            round_text = self.generate_round(
                attacker=att_name,
                defender=def_name,
                att_weapon=self._from_arsenal(att, 'weapons', 'weapon'),
                att_skill=self._from_arsenal(att, 'skills', 'skill'),
                att_magic=att['magic'],
                def_skill=self._from_arsenal(defe, 'skills', 'skill'),
                def_treasure=self._from_arsenal(defe, 'treasures', 'treasure'),
                terrain=terrain
            )
            lines.append(f"——第{i+1}回合——")
            lines.append(round_text)
            lines.append("")

        # 战斗收尾
        endings = [
            f"经过{rounds}回合的激战，两人各自后退几步，彼此眼中都多了几分凝重。",
            f"这一战打得天昏地暗，{terrain}之上已是面目全非。",
            "两人相视一眼，同时收招——这一场，平手。",
            f"{rounds}个回合下来，{a}的呼吸乱了，{b}的呼吸也不再匀。谁都没占到便宜。",
            "最后一击落空之后，两人之间空出了三步的距离。没人再上前。",
            f"{terrain}安静下来。只剩下两个人的喘息，一长一短，错着拍子。",
            f"{a}先收了势。{b}盯着他看了很久，才把手里的东西放下。",
            f"打到第{rounds}回合，双方都清楚了一件事——今天分不出胜负。",
        ]
        lines.append(self._deal("ending", endings))

        return "\n".join(lines)
