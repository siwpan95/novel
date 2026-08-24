# -*- coding: utf-8 -*-
import json as _json

from .word_bank import resolve_bank_path


class _LazyBank:
    """延迟加载JSON词库——首次 __getitem__ 访问时才读文件，避免 import-time I/O。"""
    __slots__ = ('_data', '_bank_name')

    def __init__(self, bank_name: str):
        self._data = None
        self._bank_name = bank_name

    def _load(self):
        if self._data is None:
            path = resolve_bank_path(self._bank_name)
            with open(path, encoding='utf-8') as _f:
                self._data = _json.load(_f)
        return self._data

    def __getitem__(self, key):
        return self._load()[key]

    def get(self, key, default=None):
        return self._load().get(key, default)


_QF = _LazyBank('quality_fragments')
"""文本质感引擎：句式节奏 + 去AI味 + 五感分配。

P0 优先级：直接影响读者第一印象的三个维度。
"""

import random


# ================================================================
# 1. 句式节奏引擎
# ================================================================

# 每个节拍预设句式策略：(短句权重, 中句权重, 长句权重, 单字独段概率)
# v2.1: 降低单字独段概率（集成模式下VoiceEngine已自带节奏）
BEAT_RHYTHM = {
    'opening':      (0.35, 0.40, 0.20, 0.06),  # 原0.15→0.06
    'theme':        (0.25, 0.45, 0.25, 0.04),  # 原0.10→0.04
    'inciting':     (0.25, 0.45, 0.25, 0.04),
    'debate':       (0.30, 0.40, 0.25, 0.05),
    'break_1':      (0.35, 0.35, 0.25, 0.08),
    'b_story':      (0.20, 0.50, 0.28, 0.02),
    'fun_games':    (0.25, 0.40, 0.30, 0.04),
    'midpoint':     (0.25, 0.45, 0.28, 0.05),
    'bad_guys':     (0.40, 0.35, 0.20, 0.10),  # 保持紧张感
    'all_lost':     (0.40, 0.35, 0.20, 0.10),
    'dark_night':   (0.20, 0.40, 0.35, 0.06),
    'break_2':      (0.25, 0.45, 0.25, 0.05),
}

# 短句模板（2-8字）
SHORT_PATTERNS = _QF['short_patterns']

# 单字独段池（精简版——只保留叙事上有意义的空白制造，删掉破坏语境的）
SINGLE_CHAR_LINES = _QF['single_char_lines']

# 长句连接词（让长句不显AI）
LONG_SENTENCE_CONNECTORS = _QF['long_sentence_connectors']


class RhythmEngine:
    """句式节奏引擎：根据节拍自动调整句长分布。"""

    def __init__(self, seed=None):
        self._rng = random.Random(seed)

    def get_weights(self, beat: str):
        """获取节拍对应的句长权重。"""
        return BEAT_RHYTHM.get(beat, (0.30, 0.40, 0.25, 0.08))

    def generate_variation(self, text: str, beat: str) -> str:
        """对一段文本进行节奏后处理。

        将已经生成的长段落按节奏权重拆分成短/中/长句混合。
        """
        weights = self.get_weights(beat)
        short_w, mid_w, long_w, single_p = weights

        # 按句号拆分，重新调整
        sentences = text.replace('！', '。').replace('？', '。').split('。')
        sentences = [s.strip() for s in sentences if s.strip()]

        result = []
        for sent in sentences:
            length = len(sent)
            roll = self._rng.random()

            if roll < single_p * 0.3:
                # 强制插入一个单字独段
                result.append(self._rng.choice(SINGLE_CHAR_LINES))
                result.append('')
                result.append(sent + '。')

            elif length > 60 and roll < 0.3:
                # 长句拆成中句 + 短句
                mid = len(sent) // 2
                result.append(sent[:mid] + '——')
                result.append(sent[mid:] + '。')

            elif length < 10:
                # 短句保留，有时加独段强调
                result.append(sent + '。')
                if self._rng.random() < single_p:
                    result.append('')

            elif length < 30:
                result.append(sent + '。')

            else:
                result.append(sent + '。')

        return '\n'.join(result)

    def inject_single_char(self, paragraphs: list, beat: str, frequency: float = 0.15) -> list:
        """在段落间注入单字独段制造空白冲击。"""
        weights = self.get_weights(beat)
        single_p = weights[3]

        result = []
        for i, para in enumerate(paragraphs):
            result.append(para)
            # 每隔若干段，按概率注入
            if (i + 1) % 4 == 0 and self._rng.random() < single_p:
                result.append(self._rng.choice(SINGLE_CHAR_LINES))
        return result


