# -*- coding: utf-8 -*-
"""Step 2 v2: 事件展开引擎（句子类型感知）+ Step 3: 世界差异化词库。

v2 改进：
- 句子类型分类：动作/叙事/心理/环境，分别套用不同模板族
- 避免「膝盖已经贡献榜更新了排名了」这类模板不匹配问题
- 弱势节拍（fun_games/debate/b_story）增加人物内心展开
"""

import random


# ================================================================
# 句子类型分类器
# ================================================================

ACTION_VERBS = ['冲', '跑', '站', '握', '按', '跳', '撕', '推', '拉', '挥', '踢',
                '走', '爬', '抓', '挡', '砍', '刺', '击', '射', '落', '升', '降',
                '取出', '打开', '关上', '按下', '穿过', '撕裂', '举起', '放下']
NARRATIVE_MARKERS = ['发布', '上线', '建立', '更新', '记录', '整理', '发现', '调查',
                     '开始', '结束', '完成', '触发', '生成', '解锁', '回收']
PSYCH_MARKERS = ['觉得', '认为', '知道', '意识到', '想起', '注意到', '怀疑', '害怕',
                 '担心', '犹豫', '决定', '选择', '理解', '明白', '感受到']
ENV_MARKERS = ['闪烁', '发光', '震动', '响起', '扩大', '缩小', '改变', '裂开', '崩塌']


def classify_sentence(skeleton: str) -> str:
    """分类骨架句类型。"""
    for v in ACTION_VERBS:
        if v in skeleton and len(skeleton) < 20:
            return 'action'
    for m in PSYCH_MARKERS:
        if m in skeleton:
            return 'psychological'
    for m in NARRATIVE_MARKERS:
        if m in skeleton:
            return 'narrative'
    for m in ENV_MARKERS:
        if m in skeleton:
            return 'environmental'
    return 'action'  # 默认按动作处理


# ================================================================
# 4套模板族
# ================================================================

ACTION_TEMPLATES = [
    # 身体反应 + 环境（增加多样性，减少"他没有想/不是故意的"重复）
    '{name}的{body_part}在那瞬间{reaction}。不是故意的——身体先于思维做出了反应。{detail}。',
    '他没有想。{body_part}已经做出了选择。{detail}——这是他事后才注意到的，当时根本顾不上。',
    '那一刻{name}的{body_part}{reaction}。周围的一切都在{verb}——只有他定格在{action}的瞬间。',
    # 新增3个变体，分散"他没有想"的重复
    '{name}甚至没意识到自己在动。{body_part}{reaction}的过程完全是自动的——就像呼吸。{detail}。',
    '{action}发生的时候，{name}的{body_part}{reaction}。事后回想——那个反应是对的。本能有时候比分析快。',
    '身体的记忆比大脑诚实。{name}的{body_part}{reaction}的时候，脑子还在处理信息。{detail}。',
]

NARRATIVE_TEMPLATES = [
    # 事件意义 + 观察
    '{name}看着{action}——不是在看事件的表象，是在看它的余波。{detail}。',
    '没有人注意到{action}的真正含义。除了{name}。他的{body_part}{reaction}——那是一个策划做了十年的身体记忆：当系统里出现了一个不该出现的变量，身体会比脑子先知道。',
    '{action}。这个事件的形状在{name}的心里慢慢成型——不是通过推理，是通过{detail}。',
]

PSYCH_TEMPLATES = [
    # 内心活动展开
    '{name}觉得自己的思维像被{verb}了一下。{action}——这个认知不是突然来的，是一点点渗透进来的，像水渗进石缝。{detail}。',
    '{action}。{name}没有把这个念头说出口。他只是让它停在{body_part}的位置，不上不下——像一颗还没吞下去的药。',
    '他应该{reaction}的。但他没有。{action}带来的不是结论——是一个新的问题。一个他之前没想过要问的问题。{detail}。',
]

