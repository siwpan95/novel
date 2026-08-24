# -*- coding: utf-8 -*-
import json as _json

from .word_bank import resolve_bank_path


def _load_enrichments():
    """延迟加载章节增强词库——首次调用时才读文件，避免 import-time I/O。"""
    path = resolve_bank_path('chapter_enrichments')
    with open(path, encoding='utf-8') as _f:
        return _json.load(_f)

_ENRICHMENTS = None
"""IntegratedChapterGenerator —— 双引擎融合的章节生成器。

这是真正的 1+1>2 实现：
  - 因果引擎提供"编排层"：什么事件在什么顺序发生
  - ASP引擎提供"渲染层"：用词库将事件渲染为具体文字
  - NarrativeContext 是两者的共享总线

与旧 causal_chapter.py 的本质区别：
  旧：每个节拍 = 硬编码的 L.append("...")  → 每次输出完全一样
  新：每个节拍 = BeatOrchestrator → VoiceEngine →  每次输出会变化，但因果一致

用法：
  gen = IntegratedChapterGenerator(wb, plot_state)
  chapter = gen.generate_chapter(chapter_num, outline_entry)
"""

import logging
import random
from .word_bank import WordBank
from .plot_state import PlotState
from .narrative_context import NarrativeContext
from .voice_engine import VoiceEngine
from .beat_orchestrator import BeatOrchestrator, VoiceOperation, OpType
from .causal_dialogue import CausalDialogueEngine
from .rubric_player import RubricEngine, PlayerArchetypeEngine, FamousSceneEngine
from .text_quality import TextQualityPipeline
from .rashomon import RashomonEngine, InfoMatrix
from .expansion import ExpansionEngine, WorldSenseInjector
from .rhythm_engine import RhythmEngine
from .generators.character import CharacterGenerator
from .generators.battle import BattleGenerator, SceneGenerator

_logger = logging.getLogger(__name__)