# ================================================================
# 2. 去AI味引擎
# ================================================================

# 不完整句注入模板
INCOMPLETE_SENTENCE_TEMPLATES = _QF['incomplete_sentence_templates']

# 自我纠正注入模板（对话中）
SELF_CORRECTION_TEMPLATES = _QF['self_correction_templates']

# 物理传感注入池（按感觉类型分类）
PHYSICAL_SENSATIONS = _QF['physical_sensations']


class DeAIEngine:
    """去AI味引擎：三点合一改造文本。"""

    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self._incomplete_count = 0
        self._correction_count = 0
        self._physical_count = 0

    def inject_imperfection(self, paragraphs: list, beat: str,
                            total_chars: int) -> list:
        """在段落序列中按字数密度注入不完美元素。

        每 500 字：1 句不完整句 + 1 个物理传感。
        每 800 字对话：1 次口误自我纠正。
        """
        result = []
        char_counter = 0
        incomplete_interval = 450
        physical_interval = 400

        for para in paragraphs:
            result.append(para)
            char_counter += len(para)

            if char_counter > incomplete_interval and self._rng.random() < 0.6:
                result.append(self._rng.choice(INCOMPLETE_SENTENCE_TEMPLATES))
                self._incomplete_count += 1
                char_counter = 0
                incomplete_interval = 400 + self._rng.randint(0, 200)

            if char_counter > physical_interval and self._rng.random() < 0.7:
                sense_type = self._rng.choice(list(PHYSICAL_SENSATIONS.keys()))
                result.append(self._rng.choice(PHYSICAL_SENSATIONS[sense_type]))
                self._physical_count += 1
                physical_interval = 350 + self._rng.randint(0, 200)

        return result

    def inject_dialogue_correction(self, dialogue: str) -> str:
        """在对话中按概率注入口误自我纠正。"""
        if self._rng.random() < 0.25:
            correction = self._rng.choice(SELF_CORRECTION_TEMPLATES)
            # 插入到对话中段
            sentences = dialogue.split('。')
            if len(sentences) >= 3:
                mid = len(sentences) // 2
                sentences.insert(mid, correction)
                self._correction_count += 1
                return '。'.join(sentences)
        return dialogue

    @property
    def stats(self):
        return {
            'incomplete': self._incomplete_count,
            'corrections': self._correction_count,
            'physical': self._physical_count,
        }

    # ----------------------------------------------------------------
    # 去AI味：AI腔连接词检测与清理（来自 AI 文本特征研究）
    # ----------------------------------------------------------------
    # 大模型逐字高发的机械连接词 / 空壳强调句。模板化生成本就不产出这些，
    # 该能力主要用于「安全网 + 自检」：若未来接入 LLM 润色，可即时拦截。
    AI_CLLICHE_CN = [
        '首先', '其次', '最后', '此外', '另外', '值得注意的是', '需要指出的是',
        '重要的是', '综上所述', '总而言之', '话说回来', '发挥着关键作用',
        '不可或缺的', '具有重要意义', '不难看出', '显而易见', '众所周知',
        '毋庸置疑', '在这个快节奏的时代',
    ]

    # 仅作为句首/句间起手的连接词才会被剥离（避免误伤正常叙述）
    _SCRUB_STARTERS = [
        '首先', '其次', '最后', '此外', '另外', '值得注意的是', '需要指出的是',
        '重要的是', '综上所述', '总而言之', '话说回来',
    ]

    def detect_ai_tells(self, text: str) -> list:
        """检测文本中的 AI 腔连接词，返回 [(词, 出现次数), ...]。"""
        found = []
        for w in self.AI_CLLICHE_CN:
            c = text.count(w)
            if c:
                found.append((w, c))
        return found

    def scrub_ai_tells(self, text: str) -> str:
        """剥离文本中可能残留的 AI 腔连接词（仅低误伤位置）。

        策略：
          - 句间（句号/叹号/问号/换行后紧跟的连接词）直接删除
          - 句首的连接词删除，并顺带清掉紧随其后的标点/空格
        正常叙事文本几乎不含这些起手词，因此调用本方法基本是零副作用。
        """
        import re
        cleaned = text
        for w in self._SCRUB_STARTERS:
            # 句间连接词
            cleaned = re.sub(r'([。！？!?\n])' + re.escape(w), r'\1', cleaned)
            # 句首连接词
            if cleaned.startswith(w):
                cleaned = cleaned[len(w):]
                if cleaned and cleaned[0] in '，,：: ；; ':
                    cleaned = cleaned[1:].lstrip()
        return cleaned


