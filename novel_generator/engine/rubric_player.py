# -*- coding: utf-8 -*-
"""P2: 质量评估引擎 + 玩家类型建模。

评估引擎：5维度自动打分，低于阈值自动触发局部重写。
玩家类型：5种行为原型，在不同场景按类型权重分配对话和行为倾向。
"""

import random
import re


# ================================================================
# 1. 质量评估引擎 (Rubric Engine)
# ================================================================

# 5维评分标准
RUBRIC_DIMENSIONS = {
    '因果一致性': {
        'weight': 0.25,
        'description': '本章事件是否基于上一章状态自然延伸',
        'checks': ['事件与前章有因果关联', '角色行为符合当前状态', '无时间线矛盾'],
    },
    '节奏感': {
        'weight': 0.20,
        'description': '短句/中句/长句分配是否符合节拍要求',
        'checks': ['句长有变化不是均匀分布', '紧张段落短句多', '有空白/停顿制造冲击'],
    },
    '对话自然度': {
        'weight': 0.20,
        'description': '对话是否有潜台词/角色辨识度/推进情节',
        'checks': ['遮住名字能分辨谁在说话', '每句对话有目的', '对话中有非语言反应'],
    },
    '情感曲线': {
        'weight': 0.20,
        'description': '本章是否有清晰的情感走向',
        'checks': ['有情感起点和终点', '情感变化有触发事件', '不止一种情绪'],
    },
    '去AI味': {
        'weight': 0.15,
        'description': '是否规避了AI常见痕迹',
        'checks': ['无不禁/忍不住/一股XX涌上心头', '无每段均匀3-4句', '有身体感知描写'],
    },
}

# AI味高频词黑名单（32词，分3级严重度）
AI_BLACKLIST = [
    # L1 重度：几乎只有AI会用（扣分×1.5）
    ('不禁', 1.5), ('忍不住', 1.5), ('一股', 1.5), ('涌上心头', 1.5),
    ('不由自主地', 1.5), ('下意识地', 1.5), ('他深知', 1.5),
    ('毋庸置疑', 1.5), ('心中暗道', 1.5), ('不由得', 1.5),
    # L2 中度：模板化表达（扣分×1.0）
    ('与此同时', 1.0), ('另一边', 1.0), ('突然之间', 1.0),
    ('在这一刻', 1.0), ('毫无疑问', 1.0), ('显而易见', 1.0),
    ('只见', 1.0), ('但见', 1.0), ('说时迟那时快', 1.0),
    ('电光火石之间', 1.0), ('顿时', 1.0), ('瞬间（作独立过渡词时）', 1.0),
    ('浑身一震', 1.0), ('面色一变', 1.0), ('眼神一凛', 1.0),
    ('目光一凝', 1.0),
    # L3 轻度：高频但非纯AI味（扣分×0.5）
    ('缓缓', 0.5), ('淡淡', 0.5), ('微微', 0.5), ('轻轻', 0.5),
    ('深吸一口气', 0.5), ('心中涌起', 0.5),
]

# L1/L2/L3 词条快速查找（仅取词条本身）
AI_BLACKLIST_WORDS = [w for w, _ in AI_BLACKLIST]