class IntegratedChapterGenerator:
    """双引擎融合的章节生成器。"""

    def __init__(self, wb: WordBank, plot_state: PlotState, seed=None,
                 rubric=None, player_engine=None, quality=None,
                 rashomon=None, info=None, expansion=None,
                 world_sense=None, rhythm=None, famous=None,
                 dealer_cfg=None):
        self._wb = wb
        self._ps = plot_state
        self._rng = wb.get_rng()

        # 核心融合组件
        self._voice = VoiceEngine(wb, plot_state, seed, dealer_cfg=dealer_cfg)
        self._orchestrator = BeatOrchestrator(self._voice)
        self._dlg = CausalDialogueEngine(wb, plot_state)

        # 质量管线（支持外部注入，避免双重实例化）
        self._rubric = rubric or RubricEngine(seed or 42)
        self._player_engine = player_engine or PlayerArchetypeEngine(seed or 42)
        self._quality = quality or TextQualityPipeline(seed or 42)
        self._rashomon = rashomon or RashomonEngine(seed or 42)
        self._info = info or InfoMatrix()
        self._expansion = expansion or ExpansionEngine(seed or 42)
        self._world_sense = world_sense or WorldSenseInjector(seed or 42)
        self._rhythm = rhythm or RhythmEngine(seed or 42)
        self._famous = famous or FamousSceneEngine(seed or 42)

        # ASP组件
        self._char_gen = CharacterGenerator(wb)
        self._battle_gen = BattleGenerator(wb)
        self._scene_gen = SceneGenerator(wb)

    # ================================================================
    # [已取消] generate_outline / generate_chapter（旧章/卷循环逻辑）
    # ----------------------------------------------------------------
    # 旧的「Save the Cat 15 拍硬编码到章号 + 按卷 dispatch + 固定 _QUOTA[beat]」
    # 是典型的「罐头式脚本驱动」结构，已于本轮重构中取消。
    # 取而代之：WordCountDirector（以字数为目标）+ EmergentOrchestrator
    # （状态驱动采样、弱化大纲、卷已移除）。相关能力仍由底层管线提供：
    #   - _execute_operation / _wire_foreshadowing / _enforce_must_include
    #   - _enrich_thin_chapter / _sync_characters / _voice（被 WordCountDirector 复用）
    # ================================================================

    # ================================================================
    # P2：伏笔闭环 / 死字段必含元素 —— 接通此前仅存于弃用 causal_chapter 的伏笔 API
    # ================================================================
    def _foreshadowing_pool(self) -> dict:
        """懒加载伏笔词库（带缓存）。"""
        if not hasattr(self, '_fs_pool'):
            try:
                self._fs_pool = self._wb.load('foreshadowing_pool')
            except Exception as e:
                _logger.debug('伏笔词库加载失败，降级为空池: %s', e)
                self._fs_pool = {'planting_beats': [], 'seeds': {}}
        return self._fs_pool

    def _wire_foreshadowing(self, ctx, operations, L, events, chapter_num):
        """把伏笔从「仅存在于弃用 causal_chapter」接到活动生成路径：

        - 回收优先：凡 planned_recovery_chapter 已到期且仍 active 的伏笔，先标记回收
          并把呼应句写进正文，闭合环路；
        - 种植在后：仅在「种植节拍」的最后一章埋一次（避免同拍多章重复埋同 id），
          将种植句写进正文，让伏笔真正可见。
        回收先于种植，确保同一章不会既埋又收同一个 id。
        """
        pool = self._foreshadowing_pool()
        planting_beats = pool.get('planting_beats', [])
        is_last_of_beat = (ctx.sub_index == ctx.total_in_beat)

        # —— 回收：到期的伏笔优先闭合 ——
        try:
            pending = self._ps.get_pending_foreshadowing(chapter_num)
        except Exception as e:
            _logger.debug('get_pending_foreshadowing 失败: %s', e)
            pending = []
        for fs in pending:
            try:
                self._ps.recover_foreshadowing(fs['id'], chapter_num)
                rec = fs.get('recovery_text') or fs.get('content', '')
                if rec:
                    L.append('')
                    L.append(rec)
                    events.append(
                        f'伏笔回收：{fs["id"]}（埋于第{fs.get("planted_chapter")}章）'
                    )
            except Exception as e:
                _logger.debug('伏笔回收 %s 失败: %s', fs.get('id'), e)

        # —— 种植：仅种植节拍的最后一章埋一次（洗牌发牌保证跨卷不重复） ——
        if ctx.beat in planting_beats and is_last_of_beat:
            seeds = pool.get('seeds', {}).get(ctx.beat, [])
            if seeds:
                try:
                    seed = self._voice._deal(f'foreshadow::{ctx.beat}', seeds)
                except Exception as e:
                    _logger.debug('foreshadow 洗牌发牌失败: %s', e)
                    seed = None
                if seed:
                    lo, hi = seed.get('recovery_offset', [3, 8])
                    planned = chapter_num + random.randint(int(lo), int(hi))
                    fid = seed['id']
                    # 极端重跑场景下，若同 id 已存在则跳过，避免污染 foreshadowing 列表
                    if not any(f['id'] == fid for f in self._ps.state.get('foreshadowing', [])):
                        self._ps.add_foreshadowing(
                            fid, seed['content'], chapter_num, planned,
                            recovery_text=seed.get('recovery_text', ''),
                        )
                        L.append('')
                        L.append(seed['content'])
                        events.append(f'伏笔埋设：{fid}（计划第{planned}章回收）')

    # 必含元素 → 自然收尾句（死字段 ctx.must_include 的落实模板）。
    # 任一 token 在本章正文缺失时，补一句不破坏语感的收尾，让节拍的「必须出现元素」真正落地。
    _MUST_INCLUDE_SENTENCES = {
        '墟核直连': '墟核的链接灯第一次亮成稳定的青色——直连建立，再没有中间层替它过滤指令。',
        '协议附录': '那份《协议附录》摊在他手边，第三条被涂抹的痕迹比正文更刺眼。',
        '叶琳的紫纹': '叶琳腕间的紫纹又深了一分，像某种契约正在她皮肤下慢慢收口。',
        '碎片能量读数': '星图边缘跳出一个读数：那枚碎片的能量曲线，和归墟核心的呼吸同频。',
        '渗透型': '他看清了——那不是普通的敌人，是带着「渗透型」标记的代理人。',
    }

    def _enforce_must_include(self, ctx, L, events):
        """保证 ctx.must_include 中的必含元素在本章正文里出现；缺失则补一句自然收尾。"""
        if not ctx.must_include:
            return
        joined = '\n'.join(L)
        for item in ctx.must_include:
            if item and item not in joined:
                sentence = self._MUST_INCLUDE_SENTENCES.get(
                    item, f'{item}——这一条他不能忽略。'
                )
                L.append('')
                L.append(sentence)
                events.append(f'must_include 落实：{item}')

    # ================================================================
    # 操作执行器（策略模式：每种 OpType 独立方法，通过注册表调度）
    # ================================================================
    def _execute_operation(self, op: VoiceOperation, ctx: NarrativeContext) -> list:
        """执行单个语音操作——通过注册表分发到各 OpType 的独立执行器。"""
        handler = self._OP_EXECUTORS.get(op.op_type)
        if handler is not None:
            return handler(self, op, ctx)
        return []

    # -- 各 OpType 执行器 -------------------------------------------------------
    def _exec_scene(self, op, ctx):
        """SCENE: 世界入场横幅（entry=True）或章内场景散文。"""
        lines = []
        if op.params.get('entry'):
            lines = self._voice.render_opening_scene(ctx)
        else:
            lines = self._voice.render_scene_beat(ctx, op.params.get('scene_type'))
            flavour = self._voice.render_world_flavour(ctx, op_type='SCENE')
            if flavour:
                lines = lines + ['', flavour]
        if lines:
            lines = [''] + lines + ['']
        return lines

    def _exec_text(self, op, ctx):
        """TEXT: 硬编码叙事文本 + 世界感官细节注入。"""
        if 'text' not in op.params:
            return []
        text = op.params['text']
        flavour = self._voice.render_text_snippet(ctx, prob=0.40)
        if flavour:
            return [text, '', flavour]
        return [text]

    def _exec_action(self, op, ctx):
        """ACTION: 角色动作渲染——配额注入默认指向林朔。"""
        char_name = op.params.get('char', '林朔')
        action = op.params.get('action', 'observe')
        char = ctx.get_character(char_name) or ctx.get_character('林朔')
        if char:
            text = self._voice.render_character_action(char, action, ctx)
            if text:
                lines = ['', text]
                flavour = self._voice.render_world_flavour(ctx, prob=0.3, op_type='ACTION')
                if flavour:
                    lines.append(flavour)
                lines.append('')
                return lines
        return []

    def _exec_battle(self, op, ctx):
        """BATTLE: 每章至多 1 场战斗——避免同章模板逐字重复。"""
        if getattr(self, '_battle_count', 0) >= 1:
            return []
        lines = self._render_battle(ctx, op)
        if lines:
            self._battle_count = self._battle_count + 1 if hasattr(self, '_battle_count') else 1
            flavour = self._voice.render_world_flavour(ctx, prob=0.5, op_type='BATTLE')
            if flavour:
                lines = lines + ['', flavour]
        return lines

    def _exec_dialogue(self, op, ctx):
        """DIALOGUE: 因果对话引擎接入。"""
        scene_type = op.params.get('scene_type', 'generic')
        participants = op.params.get('participants', ['A', 'B'])
        context = op.params.get('context', {})
        text = self._dlg.generate(scene_type, participants, context)
        if text:
            lines = ['', text]
            flavour = self._voice.render_world_flavour(ctx, prob=0.25, op_type='DIALOGUE')
            if flavour:
                lines.append(flavour)
            lines.append('')
            return lines
        return []

    def _exec_reveal(self, op, ctx):
        """REVEAL: 千层饼信息揭示。"""
        layer = op.params.get('layer', 2)
        reveal_lines = self._voice.render_truth_reveal(ctx, layer)
        if reveal_lines:
            lines = [''] + reveal_lines
            flavour = self._voice.render_world_flavour(ctx, prob=0.4, op_type='REVEAL')
            if flavour:
                lines.append(flavour)
            lines.append('')
            return lines
        return []

    def _exec_emotion(self, op, ctx):
        """EMOTION: 情绪节拍渲染。"""
        intensity = op.params.get('intensity', 3)
        text = self._voice.render_emotion_beat(ctx, intensity)
        if text:
            return [''] + text.split('\n') + ['']
        return []

    def _exec_player(self, op, ctx):
        """PLAYER: 玩家沙雕行为渲染。"""
        count = op.params.get('count', 2)
        lines = []
        for pt in self._voice.render_player_chaos(ctx, count):
            lines.append(pt)
            lines.append('')
        return lines

    def _exec_hook(self, op, ctx):
        """HOOK: 章末钩子（直接文本）。"""
        if 'text' in op.params:
            return ['', op.params['text'], '']
        return []

    def _exec_break(self, op, ctx):
        """BREAK: 空行分隔。"""
        return ['']


    # ================================================================
    # 战斗渲染（第2条修复：BATTLE 真正接入拍点表 + 因果上下文）
    # ================================================================
    # 拍位 → 战斗的叙事定位。BATTLE 不再是一段"贴上去的 ASP 演示"，
    # 而是由因果引擎的节拍/张力/在场角色共同决定的段落。
    # 每个拍位配 7 条定场语（而不是 1 条）——第 1 卷 fun_games 有 13 章，
    # 单条提示句会原样复读 13 次，正是"单章合规、全书复读"的典型。
    _BATTLE_FRAMING = {
        'fun_games': ('试招', [
            '还不是生死局——但双方都在称对方的斤两。',
            '这一场谁都没往死里打，谁也都没真的留手。',
            '与其说是打，不如说是一次报价：我值这个数，你呢。',
            '两个人心里都清楚这不是终局，所以下手都带着分寸。',
            '真正的问题不是谁赢，是谁先把底牌摸出来。',
            '打给对方看的成分，比打赢的成分更多。',
            '像两只互相绕圈的兽——牙还没露全。',
        ]),
        'midpoint': ('转折之战', [
            '这一战之后，退路就没有了。',
            '他动手之前想了很久。动手之后就再没时间想了。',
            '从这一刻起，他不再是那个被推着走的人。',
            '不是他选了这一战，是这一战选了他——但他答应了。',
            '有些门推开之后是关不上的。这一拳就是那扇门。',
            '他终于不再问"要不要"，只问"怎么打"。',
            '中场哨响。上半场那个犹豫的人被留在了原地。',
        ]),
        'bad_guys': ('围杀', [
            '对方不是来试探的。',
            '这次来的人，是奔着结果来的。',
            '包围圈在他反应过来之前就已经合上了。',
            '没有喊话，没有条件——只有一个明确的目的。',
            '他数了数对面的人。数完就后悔数了。',
            '对方的阵型说明了一切：他们准备了很久。',
            '这不是一场遭遇战。这是一场按计划执行的清除。',
        ]),
        'all_lost': ('溃败之战', [
            '他知道自己赢不了。他还是站在了那里。',
            '所有能算的都算过了，结论只有一个——但他不接受那个结论。',
            '这一战没有胜算，只有代价高低的区别。',
            '他不是为了赢才动手的。是为了让某些人能走。',
            '他已经没有牌了，于是他把自己押了上去。',
            '这一次连观众都安静了。他们看得出结局。',
            '输是注定的。怎么输，还归他自己决定。',
        ]),
        'break_2': ('反攻', [
            '这一次是他先动的手。',
            '被追了太久，他终于停下来转过了身。',
            '他不再等对方出招——他自己就是那一招。',
            '守了整整一卷的人，第一次踏进了对方的距离里。',
            '这次不是逃，也不是挡。是往前。',
            '他把之前所有咽下去的东西，一次性还了回去。',
            '轮到对面开始退了。',
        ]),
    }

    # 战斗中可作为对手的角色（按优先级）。取不到就退回随机生成的敌人。
    _BATTLE_OPPONENTS = ('代理人', '白夜', '叶琳', '唐川')

    def _battle_terrain(self, ctx: NarrativeContext) -> str:
        """按当前世界取战场地形。

        原实现是 `'废土废墟' if world=='末日废土' else '苍云山后山'`——
        赛博都市、克苏鲁深渊、星际殖民的所有战斗都发生在"苍云山后山"，
        诸天穿越的世界差异性在战斗段落里完全塌缩。
        """
        try:
            data = self._wb.load_world_senses()
            pool = data.get('battlefields', {}).get(ctx.world_name, [])
            if pool:
                return self._voice._deal(f'battlefield::{ctx.world_name}', pool)
        except Exception as e:
            _logger.debug('_battle_terrain(%s) 取地形失败: %s', ctx.world_name, e)
        return ctx.world_name

    def _battle_participants(self, ctx: NarrativeContext) -> tuple:
        """从因果上下文里挑出真正的参战双方。

        原实现 `generate(surname='墨')` vs `generate()` 造出两个与本章毫无关系
        的路人对打——这是审计所说"融合失衡"最典型的一处：ASP 在自说自话。
        现在名字取自 ctx.characters_present，兵器/招式/法宝仍由 ASP 生成，
        因果给人、ASP 给声音。
        """
        present = [n for n in ctx.characters_present if n != '墟核']
        hero_name = '林朔' if '林朔' in present else (present[0] if present else '林朔')

        foe_name = None
        for cand in self._BATTLE_OPPONENTS:
            if cand != hero_name and cand in present:
                foe_name = cand
                break
        if foe_name is None:
            others = [n for n in present if n != hero_name]
            foe_name = others[0] if others else None

        hero = self._battle_profile(hero_name)
        if foe_name:
            foe = self._battle_profile(foe_name)
        else:
            # 本章没有第二个具名角色 → 现场生成一个无名敌手，不入档案
            foe = self._char_gen.generate()
        return hero, foe

    # 具名角色的招式库容量。设成 1（即只缓存一招）会让人设稳住，
    # 但含 {skill} 的战斗模板会退化成同一句反复出现——实测跨章 x11。
    # 一个武者本来就有一套招式，8 招既符合"剑法八式"的直觉，也把
    # 「模板 × 招式」的组合空间放大到足以压住逐字重复。
    _PROFILE_SKILLS = 8
    _PROFILE_GEAR = 4

    def _battle_profile(self, name: str) -> dict:
        """具名角色的战斗档案——全书内保持一致的一套招式/兵器/法宝。

        原实现每次战斗都重新 generate()，林朔这一章使「太极紫金铃」、
        下一章换「玄冰刺」，读者层面直接崩人设。现在档案入缓存：
        兵器招式仍由 ASP 词库生成（保留巨校风味），但同一个人在全书里
        只用自己那一套，且这套里有多件，出招不至于复读。
        """
        cache = getattr(self, '_battle_profiles', None)
        if cache is None:
            cache = self._battle_profiles = {}
        if name in cache:
            return cache[name]

        prof = self._char_gen.generate(name=name)
        cg = self._char_gen

        def _uniq(first, maker, n):
            pool = [first]
            for _ in range(n * 3):
                if len(pool) >= n:
                    break
                item = maker()
                if item not in pool:
                    pool.append(item)
            return pool

        prof['skills'] = _uniq(prof['skill'], cg._gen_skill, self._PROFILE_SKILLS)
        prof['weapons'] = _uniq(prof['weapon'], cg._gen_weapon, self._PROFILE_GEAR)
        prof['treasures'] = _uniq(prof['treasure'], cg._gen_treasure, self._PROFILE_GEAR)
        cache[name] = prof
        return prof

    def _render_battle(self, ctx: NarrativeContext, op) -> list:
        """渲染一场与节拍绑定的战斗。"""
        framing = self._BATTLE_FRAMING.get(ctx.beat)
        if framing:
            label, notes = framing
            note = self._voice._deal(f'battlenote::{ctx.beat}', notes)
        else:
            label, note = '交手', ''

        # 回合数：张力等级驱动（因果引擎 → ASP 产能），intensity 作为下限
        base = 2 if op.params.get('intensity') == 'mid' else 3
        rounds = max(base, min(5, 1 + ctx.tension_level // 2))

        hero, foe = self._battle_participants(ctx)
        terrain = self._battle_terrain(ctx)

        battle_text = self._battle_gen.generate_battle(
            char_a=hero, char_b=foe, rounds=rounds, terrain=terrain
        )

        lines = ['', f'【{label}·{terrain}】']
        if note:
            lines.append(note)
            lines.append('')
        lines.append(battle_text)
        lines.append('')
        return lines

    # ================================================================
    # 辅助方法
    # ================================================================
    def _sync_characters(self, ctx: NarrativeContext):
        """从 PlotState 同步角色状态到 NarrativeContext。"""
        all_chars = self._ps.state.get('characters', {})
        for name, data in all_chars.items():
            if name == '玩家群体':
                continue
            ctx.add_character(
                name,
                emotional_state=data.get('emotional_state', '中性'),
                current_goal=data.get('current_goal', ''),
                location=data.get('location', ''),
                knows_truth=data.get('knows_truth', False),
                corruption_level=data.get('corruption_level', 0),
                # 死字段接通：角色性格标签从 PlotState 透传到 CharacterSnapshot，
                # 由 render_character_action 追加一句性格化收尾（personality_voice 词库）。
                personality_tag=data.get('personality_tag', ''),
            )

    def _get_expansions(self, beat: str, sub_idx: int) -> list:
        expansions = {
            'opening': [('林朔站在废墟中', 1)],
            'theme': [('林朔阅读协议条款', 1)],
            'inciting': [('玩家降临', 1), ('林朔打开GM面板', 1)],
            'debate': [('玩家无视GM指令', 1)],
            'break_1': [('林朔看到碎片记忆', 2)],
            'b_story': [('叶琳站在营地边缘', 1)],
            'fun_games': [('玩家们在篝火旁争论', 1)],
            'midpoint': [('归墟星图解锁', 2)],
            'bad_guys': [('代理人从裂缝中走出', 2)],
            'all_lost': [('叶琳倒下', 2), ('林朔握住剑柄', 2)],
            'dark_night': [('林朔独自坐在归墟', 1)],
            'break_2': [('白夜揭露真相', 2)],
        }
        return expansions.get(beat, [])

    # ================================================================
    # P4: 瘦章节补叙事
    # ================================================================
    def _enrich_thin_chapter(self, L: list, beat: str, ctx) -> list:
        """对少于150字的章节注入补充叙事——世界细节、玩家动态、角色内心。"""
        world = ctx.world_name
        sub = ctx.sub_index

        enrichments = _load_enrichments()

        text_options = enrichments.get(beat, [enrichments['default']])

        choice = self._rng.choice(text_options).format(world=world, sub=sub)
        insert_pos = len(L) * 2 // 3
        # find a blank line near the position
        for i in range(max(0, insert_pos - 3), min(len(L), insert_pos + 3)):
            if i < len(L) and L[i].strip() == '':
                L.insert(i + 1, choice)
                break
        else:
            L.insert(insert_pos, '')
            L.insert(insert_pos + 1, choice)

        return L

# ================================================================
# OpType → 执行器注册表（类体外构建，策略模式）
# ================================================================
IntegratedChapterGenerator._OP_EXECUTORS = {
    OpType.SCENE:    IntegratedChapterGenerator._exec_scene,
    OpType.TEXT:     IntegratedChapterGenerator._exec_text,
    OpType.ACTION:   IntegratedChapterGenerator._exec_action,
    OpType.EMOTION:  IntegratedChapterGenerator._exec_emotion,
    OpType.DIALOGUE: IntegratedChapterGenerator._exec_dialogue,
    OpType.PLAYER:   IntegratedChapterGenerator._exec_player,
    OpType.REVEAL:   IntegratedChapterGenerator._exec_reveal,
    OpType.BATTLE:   IntegratedChapterGenerator._exec_battle,
    OpType.HOOK:     IntegratedChapterGenerator._exec_hook,
    OpType.BREAK:    IntegratedChapterGenerator._exec_break,
}
