# -*- coding: utf-8 -*-
"""跨界混搭生成器 —— 2026年网文最大趋势：母题 + 嫁接元素 = 新爆款。

为12个花瓣世界预置嫁接公式，让每个世界不仅是"一个类型的模板"，
而是带有独特跨界元素的复合世界观。

2026爆款法则：
  母题不能陌生 + 嫁接补充情绪缺口 + 焊接=发明新规则
"""

import random
from typing import Optional


# ================================================================
# 12个世界的嫁接公式
# ================================================================
FUSION_RECIPES = {
    '武侠·苍云之殇': {
        'base_genre': '传统武侠',
        'fusion': '中式民俗玄学',
        'formula': '武侠 × 民俗玄学 = 中式克苏鲁武侠',
        'new_rules': [
            '内力修炼的本质是对「阴德/业力」的量化管理',
            '每门武功都附带「代价」——练成之日就是代价支付之时',
            '《苍云剑法》的真正创始人不是人——是山里的某个「东西」',
            '魔剑中的低语不是幻觉——是在用源界古语传授《死灵之书》的残章',
        ],
        'emotional_gap_filled': '纯武侠缺「惊奇感」→ 用民俗玄学的不可知论填补',
        'sample_hook': '叶琳发现苍云派的祖师爷——不是练武练到飞升的，是把自己献祭给了苍云山里的某个东西。那个东西至今还在后山的洞里——它每隔十年要一个新的弟子。今年轮到叶琳了。',
    },
    '末日废土': {
        'base_genre': '末世生存',
        'fusion': '职场管理学',
        'formula': '废土 × 职场 = 带KPI的末世求生',
        'new_rules': [
            '避难所实行OKR制度——本季度关键目标：收集500个核融合核心',
            '辐射变异生物可以被「驯化」——但需要填写《异种生物驯养申请表》',
            '废土上的各势力之间的战争——本质上是「绩效考核」的制度之争',
            '林朔通过GM面板发现：代理人不是敌人——只是另一个避难所的「项目经理」',
        ],
        'emotional_gap_filled': '废土缺「共鸣感」→ 用社畜的日常荒诞填充',
        'sample_hook': '废土最大的势力是一个叫「无限责任公司」的组织。他们的CEO是一个只剩半个身体的AI——它用Excel管理着三万多人的生存资源分配。林朔打开它的数据表看了一眼：玩家们的战斗力被精确到了小数点后两位。它正在计算——用多少个玩家可以换一片碎片是「最经济的」。',
    },
    '近代乱世': {
        'base_genre': '历史架空',
        'fusion': '谍战密码学',
        'formula': '近代乱世 × 密码学 = 被加密的世界真相',
        'new_rules': [
            '军阀的作战命令是用源界古语加密的——源界碎片在这个世界具象化为「不可破解的密码本」',
            '每一个租界领事馆的地下室都有一个通向混沌海的暗门',
            '报纸上的每一篇社论都藏着一个坐标——是祂们的代理人留给其他代理人的暗号',
        ],
        'emotional_gap_filled': '乱世缺「智力感」→ 用密码学的解谜快感填补',
    },
    '低魔中世纪': {
        'base_genre': '西幻魔法',
        'fusion': '经济学/通货膨胀',
        'formula': '低魔 × 经济学 = 通货膨胀导致的魔法衰退',
        'new_rules': [
            '魔力是一种不可再生资源——过度开采导致魔力通胀',
            '魔法师行会实际上是一个「魔力央行」——他们控制着魔力的发行量',
            '一个火球术在过去只要3点魔力——现在要300点。不是法师变弱了，是钱不值钱了',
            '源界碎片在这个世界具象化为「魔力开采许可证」——谁掌握了它，谁就掌握了经济命脉',
        ],
        'emotional_gap_filled': '西幻缺「真实感」→ 用经济学的残酷性填充',
    },
    '剑与魔法': {
        'base_genre': '高等奇幻',
        'fusion': '司法体系/国际法',
        'formula': '高魔 × 国际法 = 魔法世界的外交博弈',
        'new_rules': [
            '不同种族之间的战争要遵守《跨种族武装冲突法》',
            '龙的领地是主权领土——在龙穴上空飞行需要申请「飞越许可」',
            '魔法学院不仅是学校——是魔法世界的「最高法院」，裁决所有魔法争议',
            '代理人试图通过「法律漏洞」合法地夺取碎片——林朔需要一个奇幻世界的律师',
        ],
        'emotional_gap_filled': '高魔缺「智斗感」→ 用法律博弈的精密性填充',
    },
    '东方修仙': {
        'base_genre': '修仙',
        'fusion': '统计学/系统论',
        'formula': '修仙 × 统计学 = 被数据化的天道',
        'new_rules': [
            '天劫的威力不是随机的——是天道根据你的「因果值」精确计算的',
            '渡劫成功率可以用贝叶斯公式预测',
            '灵脉分布遵循幂律分布——80%的灵气集中在20%的地方',
            '林朔发现修仙世界的碎片是一个「因果系数」——改变它可以改变天道的算法',
        ],
        'emotional_gap_filled': '修仙缺「逻辑感」→ 用统计学的可预测性填充',
        'sample_hook': '当林朔用墟核扫描这个修仙世界时，他看到的不再是灵脉分布图——是一张热力图。颜色越深的地方，灵气越浓。他放大到最大——每一个像素都是一个正在修炼的修士。他把墟核的算法切换到「预测模式」——屏幕上浮现了一个数字：渡劫存活率——2.7%。这就是天道。一个冷酷的概率计算器。',
    },
    '赛博都市': {
        'base_genre': '赛博朋克',
        'fusion': '非物质文化遗产传承',
        'formula': '赛博 × 非遗 = 数据化的传统技艺',
        'new_rules': [
            '古老的功夫被编码成「动作数据包」——购买后直接下载到神经接口',
            '地下黑客组织的加密算法源自古代的编绳记事',
            '城市底层有一群「记忆守护者」——他们拒绝义体化，用肉身传承即将消亡的技艺',
            '源界碎片在这个世界是一段「无法复制的原始代码」——所有的企业都想得到它',
        ],
        'emotional_gap_filled': '赛博缺「温度感」→ 用非遗的人文温度填充',
    },
    '诸神黄昏': {
        'base_genre': '神话末日',
        'fusion': '考古学/灾后重建',
        'formula': '神话末日 × 考古学 = 在神骸上重建的文明',
        'new_rules': [
            '死去神明的身体是最好的建材——神骨比钢铁硬，神血是永久能源',
            '有一群「神骸考古学家」——他们的工作是挖掘神明临终前最后的思想残片',
            '每一种从神骸中提取的技术——都要付出「神怒」的代价',
        ],
        'emotional_gap_filled': '神话缺「真实感」→ 用考古学的严谨性填充',
    },
    '克苏鲁深渊': {
        'base_genre': '宇宙恐怖',
        'fusion': '心理学/创伤治疗',
        'formula': '克苏鲁 × 心理学 = 被量化的疯狂',
        'new_rules': [
            'SAN值不仅是游戏机制——是真实可测的心理创伤指数',
            '不可名状的知识不一定会让你疯——有时它会治好你已有的疯',
            '拉莱耶不是一座城市——是一个精神病院的建筑蓝图',
            '那个在你脑子里吹笛子的声音——它在给你做心理治疗。只是它的治疗方式不是人类心理学',
        ],
        'emotional_gap_filled': '恐怖缺「共情」→ 用心理学的共鸣感填充',
    },
    '高等文明实验场': {
        'base_genre': '科幻',
        'fusion': '教育哲学/蒙台梭利',
        'formula': '实验场 × 教育哲学 = 万界是一个宇宙级的蒙台梭利教室',
        'new_rules': [
            '源不是消失了——它是在观察。一个老师是不会在学生做题时插手的',
            '所有文明面临相同的考题——但答题方式完全不同',
            '碎片的回收——在祂们看来——是偷看答案。这就是为什么祂们在阻止回收',
        ],
        'emotional_gap_filled': '科幻缺「意义感」→ 用教育的目标感填充',
    },
    '造物主遗迹': {
        'base_genre': '终极揭秘',
        'fusion': '哲学/自由意志辩论',
        'formula': '遗迹 × 哲学 = 与源的对话',
        'new_rules': [
            '源的心脏——那颗被束缚的黑洞——里面不是能量。是一个问题。',
            '每一个进入遗迹的人都要回答同一个问题：如果有机会成为新的源——你会怎样设计万界？',
            '镜子长廊里不同的你——不是在展示你的可能性，是在展示你如果做出不同选择——会成为谁。而这些选择——都是源计算过的。',
        ],
        'emotional_gap_filled': '终结缺「思辨感」→ 用哲学的深度填充',
    },
}