# ================================================================
# Authentic-Voice 7原则检测规则
# ================================================================
AUTHENTIC_VOICE_RULES = {
    '不完整原则': {
        'weight': 1.0,
        'description': '对话中应该有打断/句子不说完/话说一半',
        'positive_patterns': [
            r'[……]{2,}',           # 省略号
            r'[\u2014\u2015]{2,}',  # 破折号（话说一半）
            r'[你我这][\u4e00-\u9fff]{0,3}[——\u2014]',  # 被打断
        ],
        'negative_flags': [],  # 没有就没有，不惩罚
    },
    '重复原则': {
        'weight': 0.8,
        'description': '关键情绪词应该重复出现',
        'positive_patterns': [
            r'([\u4e00-\u9fff]{2,4})。\1',  # 词。词 的重复
        ],
    },
    '跑题原则': {
        'weight': 0.6,
        'description': '对话中偶尔插入无关的话',
        'positive_patterns': [
            r'(对了|话说|想起来了|说到这个|等一下|等等|不对)',
        ],
    },
    '延迟原则': {
        'weight': 0.8,
        'description': '不立刻回答问题，先沉默或做其他事',
        'positive_patterns': [
            r'(沉默|半晌|良久|没说话|没有回答|别过头|转过身|停顿)',
        ],
        'negative_flags': [],
    },
    '错误原则': {
        'weight': 0.5,
        'description': '角色偶尔说错话然后纠正自己',
        'positive_patterns': [
            r'(不对|不是|我说错了|重新说|更正)',
        ],
    },
    '物理性原则': {
        'weight': 1.2,
        'description': '正文中应该出现生理感知（渴/饿/累/酸/疼/冷/热）',
        'positive_patterns': [
            r'(眼皮|肩膀|指节|嘴唇|后颈|胃|喉咙|太阳穴|手心|膝盖|脚踝)',
            r'(酸|麻|疼|干|冷|热|累|饿|渴|困|恶心|晕)',
        ],
        'min_matches': 2,  # 每章至少2处物理感知
    },
    '当下原则': {
        'weight': 0.7,
        'description': '记忆应该是碎片化的、跳跃的，不是完整精确回忆',
        'positive_patterns': [],
        'negative_flags': [
            r'(清晰[地]?记得|准确[地]?回忆|那一刻的每一个细节)',
        ],
    },
}

# 情感词库（用于情感曲线评估）
EMOTION_KEYWORDS = {
    '恐惧': ['怕', '恐惧', '害怕', '寒', '抖', '颤', '凉'],
    '愤怒': ['怒', '恨', '气', '咬牙', '攥拳', '火焰'],
    '悲伤': ['泪', '哭', '难过', '失去', '再也', '痛'],
    '希望': ['光', '希望', '可以', '也许', '还能', '活'],
    '绝望': ['崩塌', '完了', '不行', '做不到', '放弃'],
    '坚定': ['必须', '一定', '不能', '无论如何', '扛'],
    '困惑': ['为什么', '不知道', '不确定', '奇怪', '不对'],
    '温暖': ['笑', '谢谢', '好', '够', '陪', '帮'],
}


