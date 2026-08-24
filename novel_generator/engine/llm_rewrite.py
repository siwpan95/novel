# -*- coding: utf-8 -*-
"""LLM润色引擎 + Rubric自动重写 + 交互式大纲。

LLM润色：规则引擎骨架 → LLM血肉化，消除模板感和重复感。
Rubric重写：得分<7 的章节自动触发局部改写。
交互式大纲：在49/75/80章暂停，让用户选分支方向。
"""

from typing import Optional, Callable


# ================================================================
# 1. LLM润色引擎
# ================================================================

# 润色提示词模板（按问题类型分类）
POLISH_PROMPTS = {
    'dialogue_naturalness': (
        "你是一位资深网文编辑。请润色以下段落，使其对话更自然，具体要求：\n"
        "1. 删减30%以上的对话标签（说/道/问/答），用动作替代\n"
        "2. 给至少一个角色加入口癖或独特的说话节奏\n"
        "3. 增加对话中的停顿、打断、沉默\n"
        "4. 确保遮住名字后能分辨是谁在说话\n\n"
        "原文：\n{text}\n\n润色后（保持原意，只改写对话部分）："
    ),
    'rhythm': (
        "你是一位资深网文编辑。请润色以下段落，改善其节奏感，具体要求：\n"
        "1. 在紧张处插入2-3个短句（5字以内）或单字独段\n"
        "2. 打破均匀感——将连续的3-4句中句至少拆散一处\n"
        "3. 在情感高点插入空白行制造停顿\n\n"
        "原文：\n{text}\n\n润色后："
    ),
    'emotion': (
        "你是一位资深网文编辑。请润色以下段落，增强情感张力，具体要求：\n"
        "1. 用身体反应代替直接的情绪形容词（不用「他很愤怒」，写「他攥紧的拳头在发抖」）\n"
        "2. 增加2处物理感知描写（心跳/呼吸/体温/触觉）\n"
        "3. 确保情感有变化——不止一种情绪\n\n"
        "原文：\n{text}\n\n润色后："
    ),
    'de_ai': (
        "你是一位资深网文编辑。请润色以下段落，消除AI写作痕迹，具体要求：\n"
        "1. 删掉「不禁」「忍不住」「一股XX涌上心头」等AI高频词\n"
        "2. 将过于完美的段落打破——插入不完整句、口误、自我纠正\n"
        "3. 用具体的、不完美的细节替代抽象的形容词\n\n"
        "原文：\n{text}\n\n润色后："
    ),
    'causality': (
        "你是一位资深网文编辑。请润色以下段落，增强因果链，具体要求：\n"
        "1. 确保每个事件都能追溯到前文的原因\n"
        "2. 加入角色对前文事件的回忆或引用\n"
        "3. 在事件转折处明确写出「因为……所以……」的逻辑\n\n"
        "原文：\n{text}\n\n润色后："
    ),
    'comprehensive': (
        "你是一位资深网文编辑。请全面润色以下小说章节片段，要求：\n"
        "1. 对话自然生动，有角色辨识度\n"
        "2. 句式长短交错，有节奏起伏\n"
        "3. 情感通过行为体现，不直接命名\n"
        "4. 无AI模板痕迹\n"
        "5. 保持原文的情节结构和信息量\n\n"
        "原文：\n{text}\n\n润色后："
    ),
}