ENV_TEMPLATES = [
    # 环境变化 + 氛围
    '{action}的那一瞬间，周围的{adjective}质感发生了变化。不是光变暗了——是{detail}。{name}的{body_part}{reaction}。',
    '{action}。{name}的余光捕捉到了{detail}——不是重要信息，但他知道它会成为重要信息。他的直觉很少错过这种碎片。',
]

EXPANSION_DETAILS = {
    'body_parts': ['手指', '肩膀', '后颈', '眼皮', '虎口', '膝盖', '太阳穴', '脊柱', '掌心', '脚底'],
    'reactions': ['先一步做出了判断', '绷紧了一瞬', '本能地松开', '在那一秒背叛了他的思维', '不受控制地轻颤', '比脑子快了两秒'],
    'verbs': ['凝结', '膨胀', '瓦解', '重组', '停摆', '加速', '变轻', '变重'],
    'adjectives': ['锋利的', '黏稠的', '冰冷的', '干燥的', '沉重的', '模糊的', '清晰的', '陌生的'],
    'details': [
        '画面的边缘在微微发红——不是光，是充血',
        '他听到自己的呼吸——节奏不对，像有人在呼吸他',
        '汗珠从额角滑下来——他感觉到的不是湿，是冷',
        '指甲掐进掌心的位置刚好是上次留下的疤',
        '他眨了眨眼——这个动作在这个场景里显得不合时宜',
        '时间感在这一刻断裂了——他不知道过了多久',
        '那个瞬间被拉长了——长到他能数清自己心跳的次数',
    ],
}

# 弱势节拍（b_story/fun_games/debate）专用的人物内心展开
INTERIORITY_TEMPLATES = [
    '{name}忽然想到一件事。不是关于{action}——是关于在那之前的。那个细节他之前看到了，但没往心里去。现在它浮上来了，{detail}。',
    '这种事——{action}——如果放在一周前，{name}的反应会完全不同。一周前他还在{adjective}的世界里。现在他连那个世界的轮廓都快记不清了。',
    '{name}在心里画了一条线。一边是{action}——可以接受的。另一边是——他还没想好。但线的位置，每次他画的时候都在往另一边挪。',
    '有时候{name}会忘记自己不是这里的人。{action}——这个场景太日常了，日常到他有一瞬间真的以为自己是这群年轻人里的一员。然后墟核的面板弹出来——提醒他他不是。',
]


# ================================================================
# v2 展开引擎
# ================================================================