class RubricEngine:
    """5维质量评估引擎。"""

    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self._history = []

    def evaluate(self, text: str, beat: str, prev_chapter_events: list = None) -> dict:
        """对章节文字进行5维评分。

        Returns:
            {dimension: score, 'total': weighted_score, 'verdict': pass/rewrite/partial}
        """
        scores = {}

        # 1. 因果一致性
        scores['因果一致性'] = self._score_causality(text, prev_chapter_events)

        # 2. 节奏感
        scores['节奏感'] = self._score_rhythm(text, beat)

        # 3. 对话自然度
        scores['对话自然度'] = self._score_dialogue(text)

        # 4. 情感曲线
        scores['情感曲线'] = self._score_emotion(text)

        # 5. 去AI味
        scores['去AI味'] = self._score_deai(text)

        # 加权总分
        total = sum(
            scores[dim] * RUBRIC_DIMENSIONS[dim]['weight']
            for dim in RUBRIC_DIMENSIONS
        )

        # 判定
        if total >= 7.5:
            verdict = 'pass'
        elif total >= 5.0:
            verdict = 'partial_rewrite'
        else:
            verdict = 'full_rewrite'

        result = {
            'scores': scores,
            'total': round(total, 1),
            'verdict': verdict,
            'issues': self._find_issues(text, scores),
        }
        self._history.append(result)
        return result

    def _score_causality(self, text: str, prev_events: list) -> float:
        base = 6.0
        # 检查是否有引用前文事件的关键词
        if prev_events:
            event_keywords = set()
            for ev in prev_events:
                for word in re.findall(r'[\u4e00-\u9fff]{2,4}', ev):
                    event_keywords.add(word)
            matches = sum(1 for kw in event_keywords if kw in text)
            base += min(matches * 0.5, 3.0)
        # 检查是否有"因为""所以""于是"等因果连接
        cause_words = len(re.findall(r'(因为|所以|于是|因此|导致|结果|原因|由于)', text))
        base += min(cause_words * 0.3, 1.0)
        return min(base, 10.0)

    def _score_rhythm(self, text: str, beat: str) -> float:
        base = 6.0
        # 按句号拆分，检查句长分布
        sentences = text.replace('！', '。').replace('？', '。').split('。')
        sentences = [s for s in sentences if s.strip()]

        if len(sentences) < 3:
            return 5.0

        lengths = [len(s) for s in sentences]
        # 短句比例
        short_pct = sum(1 for l in lengths if l < 15) / len(lengths)
        # 长句比例
        long_pct = sum(1 for l in lengths if l > 60) / len(lengths)

        # 如果全是中句（均匀感），扣分
        if 0.7 < short_pct < 0.9:
            base -= 1.5
        if long_pct > 0.7:
            base -= 0.5

        # 有单字独段加分
        if any(len(s.strip()) <= 3 for s in sentences):
            base += 1.5

        # 有空白行（段落分隔）加分
        blank_lines = text.count('\n\n')
        base += min(blank_lines * 0.3, 2.0)

        return min(base, 10.0)

    def _score_dialogue(self, text: str) -> float:
        base = 5.0
        # 检查是否有对话
        re.findall(r'[「「](.+?)[」」]', text)
        dialogue_chars = text.count('「') + text.count('」')

        if dialogue_chars < 4:
            return 5.0  # 没有足够对话，中性分

        # 检查对话标签密度
        said_tags = len(re.findall(r'(说|道|问|答|喊|叫|骂)', text))
        tag_ratio = said_tags / max(dialogue_chars / 4, 1)

        if tag_ratio > 0.6:
            base -= 1.5  # 对话标签太多
        elif tag_ratio < 0.3:
            base += 1.0  # 对话标签少，好

        # 检查是否有非语言反应（动作穿插在对话中）
        actions_in_dialogue = len(re.findall(
            r'[。！？]\s*[他她它][\u4e00-\u9fff]{1,10}(了|着|在)', text))
        base += min(actions_in_dialogue * 0.5, 2.0)

        return min(base, 10.0)

    def _score_emotion(self, text: str) -> float:
        base = 5.0
        found_emotions = set()
        for emotion, keywords in EMOTION_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    found_emotions.add(emotion)
                    break

        # 有情绪变化加分
        if len(found_emotions) >= 3:
            base += 3.0
        elif len(found_emotions) >= 2:
            base += 2.0
        elif len(found_emotions) == 1:
            base += 0.5
        else:
            base -= 2.0  # 完全没有情绪描写

        return min(base, 10.0)

    def _score_deai(self, text: str) -> float:
        """去AI味评分：三级严重度黑名单 + Authentic-Voice 7原则检测。"""
        base = 8.0

        # --- Phase 1: 三级AI黑名单检查 ---
        total_penalty = 0.0
        hit_details = []
        for word, severity in AI_BLACKLIST:
            count = text.count(word)
            if count > 0:
                penalty = count * 0.6 * severity
                total_penalty += penalty
                hit_details.append(f'{word}×{count}(-{penalty:.1f})')

        base -= min(total_penalty, 5.0)

        # --- Phase 2: 物理感知描写检测（好的信号）---
        physical_markers = [
            '眼皮', '肩膀', '指节', '嘴唇', '后颈', '胃', '喉咙', '太阳穴',
            '手心', '膝盖', '脚踝', '脊椎', '后脑勺', '胸口',
            '酸', '麻', '疼', '干', '冷', '热', '跳', '颤',
            '发凉', '发热', '发麻', '发酸', '发紧',
        ]
        physical_count = sum(1 for m in physical_markers if m in text)
        base += min(physical_count * 0.4, 2.0)

        # --- Phase 3: Authentic-Voice 7原则检测 ---
        av_score = self._score_authentic_voice(text)
        base += av_score  # -1.0 ~ +2.0

        return max(0, min(base, 10.0))

    def _score_authentic_voice(self, text: str) -> float:
        """Authentic-Voice 7原则评分。"""
        import re
        score = 0.0
        details = []

        for rule_name, rule in AUTHENTIC_VOICE_RULES.items():
            weight = rule['weight']

            # 检查正面模式（加分）
            pos_matches = 0
            for pattern in rule.get('positive_patterns', []):
                matches = re.findall(pattern, text)
                pos_matches += len(matches)

            # 检查负面标志（减分）
            neg_matches = 0
            for pattern in rule.get('negative_flags', []):
                matches = re.findall(pattern, text)
                neg_matches += len(matches)

            min_req = rule.get('min_matches', 1)
            if pos_matches >= min_req:
                score += weight * 0.15 * min(pos_matches, 3)
                details.append(f'+{rule_name}({pos_matches}处)')
            elif neg_matches > 0:
                score -= weight * 0.1 * neg_matches
                details.append(f'-{rule_name}(负面{neg_matches}处)')

        return max(-1.0, min(score, 2.0))

    def _find_issues(self, text: str, scores: dict) -> list:
        """找出需要改进的具体问题。"""
        issues = []
        for dim, score in scores.items():
            if score < 6.0:
                issues.append({
                    'dimension': dim,
                    'score': round(score, 1),
                    'suggestion': self._get_suggestion(dim, score),
                })
        return issues

    def _get_suggestion(self, dimension: str, score: float) -> str:
        suggestions = {
            '因果一致性': '增加与前章事件的显式关联——让角色想起/引用之前发生的事情',
            '节奏感': '在当前段落后插入1-2个短句（5字以内）或单字独段打破均匀感',
            '对话自然度': '删减对话标签（说/道），用动作替代；给不同角色加上口癖差异',
            '情感曲线': '增加角色的身体反应描写（不是内心独白，是生理变化）',
            '去AI味': '检查不禁/忍不住/一股等AI高频词；增加具体的物理传感描写',
        }
        return suggestions.get(dimension, '需要改进')