# ================================================================
# 3. 五感分配引擎
# ================================================================

# 每个节拍的五感分配权重
SENSE_WEIGHTS = {
    'opening':      {'视觉': 0.35, '听觉': 0.30, '触觉': 0.20, '嗅觉': 0.05, '味觉': 0.03, '体感': 0.07},
    'theme':        {'视觉': 0.45, '听觉': 0.10, '触觉': 0.15, '嗅觉': 0.05, '味觉': 0.02, '体感': 0.23},
    'inciting':     {'视觉': 0.40, '听觉': 0.20, '触觉': 0.10, '嗅觉': 0.05, '味觉': 0.05, '体感': 0.20},
    'debate':       {'视觉': 0.30, '听觉': 0.15, '触觉': 0.10, '嗅觉': 0.05, '味觉': 0.02, '体感': 0.38},
    'break_1':      {'视觉': 0.30, '听觉': 0.15, '触觉': 0.25, '嗅觉': 0.10, '味觉': 0.05, '体感': 0.15},
    'b_story':      {'视觉': 0.35, '听觉': 0.20, '触觉': 0.15, '嗅觉': 0.10, '味觉': 0.05, '体感': 0.15},
    'fun_games':    {'视觉': 0.40, '听觉': 0.30, '触觉': 0.10, '嗅觉': 0.05, '味觉': 0.05, '体感': 0.10},
    'midpoint':     {'视觉': 0.35, '听觉': 0.15, '触觉': 0.15, '嗅觉': 0.10, '味觉': 0.05, '体感': 0.20},
    'bad_guys':     {'视觉': 0.25, '听觉': 0.25, '触觉': 0.15, '嗅觉': 0.15, '味觉': 0.05, '体感': 0.15},
    'all_lost':     {'视觉': 0.20, '听觉': 0.15, '触觉': 0.20, '嗅觉': 0.10, '味觉': 0.05, '体感': 0.30},
    'dark_night':   {'视觉': 0.15, '听觉': 0.10, '触觉': 0.15, '嗅觉': 0.05, '味觉': 0.05, '体感': 0.50},
    'break_2':      {'视觉': 0.30, '听觉': 0.15, '触觉': 0.20, '嗅觉': 0.10, '味觉': 0.05, '体感': 0.20},
}

# 各感官的描写片段池
SENSE_FRAGMENTS = _QF['sense_fragments']


class SenseEngine:
    """五感分配引擎：确保每章按节拍权重分配各感官描写。"""

    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self._used_senses = {}

    def get_weights(self, beat: str) -> dict:
        return SENSE_WEIGHTS.get(beat, SENSE_WEIGHTS['opening'])

    def inject_senses(self, paragraphs: list, beat: str, total_chars: int) -> list:
        """在段落序列中按五感权重注入感官描写。

        每 ~300 字注入一条感官描写，按节拍权重分配感官类型。
        """
        weights = self.get_weights(beat)
        senses = list(weights.keys())
        probs = list(weights.values())

        result = []
        char_counter = 0
        interval = 280

        for para in paragraphs:
            result.append(para)
            char_counter += len(para)

            if char_counter > interval and self._rng.random() < 0.7:
                # 按权重选择感官类型
                sense_type = self._rng.choices(senses, weights=probs, k=1)[0]

                if sense_type in SENSE_FRAGMENTS and SENSE_FRAGMENTS[sense_type]:
                    fragment = self._rng.choice(SENSE_FRAGMENTS[sense_type])
                    result.append(fragment)
                    char_counter = 0
                    interval = 250 + self._rng.randint(0, 150)

        return result

    def audit_senses(self, text: str, beat: str) -> dict:
        """检查一段文本的五感覆盖率。

        Returns:
            {sense_type: count, 'total': total_count, 'coverage': ratio}
        """
        sense_keywords = {
            '视觉': ['看到', '看见', '望着', '盯着', '眼前', '画面', '光', '颜色'],
            '听觉': ['声音', '听到', '嗡鸣', '响声', '说话', '沉默', '静'],
            '触觉': ['冰凉', '刺痛', '握住', '碰到', '感觉', '压', '沉'],
            '嗅觉': ['气味', '闻到', '味道', '香味', '臭味', '焦味'],
            '体感': ['疲惫', '酸', '疼', '饿', '渴', '冷', '热', '跳', '呼吸'],
        }

        counts = {}
        for sense, keywords in sense_keywords.items():
            count = sum(1 for kw in keywords if kw in text)
            counts[sense] = count

        total = sum(counts.values())
        coverage = total / max(len(text) / 100, 1)
        counts['total'] = total
        counts['coverage'] = round(coverage, 2)

        return counts