class LLMPolishEngine:
    """LLM润色引擎：规则骨架 → LLM血肉化。

    支持两种模式：
    - api_mode: 通过外部API调用（需提供 call_fn）
    - inline_mode: 在对话中直接润色（利用当前LLM能力）
    """

    def __init__(self, call_fn: Optional[Callable] = None):
        """
        Args:
            call_fn: LLM调用函数，签名为 call_fn(prompt: str) -> str。
                     为None时使用inline模式。
        """
        self._call_fn = call_fn
        self._stats = {'polished': 0, 'rewritten': 0, 'total_chars_before': 0, 'total_chars_after': 0}

    def polish(self, text: str, focus: str = 'comprehensive') -> str:
        """对一段文本进行LLM润色。

        Args:
            text: 待润色的文本
            focus: 润色重点——'comprehensive'/'dialogue_naturalness'/'rhythm'/'emotion'/'de_ai'/'causality'

        Returns:
            润色后的文本。
        """
        prompt_key = focus if focus in POLISH_PROMPTS else 'comprehensive'
        prompt = POLISH_PROMPTS[prompt_key].format(text=text[:4000])  # 限制长度

        if self._call_fn:
            result = self._call_fn(prompt)
        else:
            # inline模式：由调用方在对话中处理
            result = '[需外部LLM调用] ' + prompt[:100] + '...'

        self._stats['polished'] += 1
        self._stats['total_chars_before'] += len(text)
        self._stats['total_chars_after'] += len(result)
        return result

    def polish_chapter(self, chapter_text: str, rubric_scores: dict) -> str:
        """基于Rubric评分，自动选择最有针对性的润色策略。

        Args:
            chapter_text: 章节原文
            rubric_scores: Rubric五维评分 {'对话自然度': 5.5, ...}

        Returns:
            润色后的章节文本。
        """
        # 找到最低分维度
        weakest = min(rubric_scores, key=rubric_scores.get)
        lowest_score = rubric_scores[weakest]

        if lowest_score < 5.5:
            # 严重问题：全面重写
            return self.polish(chapter_text, 'comprehensive')
        elif lowest_score < 6.5:
            # 针对最弱维度重写
            focus_map = {
                '对话自然度': 'dialogue_naturalness',
                '节奏感': 'rhythm',
                '情感曲线': 'emotion',
                '去AI味': 'de_ai',
                '因果一致性': 'causality',
            }
            focus = focus_map.get(weakest, 'comprehensive')
            return self.polish(chapter_text, focus)
        else:
            # 轻微润色
            return self.polish(chapter_text, 'comprehensive')

    @property
    def stats(self):
        return self._stats


# ================================================================
# 2. Rubric→自动重写管线
# ================================================================

class AutoRewritePipeline:
    """Rubric触发自动重写：得分<7的章节自动局部改写。"""

    def __init__(self, rubric_engine, polish_engine, max_rewrites: int = 3):
        self._rubric = rubric_engine
        self._polish = polish_engine
        self._max_rewrites = max_rewrites
        self._history = []

    def process(self, chapter_text: str, beat: str,
                chapter_num: int) -> tuple:
        """对单章进行评分→重写→再评分循环，直到达标或达到最大重写次数。

        Returns:
            (final_text, final_score, rewrite_count)
        """
        current_text = chapter_text
        rewrite_count = 0

        for attempt in range(self._max_rewrites + 1):
            result = self._rubric.evaluate(current_text, beat)

            if result['verdict'] == 'pass' and result['total'] >= 7.5:
                self._history.append({
                    'chapter': chapter_num,
                    'rewrites': rewrite_count,
                    'final_score': result['total'],
                })
                return current_text, result, rewrite_count

            if attempt < self._max_rewrites:
                # 触发重写
                current_text = self._polish.polish_chapter(
                    current_text, result['scores'])
                rewrite_count += 1

        # 达到最大重写次数，返回当前最佳
        final_result = self._rubric.evaluate(current_text, beat)
        self._history.append({
            'chapter': chapter_num,
            'rewrites': rewrite_count,
            'final_score': final_result['total'],
            'forced_stop': True,
        })
        return current_text, final_result, rewrite_count

    def batch_process(self, chapters: list, beats: list) -> list:
        """批量处理多章（带进度）。"""
        results = []
        for i, (text, beat) in enumerate(zip(chapters, beats)):
            ch_num = i + 1
            final_text, score, rewrites = self.process(text, beat, ch_num)
            results.append({
                'chapter': ch_num,
                'text': final_text,
                'score': score['total'],
                'verdict': score['verdict'],
                'rewrites': rewrites,
            })
        return results

    def summary(self) -> dict:
        total = len(self._history)
        if total == 0:
            return {}
        avg_score = sum(h['final_score'] for h in self._history) / total
        total_rewrites = sum(h['rewrites'] for h in self._history)
        return {
            'total_chapters': total,
            'avg_score': round(avg_score, 1),
            'total_rewrites': total_rewrites,
            'rewrite_rate': round(total_rewrites / total, 1),
        }


# ================================================================
# 3. 交互式大纲系统
# ================================================================