# ================================================================
# 2. 玩家类型建模
# ================================================================

PLAYER_ARCHETYPES = {
    '肝帝': {
        'weight': 0.30,
        'traits': ['冲进度', '写攻略', '刷榜', '效率至上', '鄙视休闲玩法'],
        'dialogue_style': '短促有力，爱用叹号，「冲！」「干就完了！」「攻略已出」',
        'action_tendency': {
            'explore': 0.15, 'battle': 0.50, 'social': 0.10,
            'chaos': 0.05, 'craft': 0.10, 'observe': 0.10,
        },
        'sample_names': ['肝帝老王', '熬夜战神', '效率至上', '冲分机器'],
    },
    '剧情党': {
        'weight': 0.20,
        'traits': ['深挖NPC背景', '拼凑世界真相', '截图对话', '写同人'],
        'dialogue_style': '长句居多，爱引用NPC原话，「根据第3章那个NPC说的……」',
        'action_tendency': {
            'explore': 0.30, 'battle': 0.10, 'social': 0.15,
            'chaos': 0.05, 'craft': 0.10, 'observe': 0.30,
        },
        'sample_names': ['考据狂魔', 'NPC恋爱脑', '剧情侦探', '世界观察者'],
    },
    '社交型': {
        'weight': 0.20,
        'traits': ['建公会', '撮合队友', '调解纠纷', '组织活动'],
        'dialogue_style': '话多，爱用@，「兄弟们」「来来来」「听我说」',
        'action_tendency': {
            'explore': 0.10, 'battle': 0.15, 'social': 0.50,
            'chaos': 0.10, 'craft': 0.10, 'observe': 0.05,
        },
        'sample_names': ['公会吉祥物', '社交达人', '气氛组组长', '万人迷'],
    },
    '搞事党': {
        'weight': 0.15,
        'traits': ['钻漏洞', 'PVP偷袭', '测试NPC反应极限', '制造混乱'],
        'dialogue_style': '阴阳怪气+挑衅，「嘿嘿嘿」「就这？」「兄弟们我有个大胆的想法」',
        'action_tendency': {
            'explore': 0.15, 'battle': 0.25, 'social': 0.05,
            'chaos': 0.45, 'craft': 0.05, 'observe': 0.05,
        },
        'sample_names': ['混沌恶', '乐子人', '搞事不嫌大', 'Bug猎人'],
    },
    '休闲党': {
        'weight': 0.15,
        'traits': ['看风景', '截图', '钓鱼', '不卷', '享受氛围'],
        'dialogue_style': '佛系，爱发颜文字，「好美哦~」「有人一起散步吗」',
        'action_tendency': {
            'explore': 0.30, 'battle': 0.05, 'social': 0.20,
            'chaos': 0.05, 'craft': 0.15, 'observe': 0.25,
        },
        'sample_names': ['咸鱼飞飞', '佛系玩家', '风景摄影师', '不肝不氪'],
    },
}


