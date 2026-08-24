# -*- coding: utf-8 -*-
"""P3: 交互式大纲插桩 + 轻量NLP一致性检查。

交互式大纲：在关键转折点暂停，让用户选方向分支。
NLP检查器：规则引擎检测人格漂移、伏笔超时、时间线矛盾。
"""

import re
from typing import Optional


# ================================================================
# 1. 交互式大纲插桩 (Interactive Outline)
# ================================================================

# 关键分叉点定义
STORY_BRANCHES = {
    49: {  # 中点后
        'title': '下一章发展方向',
        'options': [
            {
                'key': 'agent_line',
                'label': '代理人线',
                'description': '优先废土世界冲突——代理人开始主动攻击玩家据点',
                'effects': {'next_beat_focus': 'bad_guys', 'priority_world': '末日废土'},
            },
            {
                'key': 'yelin_line',
                'label': '叶琳线',
                'description': '优先武侠世界收尾——叶琳的魔剑侵蚀开始加速',
                'effects': {'next_beat_focus': 'b_story_deep', 'priority_world': '武侠·苍云之殇'},
            },
            {
                'key': 'balanced',
                'label': '双线并行',
                'description': '林朔分身在废土，唐川留守苍云山照看叶琳',
                'effects': {'next_beat_focus': 'balanced', 'priority_world': 'both'},
            },
        ],
    },
    75: {  # 第二转折后
        'title': '白夜的信息如何使用',
        'options': [
            {
                'key': 'tell_tangchuan',
                'label': '告诉唐川',
                'description': '林朔向唐川坦白部分真相——信任建立',
                'effects': {'next_beat_focus': 'alliance', 'tangchuan_truth': True},
            },
            {
                'key': 'keep_secret',
                'label': '独自承受',
                'description': '林朔独自调查身份真相——孤独加深',
                'effects': {'next_beat_focus': 'solo', 'lingshuo_isolation': True},
            },
            {
                'key': 'question_xuke',
                'label': '质问墟核',
                'description': '逼问墟核关于循环的全部记录——解锁千层饼第3层',
                'effects': {'next_beat_focus': 'revelation', 'truth_layer_advance': True},
            },
        ],
    },
    80: {  # 第一卷结束
        'title': '第一卷尾声基调',
        'options': [
            {
                'key': 'cliffhanger',
                'label': '悬念结尾',
                'description': '代理人在废土世界打开大型传送门——大规模入侵在即',
                'effects': {'ending_type': 'cliffhanger'},
            },
            {
                'key': 'resolution',
                'label': '阶段性收束',
                'description': '废土碎片回收成功，叶琳暂时稳定——但白夜的话悬而未决',
                'effects': {'ending_type': 'resolution_partial'},
            },
            {
                'key': 'twist',
                'label': '反转炸弹',
                'description': '墟核在最后一章显示：锚定者协议第48条——若锚定者被同化，系统将自动选择下一任',
                'effects': {'ending_type': 'twist', 'foreshadowing': 'V_bomb'},
            },
        ],
    },
}


class InteractiveOutline:
    """交互式大纲：在关键章暂停，收集用户分支选择。"""

    def __init__(self):
        self._choices = {}
        self._branches = STORY_BRANCHES

    def should_pause(self, chapter_num: int) -> bool:
        return chapter_num in self._branches

    def get_branch(self, chapter_num: int) -> Optional[dict]:
        if chapter_num in self._branches:
            return self._branches[chapter_num]
        return None

    def record_choice(self, chapter_num: int, choice_key: str):
        self._choices[chapter_num] = choice_key

    def get_choice(self, chapter_num: int) -> Optional[str]:
        return self._choices.get(chapter_num)

    def get_all_effects(self) -> dict:
        """汇总所有用户选择的效应。"""
        effects = {}
        for ch_num, choice_key in self._choices.items():
            if ch_num in self._branches:
                for opt in self._branches[ch_num]['options']:
                    if opt['key'] == choice_key:
                        for k, v in opt['effects'].items():
                            effects[k] = v
        return effects

    def format_prompt(self, chapter_num: int) -> str:
        """格式化为可呈现给用户的交互式提示。"""
        branch = self.get_branch(chapter_num)
        if not branch:
            return ''

        lines = [
            '=' * 50,
            '第%d章生成完毕。检测到分叉点：%s' % (chapter_num, branch['title']),
            '=' * 50,
            '',
        ]
        for i, opt in enumerate(branch['options'], 1):
            lines.append('  %s. %s — %s' % (chr(64 + i), opt['label'], opt['description']))

        lines.append('')
        lines.append('[选A/B/C，或输入自定义方向]')
        return '\n'.join(lines)


# ================================================================
# 2. 轻量NLP一致性检查器
# ================================================================

