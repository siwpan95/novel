# -*- coding: utf-8 -*-
"""「三番四震」节奏引擎 —— 网文黄金节奏自动注入模块。

基于调研发现的网文爆款节奏公式：
  三番 = 初番(打破常规) → 深番(认知颠覆) → 终番(降维打击)
  四震 = 怒与虐 → 惊与疑 → 爽与快 → 感与悟

在每个 Save the Cat! 节拍中，根据节拍类型自动注入对应的「震」情绪节点。
"""

import random
from typing import Optional


# ================================================================
# 三番定义：三次递进式翻转变奏
# ================================================================
SANFAN = {
    '初番(打破常规)': {
        'trigger_beats': ['inciting', 'break_1'],
        'description': '开篇打破现状，读者预期被推翻',
        'narrative_injections': [
            '「这不对。」他自言自语。但数据不会错——整张星图上的异常信号，已经扩散到了四个角落。',
            '那一瞬间，他明白了。之前所有的推测——全部错了。不是祂们在渗透万界，是万界一直在渗透祂们。',
            '墟核的面板闪烁了一下——然后跳出了一行林朔从没见过的红色文字。他读了三遍才敢相信自己的眼睛。',
        ],
        'emotional_curve': '惊→疑→兴奋',
    },
    '深番(认知颠覆)': {
        'trigger_beats': ['midpoint', 'break_2'],
        'description': '推翻之前的结论，矛盾从表面对峙转入深层角力',
        'narrative_injections': [
            '白夜的话像一把刀，精准地刺进林朔最不愿意面对的那个问题：如果他记忆中的一切——父母、童年、那间办公室——都是伪造的，那他还剩下什么？',
            '不是偶然。每一次循环、每一个锚定者、每一片碎片——全部是计算好的。源从来就没有沉睡——源从一开始就在观察。',
            '他以为自己在保护万界。现在他知道了——万界不需要保护。万界是一个笼子。而他——是笼子的管理员。',
        ],
        'emotional_curve': '震惊→愤怒→动摇',
    },
    '终番(降维打击)': {
        'trigger_beats': ['all_lost', 'dark_night'],
        'description': '终极爆发，揭开所有伏笔，全局逆转',
        'narrative_injections': [
            '然后他看到了——在归墟最深层的壁画后面，有一扇门。他之前以为那是一堵墙。但现在他知道，46个锚定者的刻痕——不是绝望的遗言。是坐标。他们用47次循环，标记了通往终点的路。',
            '那一刻他明白了。不是他选择成为锚定者——是他创造了自己来成为这个锚定者。闭环的因果中，他是自己的起点，也是万界的终点。',
            '「我不是第47个。」林朔看着白夜。白夜的机械义眼暗了下去——他也看到了。在墟核的最深层数据里，有一个编号：000。第零号锚定者。身份——未记录。创建时间——源纪元元年。',
        ],
        'emotional_curve': '绝望→顿悟→升华',
    },
}


# ================================================================
# 四震定义：四种情绪震波
# ================================================================
SIZHEN = {
    '怒与虐': {
        'trigger_beats': ['inciting', 'debate', 'bad_guys', 'all_lost'],
        'description': '通过不公平遭遇（背叛/嘲讽/误解）建立读者同情',
        'narrative_injections': [
            '「所以你从一开始就在骗我。」林朔的声音很轻——轻得不像在质问。更像是在确认一个他已经知道答案的事实。墟核没有否认。',
            '他看着那群在频道里嘻嘻哈哈的玩家，忽然觉得很累。不是生理上的累——是那种你明明站在悬崖边上，身后的人却在讨论这风景真好的累。',
            '代理人没有攻击。它只是站在那里，等林朔说完所有的话——然后它用林朔母亲的声音，喊了他的小名。那不是他告诉过任何人的名字。',
            '叶琳握住剑的手在发抖——不是因为恐惧。是因为愤怒。这个19岁的少女，在三天之内，失去了师门、失去了师父、然后发现自己正在成为杀死师父的那个东西。',
        ],
    },
    '惊与疑': {
        'trigger_beats': ['opening', 'break_1', 'midpoint', 'dark_night'],
        'description': '好奇心是第一驱动力，让读者不断猜"接下来会怎样"',
        'narrative_injections': [
            '墟核弹出了一条他从未见过的数据流。不是蓝色的——是红色。来源不是归墟——是归墟之外。有人在用归墟的频率发送信号。发送的对象……是那些光点——那些他还没解锁的世界。',
            '那面墙上的刻痕一共有47道。他之前数过。但今天他数的结果是——48。多了一道新的。他的手指停在那道新刻痕上。字迹——是他的。',
            '所有碎片在同一个瞬间震动了一下。不是回收造成的波动——更像是打嗝。或者说——是某种东西在万界的另一端，打了个哈欠。',
        ],
    },
    '爽与快': {
        'trigger_beats': ['fun_games', 'midpoint'],
        'description': '局部反击，让读者获得即时满足',
        'narrative_injections': [
            '三个公会的联手进攻——被挡在了一道看不见的墙外。不是魔法——是林朔用归墟源能在苍云山周围布设的感应结界。他早就料到了代理人会从这里突破。五天的准备，三秒的爆发。',
            '唐川在公屏上发了一个坐标。所有的玩家——肝帝、剧情党、休闲党、甚至那几个搞事党——全部出现在了那个坐标上。代理人看着面前黑压压的一片不死者——第一次，它的影子不跟着它跑了。它在后退。',
            '「你计算了47次循环。」林朔对着混沌海的方向说，「但你漏算了一件事——这一次，我不是一个人。」在他身后，十二个世界的传送门同时打开。',
        ],
    },
    '感与悟': {
        'trigger_beats': ['b_story', 'dark_night', 'break_2'],
        'description': '情感收束，让读者在爽完之后有余韵',
        'narrative_injections': [
            '叶琳没有问那把剑的事。她只是把它放在了苍云派的祠堂里——和师父的牌位放在一起。林朔站在祠堂外面，没有进去。有些事，不需要解释。',
            '那天晚上归墟里很难得地安静。墟核的蓝光柔和地照着石壁上的刻痕——47道旧的，1道新的。林朔在那道新刻痕旁边，用指腹抹了一下。不是要擦掉它——是要记住它的触感。',
            '「你觉得——源还在看着吗？」林朔问。墟核没有回答。但蓝光多了两次闪烁——那是它在犹豫。林朔笑了。在归墟里笑很奇怪——回声在断柱间转了三圈才消散。但他不在乎。今天他有资格笑。',
        ],
    },
}