class PlayerArchetypeEngine:
    """玩家类型引擎：按5种行为原型分配对话和行为倾向。"""

    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self._type_weights = {
            name: info['weight']
            for name, info in PLAYER_ARCHETYPES.items()
        }

    def generate_player(self) -> dict:
        """生成一个随机类型玩家。"""
        types = list(self._type_weights.keys())
        weights = list(self._type_weights.values())
        ptype = self._rng.choices(types, weights=weights, k=1)[0]
        info = PLAYER_ARCHETYPES[ptype]
        return {
            'type': ptype,
            'name': self._rng.choice(info['sample_names']),
            'traits': info['traits'],
            'dialogue_style': info['dialogue_style'],
            'action_tendency': info['action_tendency'],
        }

    def generate_player_action(self, player: dict, context: str = 'general') -> str:
        """根据玩家类型生成行为描述。"""
        ptype = player['type']
        info = PLAYER_ARCHETYPES.get(ptype, PLAYER_ARCHETYPES['休闲党'])
        tendencies = info['action_tendency']
        actions = list(tendencies.keys())
        probs = list(tendencies.values())
        action = self._rng.choices(actions, weights=probs, k=1)[0]

        action_descriptions = {
            'explore': [
                '%s独自一人钻进了地图边缘的迷雾区' % player['name'],
                '%s发现了一片从未有人到过的废墟' % player['name'],
                '%s在地图上标记了三个新的能量异常点' % player['name'],
            ],
            'battle': [
                '%s正在单刷稀有怪——已经是第7次尝试了' % player['name'],
                '%s的公会正在组织一次世界BOSS讨伐' % player['name'],
                '%s刚刚刷新了竞速排行榜' % player['name'],
            ],
            'social': [
                '%s在公会频道组织了一场拍卖会' % player['name'],
                '%s正在调解两个成员之间的装备纠纷' % player['name'],
                '%s发了一个招募帖，想组固定队' % player['name'],
            ],
            'chaos': [
                '%s发现了一个可以让NPC循环对话的bug，正在测试极限' % player['name'],
                '%s把一个NPC的帽子偷了，正戴着到处炫耀' % player['name'],
                '%s在安全区外袭击了一个落单玩家——PVP开关是他自己设的' % player['name'],
            ],
            'craft': [
                '%s花了三个小时调试装备附魔的参数' % player['name'],
                '%s正在画新手村的详细地图' % player['name'],
                '%s在论坛写了一篇万字攻略' % player['name'],
            ],
            'observe': [
                '%s坐在苍云山顶看了一个小时的云' % player['name'],
                '%s发现了一个NPC的日常行动路线——连他几点吃饭都记下来了' % player['name'],
                '%s在研究归墟壁画上的符号——他在现实里是个考古专业的学生' % player['name'],
            ],
        }

        pool = action_descriptions.get(action, action_descriptions['explore'])
        return self._rng.choice(pool)

    def player_chat_line(self, player: dict, topic: str = 'general') -> str:
        """根据玩家类型生成一句聊天消息。"""
        ptype = player['type']
        name = player['name']

        chat_templates = {
            '肝帝': {
                'general': ['冲！', '攻略已出，需要的看群文件', '今天的目标是升到20级'],
                'battle': ['BOSS还剩30%血！来人！！', '谁有那个稀有材料的坐标？'],
                'discovery': ['等等，这个数值不对——程序员的直觉', '我测了三遍，这个概率不是随机的'],
            },
            '剧情党': {
                'general': ['这个游戏的背景故事好深……', '有人整理过世界观时间线吗？'],
                'NPC': ['叶琳的背景故事有更新吗？', '我读了苍云派遗址的所有碑文'],
                'discovery': ['归墟壁画上的符号和碎片上的铭文是同一个体系', '灰衣人——我找到他了！'],
            },
            '社交型': {
                'general': ['兄弟们周末有活动吗？', '新手可以加公会，有导师带的'],
                'battle': ['3队缺个治疗！来的@我！', '今晚八点公会战，大家都上线啊'],
                'discovery': ['有人一起去探索新区域吗？组个观光团', '谁要组固定队？现在队伍缺两人'],
            },
            '搞事党': {
                'general': ['嘿嘿嘿，我发现了一个好玩的东西', '有没有人想试试——算了不说了太危险'],
                'battle': ['偷袭成功！哈哈哈哈', '谁把PVP关了？开回来！'],
                'discovery': ['这个墙能穿模！我卡进去了！！', '如果同时给NPC送两个相反任务的道具会怎样……'],
            },
            '休闲党': {
                'general': ['今天又找到了一处好风景~', '有人一起钓鱼吗？'],
                'battle': ['我就看看不说话', '你们打架的时候能换个地方吗——我在截图'],
                'discovery': ['这个世界的月亮比地球的亮好多', '有人在废土世界听到风声吗？超级恐怖的'],
            },
        }

        templates = chat_templates.get(ptype, chat_templates['休闲党'])
        topic_templates = templates.get(topic, templates['general'])
        return '%s：%s' % (name, self._rng.choice(topic_templates))

    def get_type_distribution(self) -> dict:
        """获取当前玩家类型的权重分布。"""
        return dict(self._type_weights)