# ================================================================
# 综合文本质检管道
# ================================================================

class TextQualityPipeline:
    """文本质检管道：串联节奏→去AI→五感三个引擎。"""

    def __init__(self, seed=None):
        self.rhythm = RhythmEngine(seed)
        self.deai = DeAIEngine(seed)
        self.sense = SenseEngine(seed)

    def process(self, paragraphs: list, beat: str) -> list:
        """标准管线（用于asp/causal旧模式：原始文本缺乏感官细节，需要补丁注入）。"""
        total_chars = sum(len(p) for p in paragraphs)
        paragraphs = self.sense.inject_senses(paragraphs, beat, total_chars)
        paragraphs = self.deai.inject_imperfection(paragraphs, beat, total_chars)
        paragraphs = self.rhythm.inject_single_char(paragraphs, beat)
        # 去AI腔安全网（仅当检测到AI连接词时才清理；正常生成文本本就不含，零误伤）
        paragraphs = self._safe_scrub_ai_tells(paragraphs)
        return paragraphs

    def process_light(self, paragraphs: list, beat: str) -> list:
        """轻量管线（用于integrated模式：VoiceEngine已内嵌感官+情绪，只需微量润色）。

        与标准管线的差异：
        - 五感注入频率降低80%（每1200字→1条，且只在段落边界）
        - 去AI注入频率降低60%
        - 单字独段概率降低70%
        """
        total_chars = sum(len(p) for p in paragraphs)

        # Step 1: 五感注入 — 只有总文字>1500时才触发，且只在段落间
        if total_chars > 1500:
            paragraphs = self._light_sense_inject(paragraphs, beat, total_chars)

        # Step 2: 去AI注入 — 只注入物理传感，不注入不完整句
        paragraphs = self._light_deai_inject(paragraphs, beat, total_chars)

        # Step 3: 节奏 — 单字独段概率极低
        paragraphs = self._light_rhythm_inject(paragraphs, beat)

        # Step 4: 去AI腔安全网（仅当检测到AI连接词时才清理；正常生成文本本就不含，零误伤）
        paragraphs = self._safe_scrub_ai_tells(paragraphs)

        return paragraphs

    def _light_sense_inject(self, paragraphs, beat, total_chars):
        """轻量五感：只在段落边界、低频注入。"""
        weights = self.sense.get_weights(beat)
        senses = list(weights.keys())
        probs = list(weights.values())

        result = []
        injected = 0
        max_injections = max(1, total_chars // 1200)  # 每1200字最多1条

        for i, para in enumerate(paragraphs):
            result.append(para)

            # 只在空行（段落边界）处注入
            is_boundary = (para.strip() == '' or
                          (i + 1 < len(paragraphs) and paragraphs[i + 1].strip() == '') or
                          i == len(paragraphs) - 1)

            if is_boundary and injected < max_injections and self.sense._rng.random() < 0.35:
                sense_type = self.sense._rng.choices(senses, weights=probs, k=1)[0]
                if sense_type in SENSE_FRAGMENTS and SENSE_FRAGMENTS[sense_type]:
                    fragment = self.sense._rng.choice(SENSE_FRAGMENTS[sense_type])
                    result.append(fragment)
                    injected += 1

        return result

    def _light_deai_inject(self, paragraphs, beat, total_chars):
        """轻量去AI：只注入物理传感（最有价值），不注入不完整句/自我纠正。"""
        result = []
        char_counter = 0
        max_injections = max(1, total_chars // 1000)  # 每1000字1条
        injected = 0

        for para in paragraphs:
            result.append(para)
            char_counter += len(para)

            if char_counter > 900 and injected < max_injections and self.deai._rng.random() < 0.4:
                sense_type = self.deai._rng.choice(list(PHYSICAL_SENSATIONS.keys()))
                result.append(self.deai._rng.choice(PHYSICAL_SENSATIONS[sense_type]))
                self.deai._physical_count += 1
                char_counter = 0
                injected += 1

        return result

    def _light_rhythm_inject(self, paragraphs, beat):
        """轻量节奏：单字独段概率降至原始值的30%。"""
        weights = self.rhythm.get_weights(beat)
        single_p = weights[3] * 0.3  # 降低70%

        result = []
        for i, para in enumerate(paragraphs):
            result.append(para)
            if (i + 1) % 8 == 0 and self.rhythm._rng.random() < single_p:
                result.append(self.rhythm._rng.choice(SINGLE_CHAR_LINES))
        return result

    # ================================================================
    # 去AI腔（AI连接词检测/清理）——来自写作特征研究
    # ================================================================
    def detect_ai_tells(self, text: str) -> list:
        """检测文本中的 AI 腔连接词。返回 [(词, 次数), ...]。"""
        return self.deai.detect_ai_tells(text)

    def scrub_ai_tells(self, text: str) -> str:
        """清理文本中的 AI 腔连接词（句首/句间低误伤位置）。"""
        return self.deai.scrub_ai_tells(text)

    def _safe_scrub_ai_tells(self, paragraphs: list) -> list:
        """仅当整体文本检测到 AI 连接词时，才逐段清理——正常输出零副作用。"""
        joined = '\n'.join(paragraphs)
        if not self.deai.detect_ai_tells(joined):
            return paragraphs
        return [self.deai.scrub_ai_tells(p) for p in paragraphs]

    # ================================================================
    # 逐句重复检测（P0 内容缺陷的全局安全网）
    # ================================================================
    def check_repetition(self, text: str, min_len: int = 15, top_n: int = 10) -> dict:
        """检测章节内逐字重复的整句。

        这是针对 P0 内容缺陷（硬编码情绪池逐字重复）的全局安全网：
        无论重复句来自哪个渲染器，只要在同一章节内逐字出现 >=2 次即被捕获。

        Args:
            text: 章节全文
            min_len: 仅统计长度 >= 该值的句子（过滤过短的无意义片段）
            top_n: 返回重复最多的前 N 条
        Returns:
            {
                'repeated': [(sentence, count), ...],  # 按次数降序
                'max_count': int,                       # 单句最多出现次数
                'penalty': float,                       # 去重质量扣分（0~1）
            }
        """
        import re
        # 按中英文句末标点 + 换行切分，并去除空白后用于统计
        raw_sentences = re.split(r'[。！？!?\n]', text)
        sentences = []
        for s in raw_sentences:
            s_norm = re.sub(r'\s+', '', s)
            if len(s_norm) < min_len:
                continue
            # 过滤纯标点/装饰行（如章节分隔符 ============），避免误报
            if not re.search(r'[\u4e00-\u9fffA-Za-z0-9]', s_norm):
                continue
            sentences.append(s_norm)

        counts: dict = {}
        for s in sentences:
            counts[s] = counts.get(s, 0) + 1

        repeated = [(s, c) for s, c in counts.items() if c >= 2]
        repeated.sort(key=lambda x: x[1], reverse=True)
        repeated = repeated[:top_n]
        max_count = max((c for _, c in repeated), default=0)

        # 扣分：每多一次重复递增，单句封顶 0.5，总分封顶 1.0
        penalty = 0.0
        for _, c in repeated:
            penalty += min(0.25 * (c - 1), 0.5)
        penalty = min(penalty, 1.0)

        return {
            'repeated': repeated,
            'max_count': max_count,
            'penalty': penalty,
        }

    def quality_report(self) -> dict:
        """生成质量报告。"""
        return {
            'deai_stats': self.deai.stats,
        }