class FusionGenerator:
    """跨界混搭生成器：为每个世界预置嫁接公式，输出融合创意。

    Usage:
        fg = FusionGenerator(seed=42)
        recipe = fg.get_recipe('武侠·苍云之殇')
        world_hook = fg.generate_hook('武侠·苍云之殇')
        all_fusions = fg.list_all_formulas()
    """

    def __init__(self, seed=None):
        self._rng = random.Random(seed)

    def get_recipe(self, world_name: str) -> Optional[dict]:
        """获取指定世界的完整嫁接公式。"""
        return FUSION_RECIPES.get(world_name)

    def get_formula(self, world_name: str) -> str:
        """获取嫁接公式字符串（如'武侠 × 民俗玄学 = 中式克苏鲁武侠'）。"""
        recipe = self.get_recipe(world_name)
        return recipe['formula'] if recipe else f'{world_name}（未配置嫁接）'

    def get_new_rules(self, world_name: str) -> list:
        """获取新规则列表。"""
        recipe = self.get_recipe(world_name)
        return recipe['new_rules'] if recipe else []

    def generate_hook(self, world_name: str) -> str:
        """为指定世界生成一个嫁接后的故事钩子。"""
        recipe = self.get_recipe(world_name)
        if not recipe:
            return f'{world_name}的标准故事线。'
        if 'sample_hook' in recipe:
            return recipe['sample_hook']
        # 从new_rules中随机取一条作为钩子
        if recipe.get('new_rules'):
            return self._rng.choice(recipe['new_rules'])
        return recipe['formula']

    def list_all_formulas(self) -> list:
        """列出所有世界的嫁接公式。"""
        return [
            {
                'world': name,
                'formula': info['formula'],
                'base': info['base_genre'],
                'fusion': info['fusion'],
            }
            for name, info in FUSION_RECIPES.items()
        ]

    def generate_cross_world_fusion(self, world_a: str, world_b: str) -> str:
        """尝试将两个世界的融合元素交叉组合。"""
        recipe_a = self.get_recipe(world_a)
        recipe_b = self.get_recipe(world_b)
        if not recipe_a or not recipe_b:
            return "无法生成——其中至少一个世界未配置。"
        return (
            f'【跨界实验】{recipe_a["formula"]} × {recipe_b["formula"]}\n'
            f'  {world_a}的嫁接元素({recipe_a["fusion"]}) '
            f'渗透入{world_b}会怎样？\n'
            f'  可能的化学反应：'
            f'{world_b}的角色突然发现——'
            f'{world_a}的规则在自己的世界也部分适用。'
        )