# ================================================================
# 3. 玩家名场面生成器（基于第四天灾爆款桥段）
# ================================================================

FAMOUS_SCENES = {
    '误把BOSS当NPC': [
        '{player}发现了一个全身散发着黑气的NPC——他以为那是隐藏时装。他上去搭了十五分钟的讪，直到那个NPC——其实是一个来自混沌海的代理人——终于用低沉的声音说了一句：你在跟我说话？',
        '{player}对着一个明显是大BOSS的角色说：你好，请问新手村怎么走？那个存在活了47000年，第一次不知道该怎么回答。',
    ],
    '游戏漏洞造永动机': [
        '{player}发现如果把两件装备以特定顺序放进交易窗口然后取消，会复制装备。他试了三次——成功了。他用了六个小时，复制了四百件装备。整个服务器的经济体系在一天之内崩塌了。林朔花了三天修复这个bug。{player}被封了七天——但他在第七天之后，已经找到了另一个漏洞。',
        '这个世界的物理规则比任何游戏都真实——但再真实的规则也有漏洞。{player}用三条绳子和两个滑轮造出的装置，在理论上应该什么用都没有——但它真的可以让一块石头悬浮半空。林朔看着墟核的分析报告：这不是bug，是世界规则本身存在弹性。{player}无意中发现了源在设计万界时留下的一个设计余量。',
    ],
    '全服排队领道具': [
        '有人发现苍云山的某个NPC每天早晨会在村口放三十份免费的粥——本来只是游戏细节。但粥喝下去之后会获得一个持续一小时的"饱食"buff——提升5%经验获取。于是每天早晨五点，村口就有两百个玩家在排队。有人开始卖排队的位置。有人搞了预约系统。有人在粥里下毒——只是为了看NPC的反应。',
    ],
    '把商业模型搬进游戏': [
        "{player}在武侠世界开了第一家\"现代服务公司\"。经营范围包括：代练（帮新手打怪）、代购（从NPC那里买药草然后加价卖）、快递（利用公会传送阵帮人运货）、保险（交一笔钱，死了帮你捡装备）、经纪（帮高端玩家找队伍）。开业第一周，营收超过武侠世界三个月的GDP。当地商会来找林朔投诉。林朔不知道该怎么跟他们解释\"自由市场\"这个概念。",
    ],
    '玩家组织大型社会实验': [
        '一个叫\'社会学研究生\'的玩家发了一个帖子：我们来试试这个世界的NPC到底有多智能。于是三天之内，全服玩家开始执行一套精心设计的测试流程——在不同时间、不同地点、给不同NPC送不同的礼物，然后记录他们的反应。实验结果让这个人写了一篇论文。而林朔看完那篇论文之后，失眠了整整一夜——因为玩家们无意中测试出了一个事实：NPC的记忆不是独立存储的。他们共享记忆。所有的NPC——是同一个意识的不同投影。',
    ],
    '玩家试图和NPC谈恋爱': [
        '{player}对叶琳发起了追求——用的是地球上最老套的方法：每天送她一朵花、在她练剑的时候在旁边站岗、写了三封情书（每封都超过两千字）。叶琳的反应让林朔意外——她没有生气，没有感动，只是一脸困惑地问：天人为什么对人类的繁衍方式这么感兴趣？全服在频道里笑了一整天。{player}没有放弃——他把这句话当成了一种鼓励。',
    ],
    '玩家发动无产阶级革命': [
        '一群读了太多书的玩家在武侠世界发起了一场革命。他们的核心诉求是——废除门派制度，建立民主公会。他们把一个铁匠铺改造成了演讲台，每天对着路过的NPC发表长篇大论——内容包括自由、平等、博爱、以及要求所有门派公开武功秘籍。NPC们听不懂。但林朔看懂了——这群人不是在玩游戏，他们是在把游戏当成一个可以实践理想的乌托邦。他不知道自己该为此感到欣慰还是恐惧。',
    ],
}