STORY_BRANCHES = {
    49: {
        'title': '中点后——下一阶段主线方向',
        'options': [
            {'key': 'agent_war', 'label': '代理人战争', 'desc': '优先废土世界——代理人开始主动攻击玩家据点，林朔被迫发动第一次反攻'},
            {'key': 'yelin_crisis', 'label': '叶琳危机加深', 'desc': '魔剑同化率加速——叶琳必须在20章内获得碎片核心否则将被完全同化'},
            {'key': 'dual_front', 'label': '双线并行', 'desc': '林朔分身废土指挥，唐川留守苍云山组建叶琳守护队——两线压力同时升级'},
        ],
    },
    75: {
        'title': '白夜的真相——如何使用',
        'options': [
            {'key': 'tell_all', 'label': '告知唐川全部', 'desc': '林朔向唐川坦白循环真相——信任建立，但唐川陷入存在危机'},
            {'key': 'keep_partial', 'label': '保留部分', 'desc': '只说循环不说身份——给林朔保留最后的防线，但白夜认为这是懦弱'},
            {'key': 'interrogate_xuke', 'label': '逼问墟核', 'desc': '用白夜的信息逼墟核解锁加密日志——千层饼揭开第3层，代价未知'},
        ],
    },
    80: {
        'title': '第一卷尾声——终局基调',
        'options': [
            {'key': 'cliffhanger', 'label': '悬念式', 'desc': '代理人打开大型传送门——大规模入侵在即，林朔和唐川站在归墟之巅准备迎战'},
            {'key': 'resolution_earned', 'label': '阶段性胜利', 'desc': '废土碎片回收成功+叶琳暂时稳定——但白夜的话悬而未决，为第二卷留下引线'},
            {'key': 'bomb_twist', 'label': '反转炸弹', 'desc': '墟核在最后一章显示：锚定者协议第48条——若锚定者被同化，系统将自动选择下一任。谁是下一任？唐川。'},
        ],
    },
}


class InteractiveOutline:
    """交互式大纲：在分支点暂停，收集用户决定。"""

    def __init__(self):
        self._choices = {}

    def should_pause(self, chapter_num: int) -> bool:
        return chapter_num in STORY_BRANCHES

    def get_branch(self, chapter_num: int) -> Optional[dict]:
        return STORY_BRANCHES.get(chapter_num)

    def record(self, chapter_num: int, choice_key: str):
        self._choices[chapter_num] = choice_key

    def get_effects(self) -> dict:
        effects = {}
        for ch_num, choice_key in self._choices.items():
            branch = STORY_BRANCHES.get(ch_num, {})
            for opt in branch.get('options', []):
                if opt['key'] == choice_key:
                    for k, v in opt.get('effects', {}).items():
                        effects[k] = v
        return effects

    def format_prompt(self, chapter_num: int) -> str:
        branch = self.get_branch(chapter_num)
        if not branch:
            return ''

        lines = [
            '\n' + '=' * 55,
            '  分叉点 | 第%d章 | %s' % (chapter_num, branch['title']),
            '=' * 55 + '\n',
        ]
        labels = ['A', 'B', 'C']
        for i, opt in enumerate(branch['options']):
            lines.append('  [%s] %-16s — %s' % (labels[i], opt['label'], opt['desc']))

        lines.append('\n  输入 A/B/C 选择方向，或直接回车使用默认(A)：')
        return '\n'.join(lines)

    def apply_branch_effects(self, chapter_num: int, choice_key: str,
                             plot_state, causal_chapter_gen):
        """将用户选择应用到情节状态和后续生成中。"""
        branch = STORY_BRANCHES.get(chapter_num, {})
        opt_effects = {}
        for opt in branch.get('options', []):
            if opt['key'] == choice_key:
                opt_effects = opt.get('effects', {})

        # 应用效果到 plot_state
        for k, v in opt_effects.items():
            if k == 'priority_world':
                plot_state.state['current_world_focus'] = v
            elif k == 'tangchuan_truth':
                plot_state.set_plot_flag('tangchuan_truth_revealed', True)
            elif k == 'truth_layer_advance':
                plot_state.advance_truth_layer()
            elif k == 'next_beat_focus':
                plot_state.state['next_beat_focus'] = v

        plot_state.save()
        return opt_effects
