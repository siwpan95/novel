# -*- coding: utf-8 -*-
"""BeatOrchestrator —— 将因果节拍转换为 VoiceEngine 操作序列。

这是双引擎融合的"编排层"——它不生产文字，它编排"应该生成什么"。

每个 Save the Cat! 节拍的每个子索引，都被分解为一串 VoiceOperation。
VoiceEngine 按序执行这些操作，最终组装成一章。

对比旧模式：
  旧：_gen_opening() → 30行硬编码 L.append("...") → 每次输出完全一样
  新：beat_opening() → [VoiceOperation(scene), VoiceOperation(action), ...] → 每次输出不同

关键设计：
  - 操作的顺序 = 叙事逻辑（来自因果引擎）
  - 操作的内容 = 词库渲染（来自ASP引擎）
  - NarrativeContext = 两者共享的状态总线
"""

from enum import Enum

from .narrative_context import NarrativeContext
from .voice_engine import VoiceEngine
from .beat_narratives import BeatNarrativeLoader
from .beat_orchestrator_legacy import BeatOrchestratorLegacy  # v2/v3 遗留编排，通过多继承保持 getattr 兼容


class OpType(Enum):
    """语音操作类型。"""
    SCENE = 'scene'           # 场景描写（世界五感）
    ACTION = 'action'         # 角色动作
    EMOTION = 'emotion'       # 情绪节拍（身体反应）
    DIALOGUE = 'dialogue'     # 对话（因果对话引擎）
    REVEAL = 'reveal'         # 信息揭示
    PLAYER = 'player'         # 玩家行为
    BATTLE = 'battle'         # 战斗场景
    TEXT = 'text'             # 直接文本（叙事句子）
    BREAK = 'break'           # 段落分隔/空白
    HOOK = 'hook'             # 悬念钩子


class VoiceOperation:
    """一个语音操作：告诉VoiceEngine做什么。"""

    def __init__(self, op_type: OpType, **params):
        self.op_type = op_type
        self.params = params  # 传递给 VoiceEngine 的参数

    def __repr__(self):
        return f'VoiceOp({self.op_type.value}, {self.params})'