class FamousSceneEngine:
    """玩家名场面生成器：基于第四天灾爆款桥段模板库。"""

    def __init__(self, seed=None):
        self._rng = random.Random(seed)

    def generate_scene(self, scene_type: str = None, player_name: str = None) -> str:
        """生成一个玩家名场面。

        Args:
            scene_type: 场景类型，None则随机选
            player_name: 主角玩家名，None则随机生成
        """
        if player_name is None:
            player_names = ['欧皇是我', '一剑仙人跪', '肝帝老王', '咸鱼飞飞',
                           '混沌恶', '考据狂魔', '社会学研究生', '奸商一号']
            player_name = self._rng.choice(player_names)

        if scene_type is None:
            scene_type = self._rng.choice(list(FAMOUS_SCENES.keys()))

        templates = FAMOUS_SCENES.get(scene_type, FAMOUS_SCENES['误把BOSS当NPC'])
        template = self._rng.choice(templates)
        return template.format(player=player_name)

    def generate_random_scene(self) -> str:
        """生成随机类型的名场面。"""
        return self.generate_scene()

    def list_scene_types(self) -> list:
        """列出所有可用的名场面类型。"""
        return list(FAMOUS_SCENES.keys())

    def generate_scene_block(self, count: int = 3) -> str:
        """生成多个名场面的文本块。"""
        scenes = [self.generate_scene() for _ in range(count)]
        return '\n\n'.join(f'【名场面{i+1}】\n{s}' for i, s in enumerate(scenes))
