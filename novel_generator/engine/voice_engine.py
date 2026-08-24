# -*- coding: utf-8 -*-
"""VoiceEngine —— ASP词库的上下文感知渲染层。

这是双引擎融合的"声音"——因果引擎说"应该有一个震撼的归墟场景"，VoiceEngine就用
归墟世界的五感词库、当前的情绪基调、角色的状态，渲染出具体的文字。

核心能力：
  - render_scene()     — 根据世界+情绪渲染场景段落
  - render_action()    — 根据角色+情绪+性格标签渲染动作
  - render_emotion()   — 用身体反应渲染情绪，而非直接命名
  - render_dialogue()  — 话轮生成，自动注入角色声纹
  - render_reveal()    — 千层饼信息揭示
  - render_player_chaos() — 玩家沙雕行为
"""

import random
import json
import logging
import re
from collections import deque

from .word_bank import WordBank
from .dealer import item_key, MarkovTransitions, SimHashDedup

_logger = logging.getLogger(__name__)
from .narrative_context import NarrativeContext, CharacterSnapshot, WORLD_PROSE_NAMES
from .causal_dialogue import CausalDialogueEngine
from .plot_state import PlotState

# 世界 → 专用术语词库映射（审计第3条：诸天世界差异性）。
# 每个世界绑定一个术语词库文件 + 一个"成句"子池（atmosphere / space_atmosphere /
# battle_atmosphere）——这些池里存的是**完整句子**，且已自然嵌入该世界的领域术语
# （赛博都市的"他的义眼闪过一道红光"、克苏鲁的"低语声…"、星际的"跃迁倒计时…"、
# 末日的"盖革计数器…疯狂尖叫"）。此前这些词库只在"世界入场横幅"里抽 1 句，
# 章节正文的感官描写完全取自通用五感池 → 术语（义眼/旧日支配者/跃迁引擎/盖革计数器）
# 根本不落地。第3条修复 = 让它们进入正文（见 render_world_flavour）。
WORLD_TERM_BANKS = {
    '归墟': ('wanjie_context', 'guixu_atmosphere'),
    '东方修仙': ('cultivation_terms', 'atmosphere'),
    '武侠·苍云之殇': ('wuxia_terms', 'battle_atmosphere'),
    '赛博都市': ('cyberpunk_terms', 'atmosphere'),
    '克苏鲁深渊': ('cthulhu_terms', 'atmosphere'),
    '星际殖民': ('scifi_terms', 'space_atmosphere'),
    '末日废土': ('post_apocalyptic_terms', 'atmosphere'),
    # 第二轮扩充：补齐此前无专用词库的 6 个世界 + 新增 4 个世界类型
    '近代乱世': ('modern_china_terms', 'atmosphere'),
    '低魔中世纪': ('lowmagic_medieval_terms', 'atmosphere'),
    '剑与魔法': ('sword_magic_terms', 'atmosphere'),
    '诸神黄昏': ('ragnarok_terms', 'atmosphere'),
    '高等文明实验场': ('high_civ_lab_terms', 'atmosphere'),
    '造物主遗迹': ('creator_ruins_terms', 'atmosphere'),
    '深海遗迹': ('deep_sea_ruins_terms', 'atmosphere'),
    '机械神域': ('mech_divinity_terms', 'atmosphere'),
    '蒸汽朋克': ('steampunk_terms', 'atmosphere'),
    '无限流': ('infinite_flow_terms', 'atmosphere'),
    '魔法学院': ('magic_academy_terms', 'atmosphere'),
    '修仙界': ('cultivation_terms', 'atmosphere'),
}

# 惰性校验：检查第二轮扩充的 10 个词库是否真实存在，缺失时记录 WARNING
# 而非在 render_world_flavour 中静默吞掉异常。
_validated = False
_missing_banks: set[str] = set()


def _validate_world_term_banks(wb: WordBank):
    """惰性校验 WORLD_TERM_BANKS 中所有词库是否存在（仅首次调用时执行）。"""
    global _validated, _missing_banks
    if _validated:
        return
    _validated = True
    for world, (bank_name, key) in WORLD_TERM_BANKS.items():
        try:
            data = wb.load(bank_name)
            if key not in data or not data.get(key):
                _logger.warning(
                    '世界 [%s] 的术语词库 %s 中缺少键 %s 或为空——该世界在正文中不会有专用氛围描写',
                    world, bank_name, key,
                )
                _missing_banks.add(world)
        except Exception as e:
            _logger.warning(
                '世界 [%s] 的术语词库 %s 加载失败: %s——该世界在正文中将无专用氛围描写',
                world, bank_name, e,
            )
            _missing_banks.add(world)


