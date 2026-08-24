# -*- coding: utf-8 -*-
"""发牌员（Dealer）三层增强引擎。

对应 spec/Dealer-ML-Enhancement.md 的 Layer2 / Layer3 实现，纯标准库、零依赖、
确定性、可复现 —— 这是贯穿全项目的四条硬约束，任何一层都不得破坏。

层次结构：
  Layer1  7-bag 洗牌发牌 + 跨包接缝防涝        （已实现于 voice_engine._deal / _refill）
  Layer2  Markov 转移感知发牌                  （本文件 MarkovTransitions，本 PR 接入）
  Layer3  近义重复去重（SimHash，零依赖）      （本文件 SimHashDedup，P2 接入）

设计原则：
  - 任何一层都可独立开关；关闭时干净降级为下一层（Layer2 off → Layer1；Layer3 off → 不过滤）。
  - 转移矩阵由真实发牌序列 bootstrap 而来（见 spec §6 / P3），本文件只负责"用"。
  - weighted_choice / 洗牌均使用调用方传入的确定性 rng，保证同 seed 同输出。

item_key：把异构池元素（str / dict / lambda）映射成稳定的短键，用于转移矩阵的键与反查。
"""

import hashlib
import json
import logging
import random
from collections import defaultdict, deque

_logger = logging.getLogger(__name__)

_HASH_PREFIX_LEN = 14


def item_key(item, pool=None):
    """把池元素映射成稳定的短键，用于转移矩阵键与反查。

    - str  → md5 前缀（内容即键，跨运行稳定）
    - dict → json(sort_keys) 的 md5 前缀（同一框架内容跨运行稳定）
    - 其它（lambda / 对象）→ 用其在 pool 中的下标，保证跨运行稳定可反查
    """
    if isinstance(item, str):
        return 's' + hashlib.md5(item.encode('utf-8')).hexdigest()[:_HASH_PREFIX_LEN]
    if isinstance(item, dict):
        try:
            s = json.dumps(item, sort_keys=True, ensure_ascii=False)
        except Exception:
            s = repr(item)
        return 'd' + hashlib.md5(s.encode('utf-8')).hexdigest()[:_HASH_PREFIX_LEN]
    # 其它类型：用池内下标作稳定键（lambda 等不可哈希对象的标准做法）
    if pool is not None:
        try:
            return 'i' + str(pool.index(item))
        except (ValueError, AttributeError):
            pass
    return 'x' + hashlib.md5(repr(item).encode('utf-8')).hexdigest()[:_HASH_PREFIX_LEN]