class RhythmEngine:
    """「三番四震」节奏引擎：自动为章节注入情绪节点。

    Usage:
        engine = RhythmEngine(seed=42)
        injection = engine.get_emotion_beat('midpoint', '惊与疑')
        chapter_text = engine.inject_rhythm(text_lines, 'inciting')
    """

    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self._beat_phase = {}  # 记录每个节拍当前的「番」阶段

    def get_narrative_injection(self, beat: str, phase: str = 'auto') -> Optional[str]:
        """根据当前节拍和「番」阶段，获取叙事注入文本。

        Args:
            beat: Save the Cat! 节拍名
            phase: '初番' | '深番' | '终番' | 'auto'(自动根据节拍选择)
        """
        if phase == 'auto':
            phase = self._resolve_phase(beat)

        if phase in SANFAN:
            return self._rng.choice(SANFAN[phase]['narrative_injections'])
        return None

    def get_emotion_beat(self, beat: str, zhen_type: str = None) -> Optional[str]:
        """获取「震」情绪节点文本。

        Args:
            beat: 当前节拍
            zhen_type: '怒与虐'|'惊与疑'|'爽与快'|'感与悟'，None则自动匹配
        """
        if zhen_type is None:
            zhen_type = self._resolve_zhen(beat)

        if zhen_type in SIZHEN:
            return self._rng.choice(SIZHEN[zhen_type]['narrative_injections'])
        return None

    def _resolve_phase(self, beat: str) -> str:
        """根据节拍自动判断当前属于哪个「番」阶段。"""
        if beat in ('opening', 'theme', 'inciting', 'debate', 'break_1'):
            return '初番(打破常规)'
        elif beat in ('b_story', 'fun_games', 'midpoint', 'bad_guys'):
            return '深番(认知颠覆)'
        else:
            return '终番(降维打击)'

    def _resolve_zhen(self, beat: str) -> str:
        """根据节拍自动匹配最合适的「震」类型。"""
        for zhen_name, config in SIZHEN.items():
            if beat in config['trigger_beats']:
                return zhen_name
        return '惊与疑'  # 默认

    def inject_rhythm(self, text_lines: list, beat: str, frequency: int = 1) -> list:
        """向章节文本中注入「震」情绪节点（轻量版——只在段落边界）。

        Args:
            text_lines: 章节文本行列表
            beat: 当前节拍
            frequency: 每章注入的震次数（默认1次，轻量管线）

        Returns:
            注入了情绪节点的文本行列表
        """
        if not text_lines or frequency <= 0:
            return text_lines

        zhen_type = self._resolve_zhen(beat)
        injection = self.get_emotion_beat(beat, zhen_type)
        if not injection:
            return text_lines

        result = list(text_lines)

        # 找段落边界（连续空行或章节分隔符的位置）
        boundary_positions = []
        for i, line in enumerate(result):
            stripped = line.strip()
            # 空行作为候选注入点
            if stripped == '' and i > 2 and i < len(result) - 2:
                boundary_positions.append(i)

        if not boundary_positions:
            # 没有空行，插在尾部
            result.append('')
            result.append(injection)
            return result

        # 选择靠近黄金分割位置（2/3处）的边界点
        target = len(result) * 2 // 3
        best_pos = min(boundary_positions, key=lambda p: abs(p - target))

        # 在边界处注入
        result.insert(best_pos + 1, injection)
        return result

    def get_sanfan_emotional_curve(self, beat: str) -> str:
        """获取当前节拍对应的「三番」情感曲线描述。"""
        phase = self._resolve_phase(beat)
        return SANFAN.get(phase, {}).get('emotional_curve', '中性')

    def get_zhen_description(self, beat: str) -> str:
        """获取当前节拍匹配的「震」类型及描述。"""
        zhen_type = self._resolve_zhen(beat)
        desc = SIZHEN.get(zhen_type, {}).get('description', '')
        return f'{zhen_type}: {desc}'

    def get_all_sanfan_for_beat(self, beat: str) -> list:
        """获取适用于当前节拍的所有「番」类型。"""
        phase = self._resolve_phase(beat)
        return [
            {
                'phase': phase,
                'description': SANFAN[phase]['description'],
                'curve': SANFAN[phase]['emotional_curve'],
                'sample': self._rng.choice(SANFAN[phase]['narrative_injections']),
            }
        ]