class BeatOrchestrator(BeatOrchestratorLegacy):
    """节拍编排器：将因果节拍分解为操作序列。"""

    def __init__(self, voice: VoiceEngine):
        self._voice = voice
        self._narrative = BeatNarrativeLoader()  # JSON 数据驱动的叙事文本
        self._text_idx = {}  # 按节拍追踪文本索引，确保顺序消费

    def orchestrate(self, ctx: NarrativeContext) -> list:
        """根据上下文生成操作序列（支持多卷dispatch）。"""
        beat = ctx.beat
        sub = ctx.sub_index
        total = ctx.total_in_beat
        volume = ctx.volume

        # 优先卷特定编排
        orchestrator = getattr(self, f'_beat_{beat}_v{volume}', None)
        if not orchestrator:
            orchestrator = getattr(self, f'_beat_{beat}', None)

        if orchestrator:
            ops = orchestrator(ctx, sub, total)
        else:
            ops = self._beat_generic(ctx, sub, total)

        # 第1条修复：按拍型注入 SCENE/ACTION/BATTLE 强制配额，把每章算子数 3.4 → 20+
        ops = self._inject_quota(ops, ctx)

        return ops

    # ================================================================
    # 第1条修复：按拍型强制配额 (scene, action, battle)
    # 用「编排层配额 × 渲染层融合」直接回应审计结论——双系统融合长期只有
    # "1 + 0.03"：TEXT 算子占 54%，ASP 三算子仅 6.5% 字数。配额让 ASP 的声音
    # （五感场景 + 角色动作 + 战斗）真正在每章里被调用，体现 1+1>2。
    # ================================================================
    _QUOTA = {
        'opening':     (9, 7, 0),   # 审计第5条：开篇章（sub1 零配额的重 TEXT 章）之外提配额，补厚度
        'theme':       (13, 11, 0), # 审计第5条：静场思辨拍，原 747 字偏薄 → 拉到 1400+
        'inciting':    (13, 10, 0), # 审计第5条：815 → 1400+
        'debate':      (14, 11, 0), # 审计第5条：711 → 1400+
        'break_1':     (14, 11, 0), # 审计第5条：661 → 1400+
        'b_story':     (14, 11, 0), # 审计第5条：819 → 1400+
        'fun_games':   (11, 10, 1), # 审计第5条：1119 → ~1500；试招拍本就多动作
        'midpoint':    (9, 7, 1),   # 带 BATTLE，本就 1900+，不动
        'bad_guys':    (10, 8, 1),  # 带 BATTLE，本就 1900+，不动
        'all_lost':    (11, 9, 1),  # 带 BATTLE，本就 2200+，不动
        'dark_night':  (14, 11, 0), # 灵魂暗夜仍是静场（不排战斗），原 922 偏薄，靠 SCENE/ACTION 补
        'break_2':     (8, 6, 1),   # 冲入第三幕 = 反攻，主角第一次先动手
        'epilogue':    (8, 6, 0),
        'generic':     (8, 6, 0),
    }

    def _inject_quota(self, ops: list, ctx: NarrativeContext) -> list:
        """按拍型把 SCENE/ACTION/BATTLE（+对话）强制配额均匀穿插进已有操作序列。

        - 配额按 ctx.beat 从 _QUOTA 取 (scene, action, battle)；
        - **P1 修复**：pace_hint / description_density / dialogue_ratio 三个此前零引用的
          死字段现在真正驱动配额——快节奏减场景增动作、rich 描写加场景、对话密度高且
          双角色在场时额外注入一段对话；
        - **章间节奏调制**：上一章与本章张力都≥8 时，给一拍喘息（减一场战斗、加一场景），
          实现「紧张→缓冲」的呼吸感；
        - ACTION 类型按 6 种旋转，章内不重复；opening 第1章不注入以免与硬编码开场塌缩。
        """
        scene_n, action_n, battle_n = self._QUOTA.get(ctx.beat, (3, 2, 0))
        if ctx.beat == 'opening' and ctx.sub_index == 1:
            scene_n = action_n = battle_n = 0
        if scene_n == action_n == battle_n == 0:
            return ops

        # === P1：节奏 / 描写密度 / 章间节奏 真正影响配额 ===
        if ctx.pace_hint == 'fast':
            action_n += 1
            scene_n = max(0, scene_n - 1)
        elif ctx.pace_hint == 'slow':
            scene_n += 1
            action_n = max(0, action_n - 1)

        if ctx.description_density == 'rich':
            scene_n += 1
        elif ctx.description_density == 'sparse':
            scene_n = max(0, scene_n - 1)

        # 章间节奏调制（紧张→缓冲）：连续两章高张力时，给一拍喘息
        if ctx.prev_beat_tension >= 8 and ctx.tension_level >= 8:
            battle_n = max(0, battle_n - 1)
            scene_n += 1

        # 交错排列：SCENE/ACTION 交替，BATTLE 置后
        action_cycle = ['observe', 'arrive', 'react', 'decide', 'stand_up', 'collapse']
        order = []
        sa_max = max(scene_n, action_n)
        sc = ac = 0
        for _ in range(sa_max):
            if sc < scene_n:
                order.append(('SCENE', None)); sc += 1
            if ac < action_n:
                order.append(('ACTION', action_cycle[ac % len(action_cycle)])); ac += 1
        for _ in range(battle_n):
            order.append(('BATTLE', None))

        # 对话密度驱动：对话占比够高且至少两名具名角色在场，注入一段对话
        if ctx.dialogue_ratio >= 0.45 and ctx.beat not in ('opening', 'epilogue'):
            present = [n for n in ctx.characters_present if n != '墟核']
            if len(present) >= 2:
                order.append(('DIALOGUE', None))

        n = len(order)
        result = list(ops)
        # 逆向插入以保持前面已算位置稳定：第 i 个配额落在
        # round((i+1) * len(ops) / (n+1)) 处，实现均匀散布。
        action_idx = 0  # 每个 ACTION 算子独立计数，驱动 _action_char 在角色间轮换
        for i in range(n - 1, -1, -1):
            kind, arg = order[i]
            pos = round((i + 1) * len(ops) / (n + 1))
            if kind == 'SCENE':
                result.insert(pos, VoiceOperation(OpType.SCENE))
            elif kind == 'ACTION':
                result.insert(pos, VoiceOperation(OpType.ACTION, char=self._action_char(ctx, action_idx), action=arg))
                action_idx += 1
            elif kind == 'BATTLE':
                result.insert(pos, VoiceOperation(OpType.BATTLE, intensity='mid'))
            else:  # DIALOGUE
                result.insert(pos, VoiceOperation(
                    OpType.DIALOGUE,
                    scene_type=self._dialogue_scene_for_beat(ctx.beat),
                    participants=self._dialogue_participants(ctx),
                ))
        return result

    def _dialogue_scene_for_beat(self, beat: str) -> str:
        """按节拍选择注入对话的场景类型（喂给 CausalDialogueEngine）。"""
        return {
            'b_story': 'npc_encounter', 'fun_games': 'player_interaction',
            'debate': 'gm_player', 'break_1': 'npc_encounter',
            'break_2': 'npc_encounter', 'inciting': 'gm_player',
            'midpoint': 'revelation', 'bad_guys': 'revelation',
            'all_lost': 'npc_encounter', 'dark_night': 'npc_encounter',
            'theme': 'gm_player', 'generic': 'generic',
        }.get(beat, 'generic')

    def _dialogue_participants(self, ctx: NarrativeContext) -> list:
        """从在场角色里挑两名具名角色作为对话参与者。"""
        present = [n for n in ctx.characters_present if n != '墟核']
        if len(present) >= 2:
            return present[:2]
        return ['林朔', '墟核']

    def _action_char(self, ctx: NarrativeContext, idx: int) -> str:
        """ACTION 算子的执行角色：在在场具名角色间轮换，让性格尾句（personality_tag）
        能覆盖多位角色；林朔 排在最前、作为默认主角，其余角色轮流上场。"""
        present = [n for n in ctx.characters_present if n != '墟核']
        if not present:
            return '林朔'
        return present[idx % len(present)]

    def _t(self, beat_name: str, hardcoded_fallback: str) -> str:
        """数据驱动的叙事文本加载（轮询选择，避免跨章逐字重复）。

        - 优先从 beat_narratives.json 的变体池中轮询选取，生产运行时完全数据驱动；
        - key 不存在或变体池为空时回退到硬编码文本（fallback），保证行为不变；
        - 轮询（round-robin）而非顺序索引：单次使用的节拍固定取变体[0]（即原始文本，
          输出与原硬编码逐字一致）；同一节拍跨章复用时依次轮换变体，彻底消除
          "第二次起全部塌缩为变体[0]" 的 bug，并自然缓解跨章逐字重复。
        """
        key = f'_{beat_name}' if not beat_name.startswith('_') else beat_name
        variants = self._narrative.get_all(key)
        if not variants:
            return hardcoded_fallback
        counter = self._text_idx.get(key, 0)
        idx = counter % len(variants)
        self._text_idx[key] = counter + 1
        return variants[idx]

    # ================================================================
    # OPENING: 第1-3章 —— 归墟登场
    # ================================================================
    def _tf(self, beat_name: str, hardcoded_fallback: str, **fmt) -> str:
        """数据驱动叙事模板（支持占位符的 f-string 文本），轮询选择 + .format。

        - 模板来自 beat_narratives.json（与 _t 共用加载器 / 轮询索引）；
        - fallback 为原始 f-string：JSON 缺失时仍按原逻辑求值，行为不变；
        - 模板中的 {sub}/{world}/{pct} 等占位符由调用处通过 fmt 注入。
        """
        tpl = self._t(beat_name, hardcoded_fallback)
        if not fmt:
            return tpl
        try:
            return tpl.format(**fmt)
        except (KeyError, IndexError):
            return hardcoded_fallback.format(**fmt)

    def _beat_opening(self, ctx, sub, total):
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='困惑')
        ctx.tension_level = 7

        if sub == 1:
            return [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '林朔记得的最后一件事，是在办公室里改策划案。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '然后世界碎了。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '不是比喻——是真的碎了。电脑屏幕、马克杯、窗外的写字楼，一切像被无形的手揉皱，折叠，压缩成一团刺眼的蓝光。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '当他再次能看清东西时，他站在一个不该存在的地方。头顶不是天花板，是一望无际的虚空。脚下不是地板，是一座巨大到失去比例感的古代废墟——断裂的石柱像巨人的骨骼，铺满了视野所及的范围。没有风，没有声音，只有深远的低频嗡鸣。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '一颗拳头大小的水晶悬浮在半空。蓝光缓慢闪烁，每闪一次，他的太阳穴就跳一下。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '然后水晶说话了——不是声音，是一行直接出现在脑海中的文字：')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '「锚定者协议启动。」')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '「身份确认：林朔。」')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '「欢迎来到归墟。」')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.EMOTION, intensity=3),
            ]
        elif sub == 2:
            return [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '林朔不记得自己站了多久——归墟里没有日升月落。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '他决定先搞清楚自己在哪。废墟很大，大到让他想起被扔进一个被遗弃的斗兽场。他沿着断裂的石阶往下走，穿过倒塌的拱门，脚下的石板上有模糊的雕刻。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '然后他看到了那面墙。墙上有刻痕——深浅不一，显然不是精密仪器留下的，更像是有人用尖锐的物体，一下一下地，在石头上划出来的。字迹潦草，但林朔认出来了——这是汉字。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '「第四十七次。」')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '「还是失败。」')),
                VoiceOperation(OpType.EMOTION, intensity=2),
            ]
        else:
            return [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '林朔试过了所有能想到的办法。先找出口——废墟的边界是悬崖，悬崖下面是虚空。他扔了一块碎石下去，没听到落地的声音。然后试墟核——摸不到实体。试图骂它、威胁它、求它——全部无效。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_opening', '最后他坐下来。他用手指在石板地面上画：1.地点叫归墟。2.被锚定者协议绑定。3.水晶叫墟核。4.源能耗尽会崩塌。5.我是被选中的。')),
                VoiceOperation(OpType.EMOTION, intensity=2),
            ]

    # ================================================================
    # INCITING: 第7-12章 —— 玩家降临
    # ================================================================
    def _beat_inciting(self, ctx, sub, total):
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='警觉')
        ctx.tension_level = 5 if sub <= 3 else 6

        if sub == 1:
            return [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '墟核弹出一长串数据的时候，林朔正在归墟的地面上画地图。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '「检测到地球侧登录信号。数量：12。」')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '「已连接世界：武侠·苍云之殇。」')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '「玩家正在进入世界。」')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.EMOTION, intensity=3),
                VoiceOperation(OpType.PLAYER, count=4, type='first_landing'),
            ]
        elif sub == 2:
            return [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '墟核给了林朔一份简要说明——玩家们以为自己在通过VR设备体验一款全息游戏，实则灵魂被投射至真实世界。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.EMOTION, intensity=4),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '「原住民非NPC。原住民为真实生命体。该世界任何生命死亡不可逆转。」')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '林朔看着这行字，胃里涌起一股凉意。玩家死了可以重来。但武侠世界的每一个人——死了，就是真的死了。')),
            ]
        elif sub == 3:
            return [
                VoiceOperation(OpType.ACTION, char='林朔', action='decide'),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '林朔发出了第一条GM公告。他删改了五遍。最终发出去的是：')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '「系统公告：欢迎来到《万界》封测。当前版本开放世界：1。请自行探索，注意安全。」')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.PLAYER, count=2, type='gm_response'),
                VoiceOperation(OpType.DIALOGUE, scene_type='gm_player', participants=['GM', '唐川']),
            ]
        elif sub == 4:
            return [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '第四天开始，事情的走向超出了林朔的想象。玩家们不再满足于打野狼。他们开始把这个世界当成沙盒。')),
                VoiceOperation(OpType.PLAYER, count=4, type='chaos'),
                VoiceOperation(OpType.EMOTION, intensity=1),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '林朔在监控台后面看着这些。他本该烦躁——源能消耗比预计高了30%。但他发现自己嘴角在上扬。')),
            ]
        elif sub == 5:
            return [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '玩家「肝帝老王」死的时候，林朔正盯着能量消耗曲线。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.EMOTION, intensity=5),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '一条红色警报弹出来：「玩家-肝帝老王：生命体征归零。原因：坠落伤害。」')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '然后他看到了一段让他脊背发凉的画面。肝帝老王坠落时撞断了一大片山壁上的岩石，其中一块碎石砸到了山下正在采药的NPC——一个老药师。老药师没有复活。')),
                VoiceOperation(OpType.HOOK, text=self._t('_beat_inciting_hook', '玩家的沙雕行为第一次产生了不可逆的后果。')),
            ]
        else:
            return [
                VoiceOperation(OpType.ACTION, char='林朔', action='decide'),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '「我要亲自去。」林朔说。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.EMOTION, intensity=3),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '墟核沉默了。然后弹出了一行字：「正在生成伪装身份。已生成：墨先生，隐世游侠。注意：离开归墟后，你将失去墟核的直接保护。」')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_inciting', '林朔闭上眼。当他再睁开的时候，面前出现了一片扭曲的光——那是墟核打开的穿越通道。他深吸了一口气，走了进去。')),
            ]

    # ================================================================
    # B_STORY: 第27-35章 —— 叶琳线与玩家羁绊
    # ================================================================
    def _beat_b_story(self, ctx, sub, total):
        ctx.world_name = '武侠·苍云之殇'
        ctx.add_character('林朔', emotional_state='投入')
        ctx.add_character('叶琳', emotional_state='警觉')
        ctx.tone_modifier = 'warm'
        ctx.tension_level = 3

        scenes = {
            1: [
                VoiceOperation(OpType.SCENE, scene_type='苍云山'),
                VoiceOperation(OpType.ACTION, char='林朔', action='arrive'),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_b_story', '林朔以墨先生的身份出现在营地边缘。灰色长袍，铁剑，隐世高人的设定——墟核用三秒钟生成的伪装。但当他看到那群围在篝火边、吵吵嚷嚷地争论谁的装备更好的年轻人时，他忽然觉得自己不需要伪装。')),
            ],
            2: [
                VoiceOperation(OpType.ACTION, char='叶琳', action='arrive'),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_b_story', '叶琳在营地外等了很久。她不是来找玩家的——她是来找墨先生的。那个不说话、只在远处看着她的灰衣人。她不知道他叫什么，不知道他从哪里来。但她知道一件事——在苍云派被灭门的那个晚上，如果有一个像他这样的人在场，也许师父不会死。')),
                VoiceOperation(OpType.DIALOGUE, scene_type='npc_encounter', participants=['叶琳', '林朔']),
            ],
            4: [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_b_story', '林朔在叶琳的手腕上看到了一道紫色的纹路。很细，像毛细血管破了——但颜色不对。那是魔剑碎片侵蚀的痕迹。')),
                VoiceOperation(OpType.EMOTION, intensity=3),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_b_story', '墟核的面板上跳出数据：碎片残留能量——中度。宿主同化风险——低（当前15%）。林朔关掉了面板。15%看起来很低。但他知道这种数字不会停在15%。')),
            ],
            8: [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_b_story', '碎片第一次发作的时候，林朔不在现场。唐川后来跟他说——叶琳突然跪了下来，双手按在胸口，指节全是白的。她的眼睛变成了紫色——不是虹膜，是整个眼球，像被注入了墨水。')),
                VoiceOperation(OpType.EMOTION, intensity=4),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_b_story', '持续了不到一分钟。然后她恢复了——但她的额头上全是冷汗。碎片同化率从15%跳到了25%。林朔关掉了面板。25。不是失控，但快了。')),
            ],
        }

        return scenes.get(sub, scenes[1])

    # ================================================================
    # FUN_GAMES: 第36-48章 —— 玩家沙雕 + 公会系统
    # ================================================================
    def _beat_fun_games(self, ctx, sub, total):
        ctx.world_name = '武侠·苍云之殇'
        ctx.add_character('林朔', emotional_state='认可')
        ctx.add_character('唐川', emotional_state='投入')
        ctx.tone_modifier = 'energetic'
        ctx.tension_level = 3

        ops = []
        if sub == 1:
            ops = [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_fun_games', '公会体系上线那天，唐川在归墟广场上站了很久。GM发的公告只有一句话：玩家可自行组建公会。但唐川看到的不是公告——是一个机会。三天之内，苍云之翼公会人数破百。')),
            ]
        elif sub == 3:
            ops = [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_fun_games', '第一届PVP大赛的现场只能用灾难来形容。规则很简单——一对一，淘汰制。但没人遵守规则。')),
                VoiceOperation(OpType.PLAYER, count=3, type='pvp_chaos'),
            ]
        elif sub == 6:
            ops = [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_fun_games', '贡献榜上线的第一周，最卷的人是肝帝老王。他的在线时长是全服第一——林朔通过墟核看到他的平均睡眠时间是每天四小时。')),
                VoiceOperation(OpType.EMOTION, intensity=2),
            ]
        elif sub == 9:
            ops = [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_fun_games', '公会之间的第一次外交谈判发生在苍云山下。唐川代表苍云之翼，对面是一个新成立三个月的小公会。')),
                VoiceOperation(OpType.DIALOGUE, scene_type='player_interaction', participants=['唐川', '雨落无声']),
            ]
        else:
            ops = [
                VoiceOperation(OpType.PLAYER, count=2, type='daily'),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_fun_games', '林朔已经不记得自己是GM了。他觉得自己更像一个园丁——不是控制什么，是在该浇水的地方浇水，该修剪的地方修剪。')),
            ]

        return ops

    # ================================================================
    # MIDPOINT: 第49-53章 —— 碎片回收 + 千层饼第2层
    # ================================================================
    def _beat_midpoint(self, ctx, sub, total):
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='投入→警觉')
        ctx.tone_modifier = 'resolute'
        ctx.tension_level = 6

        if sub == 1:
            return [
                VoiceOperation(OpType.REVEAL, layer=2),
                VoiceOperation(OpType.EMOTION, intensity=4),
            ]
        elif sub == 2:
            return [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_midpoint', '星图的边缘有一块暗色区域。不规则，像被什么侵蚀过。墟核的注释只有四个字：祂们曾至。')),
                VoiceOperation(OpType.DIALOGUE, scene_type='revelation', participants=['墟核', '林朔']),
                VoiceOperation(OpType.EMOTION, intensity=3),
            ]
        return [
            VoiceOperation(OpType.TEXT, text=self._t('_beat_midpoint', '解锁星图带来了一个意外的后果：林朔现在能看到每一个已连接世界的能量状态。武侠世界是稳定的绿色——但其他三个破碎界世界都在闪烁黄色到橙色之间。它们的碎片还没回收，能量正在缓慢流失。')),
            VoiceOperation(OpType.EMOTION, intensity=2),
        ]

    # ================================================================
    # BAD_GUYS: 第54-65章 —— 代理人出现
    # ================================================================
    def _beat_bad_guys(self, ctx, sub, total):
        ctx.world_name = '末日废土'
        ctx.add_character('林朔', emotional_state='警觉')
        ctx.tone_modifier = 'tense'
        ctx.tension_level = 8

        if sub in (1, 3):
            return [
                VoiceOperation(OpType.SCENE, scene_type='末日废土初现'),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_bad_guys', '末日废土。天空是灰黄色的。空气里有一种烧焦的金属味——不是比喻，是真的。')),
                VoiceOperation(OpType.BREAK),
            ] + ([
                VoiceOperation(OpType.TEXT, text=self._t('_beat_bad_guys', '混沌海裂了一道口子。不是比喻——是真的裂了。从裂缝中走出来的东西像人，但不是人。它的影子不跟着它走——拖在后面，像一件脱不掉的旧衣服。眼睛是两团冷白色的光，没有瞳孔。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_bad_guys', '它开口了——声音像金属刮玻璃：锚定者。碎片回收到此为止。接下来的世界，是我们的。')),
                VoiceOperation(OpType.EMOTION, intensity=5),
                VoiceOperation(OpType.BATTLE, intensity='high'),
            ] if sub == 3 else [])

        return [
            VoiceOperation(OpType.TEXT, text=self._tf('_beat_bad_guys_t', f'废土世界的第{sub}天。天空还是灰黄色的。代理人的能量信号在林朔的面板上忽明忽暗——不是消失了，是在试探。', sub=sub)),
            VoiceOperation(OpType.TEXT, text=self._t('_beat_bad_guys', '墟核的分析数据里出现了一个让他警觉的模式：代理人出现的时间——与碎片能量波动——几乎完全同步。误差不超过三分钟。祂们不是在随意入侵。祂们在追踪碎片——像猎人追踪猎物。而且追踪越来越准。')),
            VoiceOperation(OpType.EMOTION, intensity=2),
            VoiceOperation(OpType.TEXT, text=self._t('_beat_bad_guys', '林朔在归墟里建立了代理人档案。每一次遭遇后提取残留的能量痕迹，比对数据库。一个令人不安的结论浮现出来：代理人的类型不止一种。探索型、战斗型——还有第三种，墟核的数据库里只有一行残缺记录：渗透型，可模仿原住民形态。尚未确认。')),
        ]

    # ================================================================
    # ALL_LOST: 第66-70章 —— 一切失去
    # ================================================================
    def _beat_all_lost(self, ctx, sub, total):
        ctx.world_name = '武侠·苍云之殇'
        ctx.add_character('林朔', emotional_state='绝望')
        ctx.add_character('叶琳', emotional_state='濒死', corruption_level=47)
        ctx.add_character('唐川', emotional_state='恐慌')
        ctx.tone_modifier = 'dark'
        ctx.tension_level = 10

        if sub == 1:
            return [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_all_lost', '叶琳倒下的时候，林朔正在废土世界调度第三轮能量风暴的防御。墟核面板上突然跳出一条来自武侠世界的警报——感应结界触发。能量源：魔剑碎片残余。目标：叶琳。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.ACTION, char='林朔', action='react'),
                VoiceOperation(OpType.EMOTION, intensity=5),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_all_lost', '他撕裂了传送通道。墟核疯狂报警——源能超额消耗，建议取消传送——他没有听。他回到苍云山的时候，第一眼看到的是唐川跪在地上，双手按在叶琳的伤口上——紫光从她的皮肤下渗出来，像活的虫子在她的血管里游。')),
            ]

        return [
            VoiceOperation(OpType.EMOTION, intensity=4),
            VoiceOperation(OpType.TEXT, text=self._tf('_beat_all_lost_t', f'源能储备跌到了红色警戒线——{self._voice._rng.randint(8, 15)}%。墟核的蓝光暗得像快熄灭的蜡烛。', pct=self._voice._rng.randint(8, 15))),
            VoiceOperation(OpType.BREAK),
            VoiceOperation(OpType.HOOK, text=self._t('_beat_all_lost_hook', '彻底治愈的办法只有一个：回收碎片的核心。但核心不在她的身体里——在魔剑本体里。这一刀——得切开15个世界的能量网才能从她体内拔出来。林朔没有这种权限。至少——现在没有。')),
        ]

    # ================================================================
    # DARK_NIGHT: 第71-74章 —— 暗夜灵魂
    # ================================================================
    def _beat_dark_night(self, ctx, sub, total):
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='崩溃中重组')
        ctx.tone_modifier = 'shattered'
        ctx.tension_level = 7

        ops = []
        if sub == 1:
            ops = [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_dark_night', '归墟里只有林朔一个人。墟核的蓝光比平时暗了很多。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.EMOTION, intensity=5),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_dark_night', '他坐在归墟的石阶上，盯着星图上那些他还没来得及探索的发光点。那些世界在等他——那些世界里的人甚至不知道自己正在崩塌。')),
            ]
        elif sub == 3:
            ops = [
                VoiceOperation(OpType.DIALOGUE, scene_type='gm_player', participants=['林朔', '唐川']),
                VoiceOperation(OpType.EMOTION, intensity=4),
            ]
        elif sub == 4:
            ops = [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_dark_night', '白夜的残影第一次出现的时候，林朔正在归墟的壁画前面。那是一团模糊的人形——半透明，边缘不稳定地闪烁。左眼的位置是一块机械义眼的蓝光。')),
                VoiceOperation(OpType.EMOTION, intensity=5),
                VoiceOperation(OpType.DIALOGUE, scene_type='npc_encounter', participants=['白夜', '林朔']),
            ]
        return ops

    # ================================================================
    # BREAK_2: 第75-80章 —— 白夜现身 + 真相初现
    # ================================================================
    def _beat_break_2(self, ctx, sub, total):
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='重新坚定')
        ctx.add_character('白夜', emotional_state='偏执')
        ctx.add_character('唐川', emotional_state='觉醒', knows_truth=True)
        ctx.tone_modifier = 'renewed'
        ctx.tension_level = 8 if sub <= 3 else 5

        if sub == 1:
            return [
                VoiceOperation(OpType.REVEAL, layer=5),
                VoiceOperation(OpType.DIALOGUE, scene_type='npc_encounter', participants=['白夜', '林朔']),
                VoiceOperation(OpType.EMOTION, intensity=5),
            ]
        elif sub == 5:
            return [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_break_2', '观星台。日落。唐川是一个人来的。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_break_2', '唐川先开口。他说了一句话，让林朔准备好的措辞全部作废。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_break_2', '「我知道这不是游戏。」唐川说。他的声音很平静。「我查过了。那个叫叶琳的女孩——她不是程序生成的。她是真实的。你——也不是AI。你是人。和我们一样。」')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.EMOTION, intensity=4),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_break_2', '林朔把能说的都说了。从归墟到源界碎片，从锚定者协议到祂们的代理人，从白夜到第47次循环。')),
            ]
        elif sub == 6:
            return [
                VoiceOperation(OpType.TEXT, text=self._t('_beat_break_2', '林朔说完了。唐川听完之后，很长时间没有说话。最后他说了一句林朔没有预料到的话。')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_break_2', '「所以我们需要所有玩家。」唐川说。「不是当成工具——是当成盟友。告诉他们真相？」')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_break_2', '唐川摇头：「现在不行。大部分人会恐慌。但我们可以慢慢来。从公会的核心成员开始——然后一层一层往外扩。」')),
                VoiceOperation(OpType.BREAK),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_break_2', '林朔看着他。这个22岁的大学生，游戏公会的会长，正在用一个游戏策划的思维方式解决一个宇宙级的危机。也许白夜说对了一件事。这一次的循环——不一样了。')),
            ]

        return [
            VoiceOperation(OpType.TEXT, text=self._tf('_beat_break_2_t', f'白夜的残影在混沌海中闪烁。第{sub}次对话——每一次都比上一次更清晰，也更残酷。', sub=sub)),
            VoiceOperation(OpType.EMOTION, intensity=3),
        ]

    # ================================================================
    # 其余节拍的编排（debate / theme / break_1）
    # ================================================================
    def _beat_debate(self, ctx, sub, total):
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='疲惫')
        ctx.tension_level = 4

        scenes = {
            1: [VoiceOperation(OpType.TEXT, text=self._t('_beat_debate', '林朔发布了第一条探索任务：收集苍云山的药草样本。奖励是一枚铜币——他觉得这个设计很合理。')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_debate', '任务发出后三十分钟，零人接取。玩家频道里飘过一行字：这任务给的也太寒碜了，铜币有毛用？我要经验值！！！林朔盯着那行字，在归墟里骂了一句——他以前设计的都是虚拟利益，现在这些铜币是真实货币，他给不起。'))],
            3: [VoiceOperation(OpType.TEXT, text=self._t('_beat_debate', '林朔禁言了一个在频道里骂人的玩家。理由很充分——那个人用脏话辱骂NPC，引来了苍云派其他弟子的反感，差点触发NPC敌对。')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_debate', '禁言公告发出后五分钟，玩家频道炸了。不是骂那个被禁言的——是骂GM。言论自由呢？GM凭什么禁言？不是开放世界吗？林朔看着滚动的抗议弹幕，忽然觉得这群人比他更像在玩游戏。'))],
            7: [VoiceOperation(OpType.DIALOGUE, scene_type='gm_player', participants=['GM', '唐川']),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_debate', '关掉对话框之后，林朔在归墟的地面上画了一张关系图。玩家、NPC、源界碎片、归墟、祂们。他把之前写的那张纸条——管理玩家——划掉。在旁边写了一行新字：与玩家共治。'))],
            8: [VoiceOperation(OpType.TEXT, text=self._t('_beat_debate', '公会制度的想法是林朔自己提出的。他设计了一套系统：玩家可以建立公会，高级公会可以解锁特殊任务和资源。他用这种方式把玩家组织起来——有序地组织。')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_debate', '结果玩家们完全没按他的设计走。唐川的公会按模板建了起来——但同时崛起了三个野鸡公会，拉人手段一个比一个离谱。林朔没有发公告辟谣。让这群人以为GM有人情味，也许不是坏事。'))],
        }
        return scenes.get(sub, [VoiceOperation(OpType.PLAYER, count=1, type='daily'),
                                VoiceOperation(OpType.TEXT, text=self._t('_beat_debate', '林朔看着面板上的数据曲线。玩家活跃度比昨天高了3%。他不知道该高兴还是该担心——每次数字涨，都意味着有人在武侠世界里多待了三个小时。那个世界是真实的。数字越高，他的责任越重。'))])

    def _beat_theme(self, ctx, sub, total):
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='被迫接受')
        ctx.tension_level = 5

        scenes = {
            1: [VoiceOperation(OpType.TEXT, text=self._t('_beat_theme', '锚定者协议足足有十六章。林朔读了一整个夜晚——虽然他完全不知道外面过了多久。他借着墟核的蓝光一行一行地读。这可能是他这辈子读得最认真的法律文件。')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_theme', '协议的核心条款其实就几条。一、锚定关系不可逆。二、任何世界内死亡即真实死亡——只有归墟之心可以豁免。三、锚定者的职责是管理穿越者，回收散落于万界的源界碎片。四、拒绝履行职责将导致归墟源能耗尽。')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_theme', '林朔读到第四条的时候停了下来。后果由锚定者承担——他翻了翻附录，没有找到后果的具体定义。他忽然想到一件事：如果后果是不可逆的，为什么协议不写清楚？'))],
            2: [VoiceOperation(OpType.TEXT, text=self._t('_beat_theme', '林朔对着墟核骂了整整二十分钟。墟核一个字都没回。那比回嘴更让人绝望。骂完之后他累得靠在石墙上。')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_theme', '「好吧。」他哑着嗓子说。「假设我接受这个烂摊子——我需要做什么？」墟核立刻弹出了回复。它好像一直在等这句话。当前可连接世界：4。建议启动穿越协议，连接第一世界。'))],
            3: [VoiceOperation(OpType.TEXT, text=self._t('_beat_theme', '那天晚上林朔做了一个梦。他站在一片紫色草原上。天空有两个太阳——一个是正常的金黄色，另一个是暗红色，像一只半闭着的眼睛。有人在草原上等他——灰白色的长袍，发光的杖。')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_theme', '那个人对他说了一句话。林朔醒来的时候不记得那句话的内容了。只记得语气——不是威胁，不是恳求，更像是一种久别重逢的招呼。')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_theme', '他坐起来，心跳得很快。墟核的蓝光照着他的脸。他忽然意识到——这个梦的场景，在那面刻痕的墙上见过。就在那句"第四十七次，还是失败"的旁边，有一个非常模糊的图案——一颗暗红色的太阳。'))],
        }
        return scenes.get(sub, scenes[1])

    def _beat_break_1(self, ctx, sub, total):
        ctx.world_name = '武侠·苍云之殇'
        ctx.add_character('林朔', emotional_state='警觉→投入')
        ctx.tension_level = 6

        scenes = {
            1: [VoiceOperation(OpType.TEXT, text=self._t('_beat_break_1', '苍云山后山。唐川小队的能量探测器响了。林朔——以墨先生的身份——已经在这个区域调查了三天。他发现的东西比他预想的要复杂得多。能量源不在山顶，在地底。一座隐藏的洞穴，入口被某种古老的法术封印着。')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_break_1', '墟核通过面板发来消息：「碎片类型：器物。形态：剑。状态：半激活。威胁等级：中等。」林朔站在洞穴入口处。他能感觉到那股能量——不是温度，是一种低沉的震动，从脚底传上来。像有什么东西在地底深处呼吸。'))],
            2: [VoiceOperation(OpType.TEXT, text=self._t('_beat_break_1', '洞穴深处的景象让林朔屏住了呼吸。一把剑悬浮在洞穴中央。剑身长约三尺，通体流淌着紫黑色的光——不是从外部照上去的，是从剑身内部渗出来的，像血管里的血液在流动。剑的周围，空气是扭曲的，仿佛高温下的柏油路。'))],
            3: [VoiceOperation(OpType.TEXT, text=self._t('_beat_break_1', '林朔看到了一切——不是在「看」，是被直接塞进了一段不属于他的记忆里。星辰在头顶熄灭。大地在脚下裂开。无数人的面孔在蓝光中化作尘埃——老人、孩子、战士、学者、恋人握紧的双手——全部，在一瞬间，变成灰。')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_break_1', '然后他看到了归墟。不是现在这座废墟，而是一座完整的、灯火通明的巨大建筑。有人在里面工作——穿着银色长袍的人，在巨大的光幕前操作着什么。他们的表情严肃，但没有恐惧。然后画面里闪过了一个人的脸——灰白色的长袍，发光的杖——那个紫色草原上的灰衣人。')),
                VoiceOperation(OpType.TEXT, text=self._t('_beat_break_1', '灰衣人转过头，看着林朔——不，看着那面剑——说了一句话。不是用汉语，但林朔听懂了意思：记住。然后一切归于黑暗。'))],
        }
        return scenes.get(sub, scenes[1])

    def _beat_generic(self, ctx, sub, total):
        """通用节拍——当某个节拍没有专门的编排器时使用。"""
        return [
            VoiceOperation(OpType.SCENE, scene_type='default'),
            VoiceOperation(OpType.EMOTION, intensity=2),
            VoiceOperation(OpType.TEXT, text=self._tf('_beat_generic_t', f'第{sub}天。{ctx.world_name}。一切在按照既定的轨迹推进——但谁也不知道这条轨迹通向哪里。', world=ctx.world_name, sub=sub)),
        ]

    # ================================================================
    # 第二卷 & 第三卷节拍编排（v2/v3后缀）
    #
    # ⚠️ DEPRECATED —— 已迁移至 beat_orchestrator_legacy.py 的
    # BeatOrchestratorLegacy 混入类。通过多继承保持 getattr 调度兼容。
    # 推荐的 words 路径使用 EmergentOrchestrator（状态驱动），本段仅
    # 对旧 causal/asp 路径有效。
    # ================================================================