class ExpansionEngine:
    """事件展开引擎 v2：句子类型感知 + 4模板族。"""

    def __init__(self, seed=None):
        self._rng = random.Random(seed)

    def expand(self, skeleton: str, beat: str, quantity: int = 1) -> str:
        """将骨架句展开为场景段落（句子类型感知）。"""
        sent_type = classify_sentence(skeleton)
        template_pool = {
            'action': ACTION_TEMPLATES,
            'narrative': NARRATIVE_TEMPLATES,
            'psychological': PSYCH_TEMPLATES,
            'environmental': ENV_TEMPLATES,
        }.get(sent_type, ACTION_TEMPLATES)

        weak_beats = ('b_story', 'fun_games', 'debate', 'theme')
        if beat in weak_beats and self._rng.random() < 0.5:
            # 50%概率使用内心展开
            template_pool = INTERIORITY_TEMPLATES + template_pool

        parts = []
        for _ in range(quantity):
            tmpl = self._rng.choice(template_pool)
            expanded = tmpl.format(
                name=self._rng.choice(['他', '林朔']),
                body_part=self._rng.choice(EXPANSION_DETAILS['body_parts']),
                action=skeleton[:20] + ('…' if len(skeleton) > 20 else ''),
                reaction=self._rng.choice(EXPANSION_DETAILS['reactions']),
                verb=self._rng.choice(EXPANSION_DETAILS['verbs']),
                adjective=self._rng.choice(EXPANSION_DETAILS['adjectives']),
                detail=self._rng.choice(EXPANSION_DETAILS['details']),
            )
            parts.append(expanded)
        return '\n'.join(parts)

    def inject_expanded_events(self, lines: list, beat: str, key_sentences: list) -> list:
        """在一章的事件节点上注入展开段落。

        Args:
            lines: 章节行列表
            beat: 节拍类型
            key_sentences: 需要展开的关键事件描述列表 [(骨架句, 展开数量), ...]

        Returns:
            扩展后的行列表。
        """
        result = list(lines)
        for skeleton, count in key_sentences:
            expanded = self.expand(skeleton, beat, count)
            # 找到合适的插入位置：在包含关键句附近的地方
            keywords = [w for w in skeleton if '\u4e00' <= w <= '\u9fff']
            match_key = ''.join(keywords[:3]) if len(keywords) >= 3 else skeleton[:3]
            insert_pos = len(result) // 2  # default: middle
            # Try to find a nearby position
            for j, line in enumerate(result):
                if match_key in line:
                    insert_pos = j + 1
                    break
            result.insert(min(insert_pos, len(result)), '')
            result.insert(min(insert_pos + 1, len(result)), expanded)
        return result

    def inject_interiority(self, lines: list, beat: str, count: int = 2) -> list:
        """弱势节拍专用：注入人物内心独白式展开。"""
        weak_beats = ('b_story', 'fun_games', 'debate', 'theme')
        if beat not in weak_beats:
            return lines

        result = list(lines)
        for _ in range(count):
            tmpl = self._rng.choice(INTERIORITY_TEMPLATES)
            interior = tmpl.format(
                name='林朔',
                action=self._rng.choice(['这一切', '这种日常', '玩家们的笑声', '面板上跳动的数字']),
                detail=self._rng.choice(EXPANSION_DETAILS['details']),
                adjective=self._rng.choice(['熟悉', '正常', '安全', '有序', '可控']),
            )
            insert_pos = self._rng.randint(len(result) // 3, 2 * len(result) // 3)
            result.insert(insert_pos, interior)
        return result


# ================================================================
# 世界差异化词库（不变，保持）
# ================================================================

WORLD_SENSE_PROFILES = {
    '归墟': {
        'visual': ['蓝光闪烁', '星图纵横', '石尘悬浮', '虚空无尽'],
        'audio': ['低频嗡鸣', '墟核的电子脉冲声', '自己的呼吸回响'],
        'touch': ['石板冰凉', '墟核静电刺痛', '空气干燥'],
        'smell': ['矿石的干涩味', '古老石料的粉尘味'],
        'atmosphere': ['空旷的压迫感', '时间失去参照物', '唯一的活物就是自己'],
    },
    '武侠·苍云之殇': {
        'visual': ['晨雾缭绕山脊', '竹林在风中倾斜', '青石板路被脚步磨得光滑'],
        'audio': ['溪水撞击鹅卵石', '铁剑出鞘的金属摩擦', 'NPC的方言叫卖声'],
        'touch': ['山风里湿气很重', '布鞋底太薄——走一天路脚底起泡'],
        'smell': ['松木燃烧的焦香', '当归和黄芪的药味', '雨后泥土翻起的青草味'],
        'atmosphere': ['山水画般的宁静下藏着魔教阴影'],
    },
    '末日废土': {
        'visual': ['灰黄色的天空', '断裂的钢筋骨架', '废弃车辆锈成铁红色'],
        'audio': ['风穿过废墟的呼啸', '能量风暴接近时的静电嗡鸣'],
        'touch': ['空气干燥且辛辣', '吸入肺里像吸进碎玻璃'],
        'smell': ['烧焦的金属', '臭氧浓度高到发甜'],
        'atmosphere': ['文明的尸骸', '沉默是一种保护色'],
    },
    '近代乱世': {
        'visual': ['蒸汽与煤烟交织', '电报线切割天空'],
        'audio': ['蒸汽机活塞的节奏', '远处的枪声'],
        'touch': ['煤灰粘在皮肤上', '枪管烫手'],
        'smell': ['煤烟和汗水的混合', '火药残留的硫磺味'],
        'atmosphere': ['变革前夜的不安'],
    },
    '低魔中世纪': {
        'visual': ['石砌城堡的轮廓', '油灯在走廊里摇曳'],
        'audio': ['马蹄踏在鹅卵石上', '铁匠铺的锤击'],
        'touch': ['粗纺羊毛的刺感', '石墙的潮湿渗透衣服'],
        'smell': ['蜡烛和旧书的混合', '雨后城堡的霉味'],
        'atmosphere': ['古老的秩序正在崩塌'],
    },
    '剑与魔法': {
        'visual': ['浮空岛屿的瀑布向下无尽倾泻', '魔法纹路在空气中短暂发光'],
        'audio': ['咒语的音阶', '翼龙翅膀划破气流的爆音'],
        'touch': ['魔法余温——空气在指尖流动时有阻力'],
        'smell': ['精灵林地的花香不像地球上的任何花'],
        'atmosphere': ['壮丽之下有深重宿命'],
    },
    '星际殖民': {
        'visual': ['星舰尾焰切割真空', '气态巨行星占据半边天空'],
        'audio': ['舰体金属受热膨胀的低吟'],
        'touch': ['人造重力——比地球轻3%'],
        'smell': ['循环空气的消毒水味'],
        'atmosphere': ['人类在宇宙中的渺小感和倔强并存'],
    },
    '东方修仙': {
        'visual': ['云雾缭绕的悬空山', '飞剑留下的青色尾迹'],
        'audio': ['闭关洞府中只有水滴', '渡劫的雷声'],
        'touch': ['灵气入体的温热——像喝了一口热茶但不在胃里'],
        'smell': ['千年灵芝——不是药香，是时间本身的味道'],
        'atmosphere': ['弱肉强食的残酷裹在道法自然的缥缈里'],
    },
    '赛博都市': {
        'visual': ['霓虹全息广告在雨夜中扭曲'],
        'audio': ['永远不停的雨打在天窗上', '数据流的电子噪音'],
        'touch': ['雨水是酸的——皮肤有轻微刺痛'],
        'smell': ['合成食物——像记忆中的味道但少了什么'],
        'atmosphere': ['科技高度发达——但人比任何时候都孤独'],
    },
    '诸神黄昏': {
        'visual': ['倒下的神像比山还高', '诸神的血是金色的'],
        'audio': ['神域的挽歌——是法则的震荡'],
        'touch': ['神陨之地的地面是温的——像还有余温的尸体'],
        'smell': ['燃烧的神性——吸进去之后人会短暂地遗忘一件小事'],
        'atmosphere': ['神的终末比人的更绝望'],
    },
}


class WorldSenseInjector:
    """世界差异感官引擎。"""

    def __init__(self, seed=None):
        self._rng = random.Random(seed)

    def inject(self, lines: list, world_name: str, frequency: int = 2) -> list:
        profile = WORLD_SENSE_PROFILES.get(world_name)
        if not profile:
            return lines
        result = list(lines)
        senses = ['visual', 'audio', 'touch', 'smell']

        # 找段落边界（空行位置）
        boundary_positions = []
        for i, line in enumerate(result):
            if line.strip() == '' and i > 2 and i < len(result) - 1:
                boundary_positions.append(i)

        if not boundary_positions:
            return result  # 没有空行可以安全注入

        injected = 0
        for _ in range(frequency):
            if injected >= frequency or not boundary_positions:
                break
            sense = self._rng.choice(senses)
            if sense in profile and profile[sense]:
                fragment = self._rng.choice(profile[sense])
                # 从边界位置中随机选一个（不重复）
                pos = self._rng.choice(boundary_positions)
                boundary_positions.remove(pos)
                result.insert(pos + 1, fragment)
                injected += 1

        return result

    def get_atmosphere(self, world_name: str) -> str:
        profile = WORLD_SENSE_PROFILES.get(world_name, {})
        atmospheres = profile.get('atmosphere', ['未知世界的氛围'])
        return self._rng.choice(atmospheres)