class VoiceEngine:
    """上下文感知的ASP词库渲染引擎。"""

    def __init__(self, wb: WordBank, plot_state: PlotState, seed=None, dealer_cfg=None):
        self._wb = wb
        self._ps = plot_state
        # 惰性校验词库存在性（仅首次实例化时执行一次）
        _validate_world_term_banks(wb)
        self._dlg = CausalDialogueEngine(wb, plot_state)
        self._rng = wb.get_rng()
        self._seed_value = seed
        self._seed_rng = random.Random(seed) if seed else wb.get_rng()
        # —— 发牌员三层增强（spec/Dealer-ML-Enhancement.md）——
        # dealer_cfg 为 None / markov.enabled=False → 全部降级为 Layer1（7-bag），
        # 输出与改造前逐字节一致（_deal 走 base 路径）。
        self._dealer_cfg = dealer_cfg or {}
        mc = self._dealer_cfg.get('markov')
        self._markov = MarkovTransitions(mc) if (mc and mc.get('enabled')) else None
        ec = self._dealer_cfg.get('embedding_dedup')
        self._dedup = SimHashDedup(ec) if ec else None
        # 发牌日志：bootstrap（P3）时开启，记录 (queue_key, item_key) 序列
        self._record_deals = bool(self._dealer_cfg.get('record', False))
        self._deal_log = []
        # 整实例级去重集合：同一情绪文本在池内全部用尽前不会再次输出，
        # 从根本上杜绝「同一句每两三章重复一次」的逐字重复问题。
        self._used_emotions = set()
        # 章末钩子去重集合（与情绪池同样的策略，避免钩子逐章重复）
        self._used_hooks = set()
        # 玩家沙雕行为模板：洗牌发牌队列（整实例持久），替代 random.choice 有放回。
        # 每轮对 chaos_templates 洗牌后无放回发牌，发完再洗；单模板最大出现次数被限制在
        # ceil(总发牌数 / 模板数) 以内，从根上消除「某条谣言模板跨章 6× 逐字重复」。
        self._chaos_rng = random.Random((seed * 7 + 13) if seed is not None else 12345)
        self._chaos_queue = []
        self._chaos_pos = 0
        # 跨包接缝防涝：记录上一张发出的 chaos 模板，用于重洗时避让紧邻重复
        self._chaos_last = None

    # ================================================================
    # 场景渲染
    # ================================================================
    def render_opening_scene(self, ctx: NarrativeContext) -> list:
        """渲染章节开场场景——世界初现，全部从 world_openings 词库发牌（拆硬编码）。

        归墟不再走写死的 3 段开场（_render_guixu_opening 已废除），改为从
        world_openings.json 的「归墟」池（1223 条）发牌，与其余 18 个世界同源。
        """
        return self.render_world_entry(ctx.world_name)

    def render_world_entry(self, world_name: str) -> list:
        """为指定世界渲染首次进入的文本。"""
        world_openings = self._wb.load('world_openings')

        entry = world_openings.get(world_name)
        result = [f'——{world_name}——', '']
        if entry:
            result.extend(entry)

        # 内容扩充：从对应世界的专用术语词库（全键合并）抽 1 句氛围描写
        if world_name in WORLD_TERM_BANKS:
            try:
                pool = self._world_term_pool(world_name)
                if pool:
                    result.append('')
                    result.append(self._deal(f'worldflavour::{world_name}', pool))
            except Exception as e:
                _logger.warning('render_world_entry 词库氛围注入失败(%s): %s', world_name, e)

        return result

    # OpType → 主题键偏置映射（Layer 2：操作类型与术语领域对齐）
    # 键名包含以下模式时对该 OpType 加权 2×，不匹配的键保持 1× 权重
    _OP_KEY_BIAS = {
        'SCENE': ('atmosphere', 'space_atmosphere', 'battle_atmosphere',
                  'locations', 'urban_terms', 'colony_terms', 'realm_terms', 'street_terms'),
        'ACTION': ('techniques', 'martial_styles', 'inner_power', 'cyberware',
                   'hacker_terms', 'tech_terms', 'survival_terms', 'knight_terms',
                   'sword_terms', 'magic_terms', 'cultivation_terms', 'items'),
        'BATTLE': ('weapon_terms', 'spaceship_terms', 'alien_terms', 'creature_terms',
                   'beast_terms', 'guardian_terms', 'construct_terms', 'gear_terms'),
        'DIALOGUE': ('sects', 'sect_names', 'corporate_terms', 'faction_terms',
                     'guild_terms', 'cults', 'class_terms', 'faith_terms'),
        'REVEAL': ('mystery_terms', 'madness_terms', 'doom_terms', 'paradox_terms',
                   'rule_terms', 'relic_terms', 'abyss_terms', 'entity_terms'),
    }

    def _world_term_pool(self, world_name: str, op_type: str = None) -> list:
        """返回指定世界的术语条目池（遍历 genre_terms JSON 所有键）。

        此前 WORLD_TERM_BANKS 每个世界只取 atmosphere 单一键 ~100-200 条，
        丢死了境界/功法/义体/企业/实体/飞船等其余 4-5 个主题键共 ~15,768 条。

        Parameters:
            world_name: 世界名
            op_type: 可选，按 OpType 对相关主题键加权（Layer 2）：匹配的键权重 2×，
                     非匹配键权重 1×。为 None 时所有权重相等（Layer 1 行为）。
        """
        if world_name not in WORLD_TERM_BANKS:
            return []
        bank_name, _ = WORLD_TERM_BANKS[world_name]
        try:
            data = self._wb.load(bank_name)
            pool = []
            bias_keys = self._OP_KEY_BIAS.get(op_type, ()) if op_type else ()

            for k, v in data.items():
                if not isinstance(v, list):
                    continue
                # Layer 2 偏置：匹配 op_type 的主题键条目重复一次（2× 权重）
                weight = 2 if bias_keys and any(pattern in k for pattern in bias_keys) else 1
                for _ in range(weight):
                    pool.extend(v)

            # Layer 3: 缓存到实例（避免同一世界重复加载）
            if not hasattr(self, '_world_term_cache'):
                self._world_term_cache = {}
            # 无偏置的完整池做缓存键（op_type=None 的结果）
            if op_type is None:
                self._world_term_cache[world_name] = pool
            return pool
        except Exception:
            return []

    def render_world_flavour(self, ctx: NarrativeContext, prob: float = 0.6,
                             op_type: str = None) -> str:
        """章内世界质感注入（审计第3条核心 + Layer 2 OpType 偏置）。

        对于绑定了专用术语词库的世界，以一定概率额外抽出 1 句该世界的描写。
        op_type 参数（如 'SCENE'/'ACTION'/'BATTLE'）使采样偏向该操作类型的
        相关术语领域——例如 BATTLE 操作更倾向从 weapon_terms/creature_terms
        中抽词条而非通用 atmosphere。
        """
        world = ctx.world_name
        if world not in WORLD_TERM_BANKS:
            return ''
        if self._seed_rng.random() > prob:
            return ''
        try:
            pool = self._world_term_pool(world, op_type=op_type)
            if not pool:
                return ''
            return self._deal(f'worldflavour::{world}', pool)
        except Exception as e:
            _logger.warning('render_world_flavour 词库注入失败(%s): %s', world, e)
            return ''

    def render_world_term(self, ctx: NarrativeContext, op_type: str = None) -> str:
        """Layer 3：按 op_type 从 ctx.world_terms 缓存中取一条世界术语。

        与 render_world_flavour 不同——本方法不走 _deal 队列，而是用
        _seed_rng 直接从预加载的 ctx.world_terms 缓存中随机抽取。
        因此不会消耗发牌队列的 bag 不变量，适合作为「即兴调味」在任意
        算子中低成本调用（每段至多 1 次，概率控制由调用方负责）。

        如果 ctx.world_terms 为空（未预加载），回退到 _world_term_pool。
        """
        pool = ctx.world_terms if ctx.world_terms else []
        if not pool and ctx.world_name in WORLD_TERM_BANKS:
            # 回退：检查缓存 → 首次加载
            cache = getattr(self, '_world_term_cache', {})
            world = ctx.world_name
            if world in cache:
                pool = cache[world]
            else:
                pool = self._world_term_pool(world, op_type=op_type)
        if not pool:
            return ''
        return self._seed_rng.choice(pool)

    def render_text_snippet(self, ctx: NarrativeContext, prob: float = 0.35) -> str:
        """为 TEXT 叙事注入世界感官细节，对所有世界有效。

        术语词库世界（赛博/克苏鲁/星际等）→ render_world_flavour
        非术语词库世界（归墟/乱世/中世纪等）→ 五感池取一条感官描写

        用固定概率控制注入密度，避免每段都需要追加，使文本更自然。
        """
        if self._seed_rng.random() > prob:
            return ''
        world = ctx.world_name

        # 术语词库世界：复用已有方法
        if world in WORLD_TERM_BANKS:
            return self.render_world_flavour(ctx, prob=1.0)

        # 非术语词库世界：用五感池生成一条感官片段
        modalities = ['visual', 'auditory', 'olfactory', 'tactile']
        modality = self._seed_rng.choice(modalities)
        sense = self._sense(modality, world)
        if sense and sense != '——':
            return f'{sense}。'
        return ''

    # ================================================================
    # 中途场景节拍渲染（ASP 引擎主力产能）
    # ================================================================
    def render_scene_beat(self, ctx: NarrativeContext, scene_type: str = None) -> list:
        """渲染章节中段的环境节拍——不是世界入场横幅。

        与 render_opening_scene 的区别：
          - render_opening_scene 打「——世界名——」横幅，语义是"首次进入某世界"，
            一章内多次调用会反复打横幅，因此编排层长期只敢用 8 次；
          - render_scene_beat 输出纯散文环境句，可在一章内多次穿插。

        实现要点：
          - 从 world_senses[world] 中挑**两个不同感官类型**各取一条碎片，塞进
            scene_beats 的句式框架 → 组合空间 = 框架数 × 感官对数，远大于任一
            单库容量，这是压低跨章逐字重复的根本手段；
          - 框架按 tension_level 分档（calm/tense/dark），保证环境描写与因果引擎
            给出的张力同步——这正是"融合"应有的样子：因果定调，词库出声；
          - 框架与感官碎片各自独立洗牌发牌（无放回），杜绝有放回采样导致的高频重复。
        """
        world = ctx.world_name
        senses = self._world_sense_pools(world)
        if not senses:
            return []

        bank = self._wb.load('scene_beats')
        band = self._tension_band(ctx.tension_level)

        # 具体落点（P0）：主导角色 location（清洗后）> 本章 scene_spot > 世界名。
        spot = self._resolve_scene_spot(ctx)

        # 只保留该世界实际具备、且槽位类型全部可满足的框架。
        # 这一步是质量红线：框架的语义与感官类型强绑定（「{s1}盖过了一切。他连自己
        # 的呼吸都听不见」只能填听觉），若不做类型校验就会产出「净水器的水有金属味
        # 盖过了一切」这种语义崩坏的句子。'spot' 是落点槽位（非感官），不参与感官校验。
        normal_pool = self._eligible_frames(bank.get('frames', {}).get(band, []), senses)
        spot_pool = []
        if spot:
            spot_pool = self._eligible_frames(bank.get('spot_frames', {}).get(band, []), senses)
        # 有落点时 70% 概率用落地框架（把镜头落到具体地点），否则用通用框架；
        # 两者用不同洗牌队列（frame:: vs spotframe::），避免队列混用导致落点失效。
        if spot_pool and (not normal_pool or self._seed_rng.random() < 0.7):
            pool = spot_pool
            frame = self._deal(f'spotframe::{band}::{world}', pool)
        else:
            pool = normal_pool or self._eligible_frames(bank.get('single_sense_frames', []), senses)
            if not pool:
                return []
            frame = self._deal(f'frame::{band}::{world}', pool)

        text = frame.get('text', '')
        slots = frame.get('slots', [])
        fill = {'world': world, 'spot': spot}
        for i, sense_type in enumerate(slots, start=1):
            if sense_type == 'spot':
                continue
            token = '{s%d}' % i
            fill[f's{i}'] = self._deal_fragment(
                f'sense::{world}::{sense_type}', senses[sense_type], text, token
            )
        # {r} = 内心反应句。与框架**独立**发牌：框架尾句若焊死在框架里，
        # 一个框架被用 N 次它就逐字复读 N 次（实测 x9）。拆成共享池之后，
        # 组合空间 = 框架数 × 反应数，且反应句自身的复用被池容量硬压住。
        if '{r}' in text:
            reactions = bank.get('reactions', {}).get(band, [])
            fill['r'] = self._deal(f'reaction::{band}', reactions) if reactions else ''
        try:
            return [frame['text'].format(**fill)]
        except KeyError as e:
            _logger.debug('render_scene_beat 框架占位符缺失(%s): %s', e, frame.get('text'))
            return []

    # 感官池小于该阈值的类型不参与常规选取：池子太小（如多数世界的 taste 仅 1-3 条）
    # 会让同一碎片被反复发牌，反而制造新的逐字重复源。
    _MIN_SENSE_POOL = 3

    def _deal_fragment(self, queue_key: str, pool: list, text: str, token: str) -> str:
        """发一条感官碎片，并做两项贴合度校验，不合格则最多重发 3 次。

        1) 破句校验：若占位符后面还有话（不是紧跟句号收尾），含破折号的长碎片会把
           句子撑断——「灰黄色的天空——核冬天之后没有真正的蓝色在他眼里失去了颜色」；
        2) 叠词校验：碎片开头若与占位符前的文字重复，会读出「空气里是空气稀薄……」。
        """
        idx = text.find(token)
        tail = text[idx + len(token):] if idx >= 0 else ''
        head = text[:idx] if idx >= 0 else ''
        mid_sentence = bool(tail) and tail[0] not in '。！？'

        candidate = ''
        for _ in range(3):
            candidate = self._deal(queue_key, pool)
            if mid_sentence and '——' in candidate:
                continue
            if head and candidate[:2] and head.endswith(candidate[:2]):
                continue
            return candidate
        return candidate

    def _eligible_frames(self, frames: list, senses: dict) -> list:
        """筛出槽位感官类型在当前世界均可满足的框架。"""
        usable = {t for t, pool in senses.items() if len(pool) >= self._MIN_SENSE_POOL}
        result = []
        for f in frames:
            if not isinstance(f, dict):
                continue
            slots = f.get('slots', [])
            if slots and all((s in usable) or s == 'spot' for s in slots):
                result.append(f)
        return result

    def _world_sense_pools(self, world: str) -> dict:
        """取某世界的五感词池（type -> [碎片]）。"""
        try:
            data = self._wb.load_world_senses()
            return {k: v for k, v in data['worlds'].get(world, {}).items() if v}
        except Exception as e:
            _logger.debug('_world_sense_pools(%s) 加载失败: %s', world, e)
            return {}

    @staticmethod
    def _tension_band(level: int) -> str:
        """张力等级 → 句式档位。因果引擎的 tension_level 直接驱动 ASP 的措辞。"""
        if level >= 8:
            return 'dark'
        if level >= 5:
            return 'tense'
        return 'calm'

    def _deal(self, queue_key: str, pool: list, take: int = 1):
        """洗牌发牌：按 queue_key 维护独立队列，无放回发牌，发完重洗（bag randomizer）。

        相比 random.choice（有放回），本策略把单条目的出现次数硬约束在
        ceil(总发牌数 / 池容量) 以内——这是治理跨章逐字重复的正确做法，
        单纯往池子里加变体只能稀释概率，压不住采样方差。

        强化（联网调研 7-bag / TGM history-reroll 随机器后引入）：
          - 每个 queue_key 一张「牌包」，洗牌后无放回发牌，发完重洗一整包；
            包内每元素恰好出现一次 → 天然限制「旱」（长期不出）与「涝」（连续重复）
            的最严重幅度为 包容量-1（参考 Tetris 7-bag：7 种各一包，连续同块存在上界）。
          - 跨包接缝防涝（anti-flood seam guard）：重洗新包时，保证「新包第一张发出的牌」
            不等于上一张发出的牌（pool>1 时）。否则旧包最后一张与新包第一张可能撞同值，
            造成跨包紧邻重复——这正是 TGM 历史重摇 / classic「避免紧邻重复」随机器
            要消除的「涝」现象（详见 test_deal_no_immediate_repeat_across_seam）。

        Layer2 增强（spec Dealer-ML-Enhancement，默认关闭）：
          - 当 dealer_cfg.markov.enabled 为真且已加载转移矩阵时，从当前牌包剩余牌中
            按「上一张 → 下一张」的转移计数加权选牌（拉普拉斯平滑 + order fallback），
            使相邻发牌更符合语感。此操作只在牌包**内部**重排发牌顺序，不改变牌包内容，
            因此 bag 不变量（每元素每包恰好一次）与接缝防涝均不被破坏。
          - dealer_cfg 关闭 / 无转移数据时，本方法走 base 路径（q.pop()），与改造前
            逐字节一致。
        """
        if not pool:
            return '' if take == 1 else []
        if not hasattr(self, '_deal_queues'):
            self._deal_queues = {}
            # 跨包接缝防涝：记录每个队列上一张发出的牌，用于重洗时避让
            self._deal_last = {}
            # 马尔可夫状态窗口：维护最近 order 张发出牌的键，用于 Layer2 状态
            self._deal_window = {}
            # 使用实例 seed 派生 deal_rng，使每轮运行产生不同的发牌顺序
            # （此前硬编码为 20260804，导致无论传什么 --seed 都得到相同的输出）
            _deal_seed = (self._seed_value * 13 + 7) if self._seed_value is not None else None
            self._deal_rng = random.Random(_deal_seed)

        picked = []
        for _ in range(take):
            q = self._deal_queues.get(queue_key)
            if not q:
                q = self._refill(queue_key, pool)
                self._deal_queues[queue_key] = q
            item = self._choose_from_bag(queue_key, pool, q)
            self._deal_last[queue_key] = item
            # 维护马尔可夫状态窗口（最近 order 张键）
            w = self._deal_window.get(queue_key)
            if w is None:
                maxlen = max(2, self._markov.order) if self._markov else 2
                w = self._deal_window[queue_key] = deque(maxlen=maxlen)
            w.append(item_key(item, pool))
            if self._record_deals:
                self._deal_log.append((queue_key, item_key(item, pool)))
            picked.append(item)
        return picked[0] if take == 1 else picked

    def _choose_from_bag(self, queue_key: str, pool: list, q: list):
        """Layer2 发牌：从牌包剩余牌中按马尔可夫转移加权选一张。

        返回选中的牌并从 q 中移除。满足以下降级条件之一即回退 base 路径（q.pop()）：
          - Layer2 未启用（self._markov is None）
          - 该队列无转移数据（bootstrap 尚未覆盖）
          - 牌包剩余 <= 1 张
          - 剩余牌的键存在冲突（如池含重复元素）→ 无法可靠反查
        降级时与改造前完全一致（pop 末尾），保证确定性不被破坏。
        """
        mk = self._markov
        if mk is None or not mk.enabled or not mk.has_data(queue_key) or len(q) <= 1:
            return q.pop()

        rem_keys = [item_key(it, pool) for it in q]
        if len(set(rem_keys)) != len(rem_keys):
            return q.pop()  # 键冲突，安全回退
        window = list(self._deal_window.get(queue_key, []))
        chosen_key = None
        # order fallback：优先用最长可用状态，稀疏时逐级缩短
        for k in range(mk.order, 0, -1):
            if len(window) >= k:
                state = tuple(window[-k:])
                sk = json.dumps(list(state), ensure_ascii=False)
                if sk in mk.matrix.get(queue_key, {}):
                    chosen_key = mk.weighted_choice(queue_key, sk, rem_keys, self._deal_rng)
                    break
        if chosen_key is None:
            # 无任何状态命中 → 牌包内均匀重排（仍确定性，使用 deal_rng）
            chosen_key = rem_keys[self._deal_rng.randrange(len(rem_keys))]
        idx = rem_keys.index(chosen_key)
        return q.pop(idx)

    # ----------------------------------------------------------------
    # 发牌日志（供 P3 bootstrap_dealer 收集转移矩阵）
    # ----------------------------------------------------------------
    def begin_deal_recording(self):
        """开启发牌日志录制（覆盖式）。"""
        self._record_deals = True
        self._deal_log = []

    def end_deal_recording(self):
        """关闭录制并返回已收集的发牌日志 [(queue_key, key), ...]。"""
        self._record_deals = False
        return list(self._deal_log)

    def _refill(self, queue_key: str, pool: list):
        """重洗一整包（无放回）。pool<=1 直接返回原池；否则带跨包防涝避让：

        新包「第一张发出的牌」是洗牌列表的末尾（_deal 用 q.pop() 取末尾），
        故保证新包末尾 != 上一张发出的牌，消除跨包紧邻重复。

        Layer3（近义去重，默认关闭）：若启用，在洗牌后再做一次「近义分离」重排——
        保证袋内任意相邻两张不近义、且袋首（将发出的第一张）不与跨包接缝上一张近义。
        此重排只改变袋内顺序、不改变袋内容，bag 不变量不变。
        """
        if len(pool) <= 1:
            return list(pool)
        last = self._deal_last.get(queue_key)
        q = self._deal_rng.sample(list(pool), len(pool))
        # 避让：重洗直到新包末尾（即下一张将发出的牌）!= 上一张；上界 2*pool 次必停。
        attempts = 0
        while last is not None and q[-1] == last and attempts < len(pool) * 2:
            q = self._deal_rng.sample(list(pool), len(pool))
            attempts += 1
        # Layer3：近义分离重排
        if self._dedup is not None and self._dedup.enabled:
            q = self._separate_near_dups(queue_key, q)
        return q

    def _near_dup(self, a, b) -> bool:
        """两元素是否近义（SimHash 汉明距离在 (0, 阈值]）。非 str / 无法指纹化 → False。
        0 距离（完全相同）排除：逐字重复由 Layer1 的 7-bag 负责。"""
        d = self._dedup
        if d is None or not (isinstance(a, str) and isinstance(b, str)):
            return False
        fa, fb = d._fingerprint(a), d._fingerprint(b)
        if fa is None or fb is None:
            return False
        h = d._hamming(fa, fb)
        return 0 < h <= d._ham_thresh

    def _separate_near_dups(self, queue_key: str, q: list) -> list:
        """Layer3：贪心重排，保证袋内无相邻近义、且首张（pop 末尾）不与接缝上一张近义/相同。

        关键：_deal 用 q.pop() 从「末尾」发牌，故首张 = 返回列表的末尾。本函数把
        接缝安全元素固定在 result[0]，最后整体反转，使其落到末尾（首张）位置。

        贪心每一步都挑一张不与「已排好的上一张」近义的元素接在末尾；若全部近义
        （池内近义过密）才降级接受。确定性（不引入 rng），故同 seed 输出可复现。
        返回新顺序的袋（内容集合不变）。
        """
        items = list(q)
        prev = self._deal_last.get(queue_key)
        # 接缝：将发出的第一张是 result[0]（反转后落到末尾 = 首张），须不与上一张
        # 完全相同（逐字重复由 7-bag 已间隔，但仍兜底）也不近义。
        if prev is not None and (items[-1] == prev or self._near_dup(items[-1], prev)):
            for i in range(len(items) - 1):
                if not (items[i] == prev or self._near_dup(items[i], prev)):
                    items[i], items[-1] = items[-1], items[i]
                    break
        # 袋内贪心：从 items[-1] 起，每次接一张不与当前末尾近义的元素
        result = [items[-1]]
        remaining = items[:-1]
        while remaining:
            idx = next((i for i, x in enumerate(remaining)
                        if not self._near_dup(x, result[-1])), 0)
            result.append(remaining.pop(idx))
        # 反转：让接缝安全元素（result[0]）落到末尾 = _deal 首张位置
        return result[::-1]

    def _deal_chaos(self, pool: list):
        """chaos 模板的洗牌发牌（bag + 跨包防涝），与 _deal 同源思路、独立 RNG 流。

        返回下一张模板（str）。pool<=1 直接返回原池首元素。
        跨包接缝防涝：重洗时保证新包第一张 != 上一张发出的模板（pool>1 时），
        消除 chaos 模板跨重洗的紧邻重复（TGM history-reroll / classic 思路）。
        """
        if not pool:
            return ''
        if self._chaos_pos >= len(self._chaos_queue):
            new_q = self._chaos_rng.sample(list(pool), len(pool))
            if len(pool) > 1 and self._chaos_last is not None:
                attempts = 0
                while new_q[0] == self._chaos_last and attempts < len(pool) * 2:
                    new_q = self._chaos_rng.sample(list(pool), len(pool))
                    attempts += 1
            self._chaos_queue = new_q
            self._chaos_pos = 0
        template = self._chaos_queue[self._chaos_pos]
        self._chaos_last = template
        self._chaos_pos += 1
        return template

    # ================================================================
    # 场景落点（P0 修复）：把世界级远景拉到具体地点
    # ================================================================
    def _scene_spot(self, ctx: NarrativeContext) -> str:
        """按当前世界从 scene_locations 词库洗牌发牌取一个具体落点。

        P0 修复核心：此前 SCENE 算子只渲染世界级五感（「苍云山的空气…」），
        散文卡在「明信片远景」——读者知道在世界A，却不知道站在A的哪一处。
        这里给每章一个具体落点（如「藏剑洞穴入口」），让镜头落地。
        """
        try:
            data = self._wb.load('scene_locations')
            pool = data.get(ctx.world_name, [])
            if pool:
                return self._deal(f'sceneloc::{ctx.world_name}', pool)
        except Exception as e:
            _logger.debug('_scene_spot(%s) 取落点失败: %s', ctx.world_name, e)
        return ''

    def _dominant_character(self, ctx: NarrativeContext):
        """返回当前章主导（在场）角色快照，用于落点/声纹判定。"""
        present = [n for n in ctx.characters_present if n != '墟核']
        if '林朔' in present:
            return ctx.characters_present.get('林朔')
        return ctx.characters_present.get(present[0]) if present else None

    def _resolve_scene_spot(self, ctx: NarrativeContext) -> str:
        """确定本章镜头落点：本章 scene_spot 优先；若主导角色有比世界名更具体的
        location（如「武侠世界·苍云山」→「苍云山」），用它落地。"""
        spot = getattr(ctx, 'scene_spot', '') or ''
        if not spot:
            spot = self._scene_spot(ctx)
        dom = self._dominant_character(ctx)
        if dom and dom.location:
            clean = re.sub(r'^.*?世界[·]?', '', dom.location).strip('· ').strip()
            if (clean and '（' not in clean and '(' not in clean
                    and clean != self._prose_world(ctx.world_name)
                    and clean != ctx.world_name):
                spot = clean
        return spot

    def _locale(self, char: CharacterSnapshot, ctx: NarrativeContext, world: str) -> str:
        """返回动作模板用的具体地点：角色 location（清洗后）> 本章 scene_spot > 世界散文名。

        此前的动作模板一律用 `self._locale(c, ctx, w)`（世界名），导致「林朔踏进武侠·苍云之殇」
        这类把设定标签当地名的句子（已修），且永远停在世界级。这里优先用角色的具体落点，
        让「林朔踏进苍云山。」这类落地镜头替代远景。
        """
        loc = getattr(char, 'location', '') or ''
        if loc:
            clean = re.sub(r'^.*?世界[·]?', '', loc).strip('· ').strip()
            if clean and '（' not in clean and '(' not in clean \
                    and clean != self._prose_world(world) and clean != world:
                return clean
        spot = getattr(ctx, 'scene_spot', '') or ''
        if spot:
            return spot
        return self._prose_world(world)

    # ================================================================
    # 角色动作渲染
    # ================================================================
    # 动作模板：以 lambda 形式保存（延迟求值，便于各世界五感注入）。
    # 关键：所有模板都从 _body_part_reaction / _sense_simple 取随机体感/五感碎片，
    # 因此同一模板每次渲染出的「身体部位+感官」组合都不同 —— 彻底避免类似旧版
    # `decide`「只有一个字——…堵死了」整句跨章逐字重复 40 次的缺陷。
    # 每个 action_type 一个 4 条池，按类型分队列洗牌发牌，章内不重复、跨章不塌缩。
    _ACTION_TEMPLATES = {
        'arrive': [
            lambda self, c, w, m, ctx: f'{c.name}站在{self._locale(c, ctx, w)}的边缘，{self._body_part_reaction(m, "stand")}。',
            lambda self, c, w, m, ctx: f'{c.name}深吸了一口气——{self._locale(c, ctx, w)}的{self._sense_simple("olfactory", w)}。',
            lambda self, c, w, m, ctx: f'{c.name}踏进{self._locale(c, ctx, w)}。{self._body_part_reaction(m, "observe")}——第一步轻得像怕惊动什么。',
            lambda self, c, w, m, ctx: f'{c.name}在{self._locale(c, ctx, w)}边站住，{self._body_part_reaction(m, "observe")}。{self._sense_simple("visual", w)}先到了，他才到。',
        ],
        'observe': [
            lambda self, c, w, m, ctx: f'{c.name}的目光扫过{self._locale(c, ctx, w)}——{self._sense_simple("visual", w)}。',
            lambda self, c, w, m, ctx: f'{c.name}注视着眼前的景象。{self._body_part_reaction(m, "observe")}。',
            lambda self, c, w, m, ctx: f'{c.name}盯着{self._locale(c, ctx, w)}。{self._body_part_reaction(m, "observe")}——没敢先动。{self._sense_simple("auditory", w)}先钻进耳朵。',
            lambda self, c, w, m, ctx: f'{c.name}眯起眼。{self._body_part_reaction(m, "observe")}——{self._sense_simple("visual", w)}在视线里慢慢有了边界。',
        ],
        'react': [
            lambda self, c, w, m, ctx: f'{c.name}的{self._body_part_reaction(m, "surprise")}——他没想到会是这样。',
            lambda self, c, w, m, ctx: f'{c.name}的{self._body_part_reaction(m, "surprise")}先于脑子反应。{self._sense_simple("auditory", w)}还在，可他已经听不进去了。',
            lambda self, c, w, m, ctx: f'{c.name}下意识退了半步。{self._body_part_reaction(m, "surprise")}——身体比想法快。',
            lambda self, c, w, m, ctx: f'{c.name}的{self._body_part_reaction(m, "surprise")}。{self._sense_simple("auditory", w)}被拉得很长，盖过了他自己的心跳。',
        ],
        'decide': [
            lambda self, c, w, m, ctx: f'{c.name}做了决定。{self._body_part_reaction(m, "resolve")}。',
            lambda self, c, w, m, ctx: f'「好。」{c.name}说。{self._body_part_reaction(m, "resolve")}——这一个字把他之后的路都钉死了。',
            lambda self, c, w, m, ctx: f'{c.name}把犹豫咽了回去。{self._body_part_reaction(m, "resolve")}——该走的路不会自己变短。',
            lambda self, c, w, m, ctx: f'「就这么办。」{c.name}听见自己说。{self._body_part_reaction(m, "resolve")}。',
        ],
        'collapse': [
            lambda self, c, w, m, ctx: f'{c.name}跪了下来。{self._body_part_reaction(m, "exhausted")}——不是被打倒的。',
            lambda self, c, w, m, ctx: f'{c.name}靠在一根断柱上，{self._body_part_reaction(m, "exhausted")}。',
            lambda self, c, w, m, ctx: f'{c.name}的{self._body_part_reaction(m, "exhausted")}。力气是慢慢抽走的，不是一下。',
            lambda self, c, w, m, ctx: f'{c.name}蹲下来，{self._body_part_reaction(m, "exhausted")}——世界在头顶转了一圈才停。',
        ],
        'stand_up': [
            lambda self, c, w, m, ctx: f'{c.name}站了起来。他的{self._body_part_reaction(m, "rise")}——不是在逞强，是真的还能扛。',
            lambda self, c, w, m, ctx: f'{c.name}深吸一口气，站直了身体。{self._body_part_reaction(m, "steady")}。',
            lambda self, c, w, m, ctx: f'{c.name}撑着地面站起来。{self._body_part_reaction(m, "rise")}——腿有点抖，但站住了。',
            lambda self, c, w, m, ctx: f'{c.name}直起身子。{self._body_part_reaction(m, "rise")}把刚才那口气换了。',
        ],
    }

    def render_character_action(self, char: CharacterSnapshot, action_type: str,
                                 ctx: NarrativeContext) -> str:
        """根据角色状态渲染动作描写（洗牌发牌，章内不重复）。

        action_type: 'arrive'|'observe'|'react'|'decide'|'collapse'|'stand_up'
        模板以 lambda 形式保存（延迟求值，便于各世界五感注入），按 action_type
        分队列洗牌发牌——同一动作类型在本章内不会连续/重复出现，从根上消除
        「配额注入大量 ACTION 后逐字重复」的风险。
        """
        world = ctx.world_name
        mood = char.mood_modifier()
        pool = self._ACTION_TEMPLATES.get(action_type, self._ACTION_TEMPLATES['observe'])
        tpl = self._deal(f'action::{action_type}', pool)
        text = tpl(self, char, world, mood, ctx)

        # 性格标签（死字段接通）：角色有 personality_tag 时追加一句性格化收尾
        tag = getattr(char, 'personality_tag', '') or ''
        if tag:
            try:
                persona_pool = self._wb.load('personality_voice').get(tag)
                if persona_pool:
                    text = f'{text}{self._deal(f"persona::{tag}", persona_pool)}'
            except Exception as e:
                _logger.debug('render_character_action 性格尾句失败: %s', e)
        return text

    # ================================================================
    # 情绪渲染（身体感知，不直接命名情绪）
    # ================================================================
    def render_emotion_beat(self, ctx: NarrativeContext, intensity: int = 3) -> str:
        """渲染一个情绪节拍——用身体感知而非直接说'他很害怕'。

        intensity: 1(微澜)~5(海啸)
        """
        emotion = ctx.dominant_emotion()

        # 每个情绪池保持 20 条「用身体反应而非直接命名情绪」的文本。
        # 注意：禁止写入调试/作者旁白式占位句（如「把同一行数据看了三遍」），
        # 这类句子会破坏叙事沉浸感，且极易被逐字重复。
        # 池越大，单句两次出现的间隔越长——这是消除全局逐字重复的根本手段。
        body_signals = {
            '恐惧': [
                '他的手指在墟核面板上停了半秒。不是因为犹豫——是因为指节在发凉。',
                '后颈像被人放了冰块。不是因为归墟的温度——是那种你明知道身后有东西，但不敢回头看的感觉。',
                '他听到了自己的心跳。不是很快——是很响。每一下都像有人在敲他的胸腔。',
                '喉咙发紧。他想喊，声音却卡在嗓子眼，变成一声自己都没听清的气音。',
                '视线开始聚焦失败——越是想看清黑暗里的东西，眼前的轮廓就越模糊。',
                '掌心沁出了汗。不是热的，是凉的，凉得他几乎握不住墟核的边缘。',
                '呼吸变浅了。不是他控制的，是身体在替他决定：少吸一点，别惊动什么。',
                '他下意识屏住呼吸，直到肺里那点空气快用完，才猛地意识到自己一直在怕。',
                '肩膀不自觉地缩了起来，像小时候听见雷声那样——明明知道没用，还是想把自己缩小。',
                '他的脚钉在原地。不是不敢跑，是怕一动，黑暗里那个东西就知道自己在哪里。',
                '他的呼吸停了一拍——不是忘了喘气，是身体先替他做出了「别出声」的决定。',
                '指尖无意识地抠进了掌心，指甲陷进肉里，他才发现自己一直在发抖。',
                '后脑勺的汗顺着脊椎往下淌，凉得他缩了下脖子。',
                '他忽然听不见周围的声音了——不是安静，是恐惧把别的感官都盖住了。',
                '膝盖像被抽了筋，差点没撑住身体的重量。',
                '嘴唇发干，舌尖一遍遍舔过同一处，却舔不出一点湿润。',
                '他下意识地退了半步——脚后跟已经顶到了墙，才意识到自己想逃。',
                '胸口那块地方揪紧了，像有人攥着他的心脏轻轻拧了一下。',
                '眼睛睁得太大，眼眶开始发酸，可他不敢眨——怕一闭眼，那个东西就动了。',
                '冷汗从额角渗出来，滑到太阳穴，像一条冰凉的虫子往下爬。',
            ],
            '愤怒': [
                '他的牙关咬紧到太阳穴开始跳。不是因为想打架——是不咬紧的话，他会说出一些收不回来的话。',
                '拳头握得太紧了——指甲在掌心里留下了四个月牙形的印子。他不觉得疼。',
                '呼吸从鼻腔里出来，带着一股压不住的灼热。像刚跑完步，可腿没动。',
                '视野边缘泛红。不是血，是怒气把注意力全逼到正中、其余都糊掉的感觉。',
                '他把手里的东西放下了——很慢，很轻。不是冷静，是怕一用力就把整张桌子掀了。',
                '后槽牙磨了一下。很轻，但他自己听见了。那声音让他想起被冤枉却说不出口的每一次。',
                '他的声音压低了，反而更危险。像绷到极致的弦，再拨一下就会断。',
                '胸口那团火往上顶，烧到喉咙口。他咽了一口，把那句骂人的话硬生生咽了回去。',
                '他的眼神钉在对方脸上，一寸都没移开。不是盯着看，是在把每一笔亏欠都记下来。',
                '指节因为用力而发白，骨节处的皮肤绷得发亮。他没发现自己已经掐进了自己的肉里。',
                '他的指尖在桌沿上敲了一下，又一下——节奏越来越快，像在数着忍耐的极限。',
                '脸色沉了下来，下颌线绷得死紧，周围的气压都低了半截。',
                '他忽然笑了——不是高兴，是那种「行，你够狠」的冷笑。',
                '一只手攥住了椅背，指节泛白，木头的棱角硌进掌心他也没松。',
                '喉咙里压着一句话，翻了三遍，最后变成一声极轻的、从牙缝里挤出来的哼。',
                '眼神暗了下去，不是熄灭，是火被压到最底、等着烧回来的那种暗。',
                '他把杯子重重顿在桌上，水晃出来溅到手背，他浑然不觉。',
                '太阳穴一跳一跳地疼，那是他咬牙咬出来的。',
                '胸口堵着一团东西，上不去下不来，憋得他眼眶都热了。',
                '他往前迈了半步，又硬生生停住——不是怕，是怕自己一出手就收不住。',
            ],
            '绝望': [
                '他看着墟核的蓝光暗下去。暗到需要眯起眼睛才能确认它还在亮。那种感觉不是恐慌——是溺水。水面上什么都没有，但他正在往下沉。',
                '墟核的面板上显示着源能储备：个位数百分比。林朔看了那个数字很久。数字没有变，他也没有动。',
                '他靠着断柱坐了下来。不是累，是突然觉得，站起来这件事本身已经没有了意义。',
                '喉咙里那句话翻了三遍，最后还是咽了回去。因为说出口，也不会改变任何东西。',
                '他的手垂在身侧，指尖碰到了冰冷的石面。那凉意顺着胳膊爬上来，和他心里的空刚好接上。',
                '他闭上眼。不是不想看，是看了那么久，看到的每一条路都通向同一个结局。',
                '胸口像被掏空了一块。不是疼，是那种风可以直接灌过去的空，吹得人发冷。',
                '他没有哭。眼泪这种东西，在连希望都没有的时候，反而流不出来。',
                '时间变得很奇怪。一秒和一小时没什么区别，都只是「还没有结束」的另一种写法。',
                '他想起了家里的灯——那种人一进门就自动亮起来的暖光。然后他告诉自己，那盏灯可能永远不会再为他亮了。',
                '他盯着自己的手——这双手刚才还什么都能做，现在连握紧都觉得没意义。',
                '归墟的蓝光还在闪，可他忽然觉得那光跟他没关系了。',
                '他试着去想「以后」，脑子里却只有一片空白，连「以后」这个词都立不住。',
                '嘴里发苦，那苦味从舌头根一直漫到嗓子，咽不下去也吐不出来。',
                '他靠在墙上，慢慢滑坐下去，像被抽掉了所有支撑的线。',
                '眼睛看着前方，却什么都没聚焦——视线是空的。',
                '他想起以前觉得过不去的坎，现在回头看，那些都不算什么。可眼前这个，是真的过不去。',
                '手指无意识地蜷着，攥紧又松开，松开又攥紧，像个停不下来的机械动作。',
                '风（如果归墟有风的话）吹过，他没躲——反正躲不躲都一样。',
                '他忽然很想睡觉。不是累，是睡着了就不用想了。',
            ],
            '坚定': [
                '他没有说话。但他的下巴微微抬了一下——一个几乎看不见的角度变化。那是他从游戏策划时期养成的习惯：当所有方案都失效的时候，不要讨论，直接做。',
                '房间里的所有人都看着他。他回看了每个人——一个一个看过去。然后他说了一个字。那个字很轻，但没有人没听到。',
                '他把手按在墟核上。不是试探，是确认。像在跟一个他不完全信任、但此刻只能依靠的东西，签了字。',
                '他深吸一口气，把脑子里所有「万一失败」的念头，一个一个按了回去。',
                '他的脚步稳了。不是不累，是累了也知道往哪走——这比不累更管用。',
                '他看了眼源能读数，又看了眼手里的东西，然后把它们放进了该放的位置。没有犹豫。',
                '他笑了。不是轻松，是那种「就算知道会很难，也认了」的笑。比哭有劲。',
                '他把刚才的慌乱从脸上抹掉了，像抹掉溅到屏幕上的水。重新露出来的，是熟悉的冷静。',
                '他点了点头——先是给自己的，然后才是给别人的。这一下，比任何保证都实。',
                '他没有再问「为什么是我」。他问的是「现在该做什么」。',
                '他把手里的东西攥紧了，指节因为用力而发白，但这次不是因为怕。',
                '他抬头看向那片黑暗——之前怕的东西，现在成了要跨过去的目标。',
                '没有慷慨激昂，他只是把下一步该做的事，在脑子里排成了一列。',
                '他呼出一口气，那口气不是叹气，是把犹豫吹走了。',
                '他看了眼身边的人，点了下头——不用说话，该上的都上。',
                '他往前走，脚步比刚才稳了，像是刚刚做了某个只有自己知道的决定。',
                '他把手按在胸前——不是宣誓，是确认自己的心跳还在，人还在。',
                '他忽然不那么怕了。不是因为危险没了，是因为他知道自己要干什么了。',
                '他把刚才的犹豫从脑子里拎出来，像丢掉一张写废的草稿，扔了。',
                '他抬起眼，目光落在该落的地方——不再游移。',
            ],
            '困惑': [
                '他盯着眼前的东西，试图找出一个能解释它的逻辑。三十秒后他放弃了——因为根本没有。',
                '他的眉心拧了起来。不是生气，是那种「已知条件都对、结论却怎么算都不对」的别扭。',
                '他读了三遍那段文字。每一遍都更确定自己没看错，也更确定自己没看懂。',
                '他抬起头，又低下头，再看一遍。好像只要重复这个动作够多次，意思就会自己浮出来。',
                '他伸手碰了碰那个东西，又缩回来。不是怕，是不知道碰了之后，该用什么常识去接住结果。',
                '他的思路在某个节点断了。不是想不下去，是前面有条他以为是路的地方，其实是悬崖。',
                '他张了张嘴，又闭上。想问的问题太多，反而不知道该从哪一个开始。',
                '他下意识去摸笔记本——然后才想起来，这里没有纸，也没有能记的东西。',
                '他的眼神在几个选项之间来回跳，像鼠标在全是链接的页面上迷了路。',
                '他忽然不确定自己刚才想通的那部分，到底是不是真想通了。这种不确定，比完全不懂还折磨人。',
                '他盯着那行数据，越看越觉得哪里不对，又说不上来哪里不对。',
                '脑子像被雾罩住了，明明每个字都认识，连起来就不是他以为的意思。',
                '他想找个逻辑支点，却发现自己站的那块地本身就在晃。',
                '他张了张嘴，想问，又觉得问出来的问题自己都答不上来。',
                '线索在手心里攥了一把，摊开却是乱的，理不出头绪。',
                '他忽然不确定刚才记得的那个细节，到底是真记得，还是自己脑补的。',
                '面前的东西不复杂，可它出现在这里这件事，本身就解释不通。',
                '他低头看了看墟核，又抬头看了看四周，两边对不上号。',
                '他想顺着一条线想下去，线却在中途打了个死结。',
                '他愣了几秒，不是没反应过来，是反应过来之后不知道该怎么反应。',
            ],
            '希望': [
                '他的嘴角动了一下。不是笑——是一个他自己都没注意到的角度变化。那条曲线从向下变成了接近水平。',
                '墟核的蓝光多闪了一下。很微弱，但他看到了。',
                '面板上多了一条绿色数据。不是什么大事，但在这片死寂里，绿色本身就是一种声音。',
                '远处有光透进来——不是归墟的光，是另一个世界的光。隔着重重废墟，他差点以为是错觉。',
                '他听见了自己的心跳。这一次不是因为怕，是因为「也许还来得及」这四个字，第一次站住了。',
                '他握紧了手里的东西。不是因为有了把握，是因为终于有了一件能握住的东西。',
                '他想起一句很久以前别人对他说的废话，此刻却像灯一样亮了起来。',
                '源能读数往上跳了零点几个百分点。微不足道，但方向是对的。',
                '他第一次觉得，脚下的废墟不全是废墟。有些石头下面，可能压着还没碎的东西。',
                '他呼出一口气，很长。不是放松，是终于敢把那口气，当作「还能继续」的证据。',
                '他盯着那条跳动的曲线，第一次觉得「上升」这两个字有了重量。',
                '远处那点光还在，没有灭——这就够了，至少现在够了。',
                '他把手里的东西翻过来覆过去地看，像在确认它不是自己看错了。',
                '胸口那块空了的地方，好像被什么很小、但真实的东西填了一角。',
                '他忽然想做点什么了——不是被逼的，是自己想动。',
                '嘴角那点弧度稳住了，没掉下去，也没夸张，就是挂着。',
                '他深吸一口气，这次吸进去的不是沉，是某种还没成形的可能。',
                '他看向身边人，第一次觉得「一起」这两个字不是负担。',
                '那扇一直关着的门，好像从里面透出了一点缝里的光。',
                '他把手按在还在跳的心脏上——活着，就还有得挣。',
            ],
        }

        pool = body_signals.get(emotion, body_signals['困惑'])

        # 整实例级去重：排除本实例已用过的文本；池内全部用尽才重置，
        # 保证同一句至少间隔「池大小」次渲染才可能出现，从根本上消除逐字重复。
        available = [b for b in pool if b not in self._used_emotions]
        if not available:
            self._used_emotions.clear()  # 池已耗尽，重置后再循环使用
            available = list(pool)

        k = min(intensity, len(available))
        parts = self._seed_rng.sample(available, k)
        self._used_emotions.update(parts)

        return '\n\n'.join(parts)

    # ================================================================
    # 章末钩子渲染（研究驱动：提升追读率的核心手段）
    # ================================================================
    def render_hook(self, ctx: NarrativeContext, hook_type: str = None) -> str:
        """渲染章末钩子——用「认知缺口」勾住读者，是网文追读率的命门。

        钩子三类型（来自网文写作研究）：
          - suspense     纵向钩/悬念钩：关键信息说到一半被打断、细思极恐的新细节、时间压力倒计时
          - payoff_tease 横向钩/爽点钩：当章爽点闭环完成后，立刻抛出一个更大的新危机
          - relationship 人物钩/关系钩：用情绪张力代替外部事件（适合羁绊/感情线）

        类型按上下文自动选择：
          - 高张力(>=7)或危机类节拍(bad_guys/all_lost/dark_night) → suspense
          - 中段/终局前节拍(midpoint/break_2)                → payoff_tease
          - 日常/羁绊/支线节拍(fun_games/b_story/break_1)     → relationship
          - 其他                                              → 按权重随机(悬念0.4/爽点0.3/关系0.3)

        返回 '' 表示无可用钩子（如词库缺失），调用方据此跳过。
        """
        try:
            data = self._wb.load('hook_templates')
        except Exception as e:
            _logger.debug('render_hook 钩子词库加载失败: %s', e)
            return ''

        pools = {
            'suspense': data.get('suspense', []),
            'payoff_tease': data.get('payoff_tease', []),
            'relationship': data.get('relationship', []),
        }

        if hook_type is None:
            beat = ctx.beat
            tension = ctx.tension_level
            if tension >= 7 or beat in ('bad_guys', 'all_lost', 'dark_night'):
                hook_type = 'suspense'
            elif beat in ('midpoint', 'break_2'):
                hook_type = 'payoff_tease'
            elif beat in ('fun_games', 'b_story', 'break_1'):
                hook_type = 'relationship'
            else:
                hook_type = self._seed_rng.choices(
                    ['suspense', 'payoff_tease', 'relationship'],
                    weights=[0.4, 0.3, 0.3])[0]

        pool = pools.get(hook_type, pools['suspense'])
        if not pool:
            return ''

        # 整实例级去重：池内全部用尽才重置，保证同一钩子至少间隔「池大小」章
        available = [h for h in pool if h not in self._used_hooks]
        if not available:
            self._used_hooks.clear()
            available = list(pool)
        choice = self._seed_rng.choice(available)
        self._used_hooks.add(choice)
        return choice

    # ================================================================
    # 玩家沙雕行为渲染
    # ================================================================
    def render_player_chaos(self, ctx: NarrativeContext, count: int = 3) -> list:
        """渲染玩家沙雕行为段落。"""

        # 生成随机玩家名
        data = self._wb.load('player_chaos')
        player_names = data['player_names']
        chaos_templates = data['chaos_templates']

        results = []
        for _ in range(count):
            # 洗牌发牌（bag + 跨包防涝），与 _deal 同源思路，独立 RNG 流
            template = self._deal_chaos(chaos_templates)
            name1 = self._seed_rng.choice(player_names)
            name2 = self._seed_rng.choice([n for n in player_names if n != name1])
            text = template.format(
                name=name1, name2=name2,
                location=self._seed_rng.choice(data['location']),
                thing=self._seed_rng.choice(data['thing']),
                action=self._seed_rng.choice(data['action']),
                reason=self._seed_rng.choice(data['reason']),
                announcement=self._seed_rng.choice(data['announcement']),
                consequence=self._seed_rng.choice(data['consequence']),
                debate_topic=self._seed_rng.choice(data['debate_topic']),
                count=self._seed_rng.randint(20, 200),
                discovery=self._seed_rng.choice(data['discovery']),
                belongings=self._seed_rng.choice(data['belongings']),
                currency=self._seed_rng.choice(data['currency']),
            )
            results.append(text)
        return results

    # ================================================================
    # 千层饼揭示渲染
    # ================================================================
    def render_truth_reveal(self, ctx: NarrativeContext, layer: int) -> list:
        """渲染千层饼信息揭示段落。

        注意：truth_reveals[layer] 是「该层级全部揭示句」的数组，单次 REVEAL
        节拍只应抽取其中 1 条，而非返回整个数组（否则一次揭示会输出上千条、
        拼成数万字的巨型段落 —— 缺陷 #4 根因 C）。
        """
        reveals = self._wb.load('truth_reveals')
        pool = reveals.get(str(layer), reveals.get('2'))
        if not pool:
            return []
        chosen = self._seed_rng.choice(pool)
        return [chosen]

    # ================================================================
    # 内置辅助：五感词库渲染
    # ================================================================
    def _sense(self, sense_type: str, world: str) -> str:
        """从世界五感词库中取一条渲染。

        审计第5条：此前用 `_seed_rng.choice`（有放回抽样）。五感池每世界每感官
        只有 3~5 条，配上 `_ACTION_TEMPLATES` 里的固定模板（如
        「{name}深吸了一口气——{world}的{olfactory}。」），整句在全卷内塌缩到 x9。
        改为与 VoiceEngine 其余部分一致的洗牌发牌：按 `sense::世界::感官` 分队列，
        池内不放回，发完再洗，使小池子也能均匀铺开。
        """
        try:
            data = self._wb.load_world_senses()
            world_data = data['worlds'].get(world, {})
            pool = world_data.get(sense_type, [])
            if pool:
                return self._deal(f'sense::{world}::{sense_type}', pool)
        except Exception as e:
            _logger.debug('_sense(%s, %s) 词库加载失败: %s', sense_type, world, e)
            pass

        # Fallback for commonly used senses
        fallbacks = self._wb.load_voice_helpers()['sense_fallbacks']
        return fallbacks.get(sense_type, '——')

    def _sense_simple(self, sense_type: str, world: str) -> str:
        """简化版的五感词库取用。"""
        return self._sense(sense_type, world)

    @staticmethod
    def _prose_world(world: str) -> str:
        """把世界的**词库键**翻译成可入文的地名。

        `_ACTION_TEMPLATES` 里的 `w` 同时承担两个角色：词库查找键（传给
        `_sense_simple`）和正文中的地名。但键本身是设定标签——「武侠·苍云之殇」
        带类型前缀，「东方修仙」「剑与魔法」是流派名不是地点——直接入文会写出
        「林朔踏进武侠·苍云之殇」。故正文位置一律经此翻译，查找位置仍用原键。
        """
        return WORLD_PROSE_NAMES.get(world, world)

    def _body_reaction(self, reaction_type: str) -> str:
        """身体反应短语。

        注意：此前本方法加载词库后遗漏 return，隐式返回 None，导致
        `_render_guixu_opening` 中的字符串拼接抛 TypeError——归墟世界的 SCENE
        算子 100% 崩溃，这正是编排层长期不敢给归墟拍点派发 SCENE 的技术原因。
        """
        reactions = self._wb.load_voice_helpers()['body_reaction']
        return reactions.get(reaction_type, reactions.get('confusion', '呼吸乱了一拍'))

    def _body_part_reaction(self, mood: str, action: str) -> str:
        """根据情绪和动作生成身体部位反应。

        审计第5条修复两处缺陷：

        1. **一半情绪掉进 fallback**。`sensations` 原本只覆盖 8 个情绪键，而
           `NarrativeContext.mood_modifier()` 的值域有 16 个——uncertain（困惑）、
           resolute（坚定）、focused（投入）、aggressive（愤怒）等最高频的情绪
           全部命中 `sensations.get(mood, '微微动了一下')` 的默认值，导致整章
           体感描写塌缩成「太阳穴微微动了一下 / 后颈微微动了一下 / …」。
           词库现已补齐 16 个情绪，每情绪 5 条。
        2. **`action` 形参从未被使用**，白白浪费了一个区分维度。现按动作类型
           取对应的身体部位池（observe→眼角/眉心，surprise→后颈/脊椎，
           resolve→指节/下颌，stand→肩膀/膝盖），让体感与动作语义对齐。

        组合数从「7 部位 × 1 感受 = 7 种/情绪」提升到「6 × 5 = 30 种/情绪」，
        且两侧都走洗牌发牌，池内不放回。
        """
        helpers = self._wb.load_voice_helpers()

        parts = helpers['body_parts']
        part_pool = parts.get(action) or parts.get('default') or ['太阳穴']
        part = self._deal(f'bodypart::{action}', part_pool)

        pool = helpers['sensations'].get(mood) or helpers['sensations'].get('neutral')
        if isinstance(pool, str):      # 兼容旧版「每情绪一条字符串」的词库
            pool = [pool]
        if not pool:
            return f'{part}微微动了一下'
        sensation = self._deal(f'sensation::{mood}', pool)
        return f'{part}{sensation}'

    def _emotion_to_face(self, emotion: str) -> str:
        """将情绪映射为面部表情描写。"""
        faces = {
            '恐惧': '瞳孔微缩——不是愤怒，是确认了最坏的猜想',
            '愤怒': '咬肌绷紧了——他在用牙齿控制自己',
            '绝望': '没有表情。不是平静——是所有的表情都用完了',
            '坚定': '嘴角没有上扬，但眼中有光——很微弱，但确定',
            '困惑': '眉心间的竖纹——他每次遇到解不开的逻辑bug都会这样',
            '希望': '嘴角极细微的弧度——他自己可能都没注意到',
            '警觉': '眼睛眯了一下——像猫看到不认识的物体时的表情',
        }
        return faces.get(emotion, '表情没有变化')

    def _emotion_to_body(self, emotion: str) -> str:
        """将情绪映射为全身反应描写。"""
        bodies = {
            '绝望': '身体里的力气突然被抽空了——不是生理上的，是那种「就算有力气也不知道该往哪里使」的空',
            '恐惧': '胃在收缩——不是因为饿，是因为身体知道危险比你想象的更近',
            '疲惫': '眼皮在往下坠——不是困，是看了太多不想看的东西',
            '愤怒': '手在发抖——不是因为害怕。是因为他需要握拳才能不让手抖',
            '警觉': '肌肉绷紧了——不是紧张，是随时准备动的那种紧',
            '投入': '整个人都沉了进去，外界的声音退得很远',
            '认可': '嘴角松了一点——不是笑，是终于有人接住了他的判断',
            '困惑': '脑子转了半圈没找到落点，像一脚踩进薄冰',
            '希望': '胸口那块空了的地方，被一点点填上',
            '坚定': '脊背挺直了——不是给谁看，是自己先信了',
            '恐慌': '呼吸抢在了思考前面，乱了节奏',
            '悲伤': '肩膀塌下去一点，又强迫自己撑住',
            '中性': '神色没什么变化，只是看着',
            '濒死': '体温在往外泄，指尖先一步变凉',
        }
        return bodies.get(emotion, '身体绷了一瞬，又慢慢松开')

    # ================================================================
    # 获取词库随机条目（上下文感知占位）
    # ================================================================
    def get_word(self, bank: str, key: str, mood_filter: str = None) -> str:
        """从指定词库获取一条，可选情绪过滤（未来扩展）。"""
        try:
            return self._wb.pick(bank, key)
        except Exception as e:
            _logger.debug('get_word(%s, %s) 失败: %s', bank, key, e)
            return '——'