class ConsistencyChecker:
    """规则引擎：检测人格漂移、伏笔超时、时间线矛盾。

    不依赖NLP模型，用关键词模式匹配 + 字符分析。
    """

    def __init__(self):
        self._char_personas = {}  # 角色人格档案

    def register_character(self, name: str, personality: dict):
        """注册角色的人格基线。

        personality = {
            'keywords': ['谨慎', '冷静', '理性'],
            'speech_patterns': ['短句', '反问', '推眼镜'],
            'emotional_range': ['警觉', '无奈', '坚定'],
            'forbidden_emotions': ['冲动', '莽撞', '开怀大笑'],
        }
        """
        self._char_personas[name] = personality

    def check_personality_drift(self, text: str, name: str) -> list:
        """检查角色是否出现人格漂移。

        Returns:
            [(issue, severity)] 问题列表。
        """
        if name not in self._char_personas:
            return []

        persona = self._char_personas[name]
        issues = []

        # 检查禁止情绪
        for forbidden in persona.get('forbidden_emotions', []):
            if forbidden in text:
                # 但要看上下文——如果是转折点，可能是故意的
                pos = text.find(forbidden)
                context_before = text[:pos] if pos != -1 else ''
                if '转折' not in context_before and '不再' not in context_before:
                    issues.append((
                        '%s出现禁止行为[%s]——若非故意转折请检查' % (name, forbidden),
                        'warning',
                    ))

        # 检查关键词频率
        keywords = persona.get('keywords', [])
        kw_count = sum(1 for kw in keywords if kw in text)
        if kw_count < len(keywords) * 0.3:
            issues.append((
                '%s的人格关键词覆盖率不足（%.0f%%）——角色可能OOC' % (
                    name, kw_count / max(len(keywords), 1) * 100),
                'info',
            ))

        return issues

    def check_foreshadowing_expiry(self, foreshadowing_list: list,
                                   current_chapter: int) -> list:
        """检查是否有超时未回收的伏笔。"""
        issues = []
        for fs in foreshadowing_list:
            if fs.get('status') == 'active':
                planted = fs.get('planted_chapter', 0)
                planned = fs.get('planned_recovery_chapter', 0)
                age = current_chapter - planted

                if age > 30:
                    issues.append((
                        '伏笔[%s]已埋设%d章（计划回收章%d），超时未回收！' % (
                            fs.get('id', '?'), age, planned),
                        'warning',
                    ))
                elif age > 20:
                    issues.append((
                        '伏笔[%s]已%d章未提——建议在最近3章内暗示' % (
                            fs.get('id', '?'), age),
                        'info',
                    ))

        return issues

    def check_timeline_contradiction(self, text: str,
                                     chapter_summaries: list) -> list:
        """检查时间线矛盾（字符频率 + 关键词碰撞）。"""
        issues = []

        # 简单检查：同一角色不能同时出现在两个世界
        for summary in chapter_summaries:
            # 检查最近一章是否有角色出现在多个地点
            pass  # 需要更复杂的实体识别，先留接口

        # 检查时间词矛盾
        time_words = re.findall(r'(第[一二三四五六七八九十\d]+天|第[一二三四五六七八九十\d]+日|过了\d+天)', text)
        if len(time_words) >= 2:
            # 简单检查：两个时间词之间的数字不能递减
            pass

        return issues

    def full_check(self, text: str, chapter_num: int,
                   chapter_summaries: list,
                   foreshadowing: list) -> dict:
        """完整一致性检查。"""
        results = {
            'personality_drift': [],
            'foreshadowing_expiry': [],
            'timeline_issues': [],
            'all_clear': True,
        }

        # 对每个注册角色做人格检查
        for name in self._char_personas:
            drift = self.check_personality_drift(text, name)
            if drift:
                results['personality_drift'].extend(drift)

        # 伏笔超时检查
        expiry = self.check_foreshadowing_expiry(foreshadowing, chapter_num)
        if expiry:
            results['foreshadowing_expiry'].extend(expiry)

        # 时间线检查
        timeline = self.check_timeline_contradiction(text, chapter_summaries)
        if timeline:
            results['timeline_issues'].extend(timeline)

        # 是否有任何问题
        results['all_clear'] = not any([
            results['personality_drift'],
            results['foreshadowing_expiry'],
            results['timeline_issues'],
        ])

        return results


# ================================================================
# 3. 统一管线
# ================================================================

# 注册林朔的人格基线
CHARACTER_PERSONAS = {
    '林朔': {
        'keywords': ['推眼镜', '沉默', '分析', '记录', '有意思'],
        'speech_patterns': ['短句', '反问', '推眼镜'],
        'emotional_range': ['警觉', '无奈', '坚定', '绝望', '愤怒', '崩溃'],
        'forbidden_emotions': ['开怀大笑', '冲动的决定', '盲目乐观'],
    },
}