class MarkovTransitions:
    """Layer2：马尔可夫转移感知发牌。

    转移矩阵结构：
        matrix = {
            queue_key: {
                '<json 状态元组>': { next_key: count, ... },
                ...
            },
            ...
        }
    状态元组长度从 1..order 全部记录（order fallback）：生成时优先用最长可用状态，
    稀疏时自动降到更短的前缀，直到 uniform。

    转移的"键"取自 item_key（与生成端反查逻辑一致），因此 bootstrap 与生成两端
    复用同一套键空间，保证可复现。
    """

    def __init__(self, cfg=None, matrix_path=None):
        cfg = cfg or {}
        self.enabled = bool(cfg.get('enabled', False))
        self.order = int(cfg.get('order', 2))
        self.alpha = float(cfg.get('alpha', 0.5))
        # source：转移矩阵文件路径；'auto' / 'bootstrap' 表示运行时由 bootstrap 注入
        self.source = cfg.get('source')
        self.matrix = {}
        self._loaded = False
        self._matrix_path = matrix_path
        if self.source and self.source not in ('auto', 'bootstrap'):
            self.load(self.source)

    # ----------------------------------------------------------------
    # 持久化
    # ----------------------------------------------------------------
    def load(self, path):
        """从 JSON 载入转移矩阵。失败（文件缺失/损坏）时降级为空矩阵，不抛异常。"""
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            self.matrix = data.get('matrix', {})
            meta = data.get('meta', {})
            if 'order' in meta:
                self.order = int(meta['order'])
            if 'alpha' in meta:
                self.alpha = float(meta['alpha'])
            self._loaded = True
        except Exception as e:
            _logger.debug('MarkovTransitions.load 失败(%s): %s', path, e)
            self.matrix = {}

    def save(self, path):
        """把转移矩阵落盘为 JSON（供 P3 bootstrap_dealer 调用）。"""
        data = {
            'meta': {'order': self.order, 'alpha': self.alpha},
            'matrix': self.matrix,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

    # ----------------------------------------------------------------
    # 由真实发牌日志构建矩阵（P3 bootstrap 调用）
    # deal_log: list of (queue_key, key)，按发生顺序排列
    # ----------------------------------------------------------------
    def build_from_log(self, deal_log):
        seqs = defaultdict(list)
        for qk, key in deal_log:
            seqs[qk].append(key)

        matrix = {}
        for qk, keys in seqs.items():
            table = defaultdict(lambda: defaultdict(int))
            n = len(keys)
            for i in range(n):
                for k in range(1, self.order + 1):
                    if i - k < 0:
                        continue
                    state = tuple(keys[i - k:i])
                    sk = json.dumps(list(state), ensure_ascii=False)
                    table[sk][keys[i]] += 1
            matrix[qk] = {s: dict(v) for s, v in table.items()}
        self.matrix = matrix
        return matrix

    # ----------------------------------------------------------------
    # 生成端：加权采样
    # ----------------------------------------------------------------
    def has_data(self, queue_key):
        return bool(self.matrix.get(queue_key))

    def weighted_choice(self, queue_key, state_key, cand_keys, rng):
        """在候选键中按转移计数 + Laplace 平滑做加权采样，返回选中的键。"""
        trans = self.matrix.get(queue_key, {}).get(state_key, {})
        weights = [trans.get(k, 0) + self.alpha for k in cand_keys]
        total = sum(weights)
        if total <= 0:
            return cand_keys[rng.randrange(len(cand_keys))]
        r = rng.random() * total
        acc = 0.0
        for k, w in zip(cand_keys, weights):
            acc += w
            if r <= acc:
                return k
        return cand_keys[-1]


class SimHashDedup:
    """Layer3：基于 SimHash 的近义重复去重（零依赖，纯标准库）。

    思路：把每条文本（字符 bigram 特征）压缩成 64-bit 指纹；维护一个滑动语义记忆窗口，
    新文本指纹与窗口内任一条的汉明距离低于阈值 → 判定为近义重复，应被拒。

    阈值：similarity = 1 - hamming/bits，threshold(默认 0.82) → 汉明上限 = (1-0.82)*64 ≈ 11。
    非 str 元素（dict / lambda）无法指纹化 → is_near_dup 一律放行（由调用方决定是否过滤）。
    """

    def __init__(self, cfg=None):
        cfg = cfg or {}
        self.enabled = bool(cfg.get('enabled', False))
        self.threshold = float(cfg.get('threshold', 0.82))
        self.window = int(cfg.get('window', 24))
        self.bits = 64
        self._ham_thresh = max(1, int((1.0 - self.threshold) * self.bits))
        self._memory = deque(maxlen=self.window)

    # ----------------------------------------------------------------
    # 指纹
    # ----------------------------------------------------------------
    def _fingerprint(self, text):
        if not isinstance(text, str) or not text:
            return None
        vec = [0] * self.bits
        feats = {text[i:i + 2] for i in range(len(text) - 1)}
        if not feats:  # 单字符
            feats = {text}
        for feat in feats:
            h = int(hashlib.md5(feat.encode('utf-8')).hexdigest(), 16)
            for b in range(self.bits):
                if (h >> b) & 1:
                    vec[b] += 1
                else:
                    vec[b] -= 1
        fp = 0
        for b in range(self.bits):
            if vec[b] > 0:
                fp |= (1 << b)
        return fp

    @staticmethod
    def _hamming(a, b):
        x = a ^ b
        c = 0
        while x:
            x &= x - 1
            c += 1
        return c

    # ----------------------------------------------------------------
    # 判定 + 记忆
    # ----------------------------------------------------------------
    def is_near_dup(self, text):
        """返回 True 表示与记忆窗口内某条「近义但非完全相同」的文本（应被拒）。

        关键：hamming == 0（完全相同的文本）不判近义 —— 那种逐字重复由 Layer1
        的 7-bag 负责（每包内每元素恰好一次），交给它处理即可；若此处也拦截，
        会导致「同一句每包复现」被误判为近义、进而把所有候选都标记成近义、
        找不到任何可换的牌，使去重层彻底失效（实测死锁）。本层只拦截「不同的句子
        却意思相近」（0 < hamming <= 阈值）。
        非 str 一律放行（无法指纹化）。
        """
        fp = self._fingerprint(text)
        if fp is None:
            return False
        for mem_fp in self._memory:
            h = self._hamming(fp, mem_fp)
            if 0 < h <= self._ham_thresh:
                return True
        return False

    def remember(self, text):
        """把一条文本指纹写入语义记忆窗口。非 str 忽略。"""
        fp = self._fingerprint(text)
        if fp is not None:
            self._memory.append(fp)


class Dealer:
    """统一发牌员（Layer1 逻辑链的规范化实现）：Fisher–Yates 洗牌 → 无放回 7-bag → 跨包接缝防涝。

    「完全随机发牌」的正确实现 = 无放回 bag，而不是 random.choice（有放回）。
    有放回纯随机反而制造「旱」（长期不出某牌）与「涝」（连续重复）；无放回 bag 把
    最坏幅度硬约束在 包容量-1（Tetris 7-bag 结论）。跨包接缝防涝保证新包首张 !=
    上一张（TGM history-reroll / classic 避免紧邻重复随机器结论）。

    本类作为编排层（世界 / 段落类型 / 算子类型）的唯一随机源；内容层
    VoiceEngine._deal 复用同一条逻辑链（并在其上叠加可选的 Layer2/3）。
    确定性：同 seed 同输出；零依赖。
    """

    def __init__(self, seed=None, rng=None):
        self._rng = rng if rng is not None else random.Random(seed)
        self._queues = {}
        self._last = {}

    def deal(self, queue_key: str, pool: list, take: int = 1):
        """按 queue_key 独立维护牌包，无放回发牌，发完重洗。

        返回单张（take==1）或列表（take>1）；跨重洗时避让上一张（防涝）。
        """
        if not pool:
            return '' if take == 1 else []
        picked = []
        for _ in range(take):
            q = self._queues.get(queue_key)
            if not q:
                q = self._refill(queue_key, pool)
                self._queues[queue_key] = q
            item = q.pop()
            self._last[queue_key] = item
            picked.append(item)
        return picked[0] if take == 1 else picked

    def _refill(self, queue_key: str, pool: list):
        """重洗一整包（Fisher–Yates 洗牌），并做跨包接缝防涝：新包末位（下一张将发出的牌）!= 上一张。"""
        if len(pool) <= 1:
            return list(pool)
        last = self._last.get(queue_key)
        q = self._rng.sample(list(pool), len(pool))
        attempts = 0
        while last is not None and q[-1] == last and attempts < len(pool) * 2:
            q = self._rng.sample(list(pool), len(pool))
            attempts += 1
        return q
