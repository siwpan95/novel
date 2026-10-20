# -*- coding: utf-8 -*-
"""BeatOrchestrator 的 v2/v3 遗留编排方法 —— 仅对旧 causal/asp 路径有效。

⚠️ DEPRECATED —— 推荐的 words 路径使用 EmergentOrchestrator（状态驱动），
本模块的方法通过 getattr(ctx.volume) 动态调度，仅当使用 --mode causal/asp
且设置了 volume=2 或 volume=3 时才会被调用。不参与主流程。

迁移计划（v3.0 前）：
- 所有硬编码叙事文本应提取到 beat_narratives.json 或专用数据文件。
- BeatOrchestrator 应降级为纯片段提供者（算子序列 + 文本查找）。
- 届时本模块直接废弃。

方法总数：24（v2 × 13 + v3 × 11）
"""

# 延迟导入：避免与 beat_orchestrator 产生循环依赖。
# OpType/VoiceOperation 在模块级通过 _resolve_types() 延迟绑定，
# 在 __init_subclass__ 或首次方法调用时从 beat_orchestrator 导入。
_OpType = None
_VoiceOperation = None


def _ensure_types():
    """延迟导入 OpType 和 VoiceOperation（避免循环 import）。"""
    global _OpType, _VoiceOperation
    if _OpType is None:
        from .beat_orchestrator import OpType as _O, VoiceOperation as _V
        _OpType = _O
        _VoiceOperation = _V
    return _OpType, _VoiceOperation


class BeatOrchestratorLegacy:
    """v2/v3 遗留编排方法混入类。

    这些方法通过 BeatOrchestrator.generate_beat() 的 getattr 调度：
        orchestrator = getattr(self, f'_beat_{beat}_v{volume}', None)
    在 volume=2 或 volume=3 时被间接调用。

    OpType/VoiceOperation 通过 __init_subclass__ 在 BeatOrchestrator 定义时
    延迟注入到模块全局 _OpType / _VoiceOperation，避免循环导入。
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        _ensure_types()

    # ================================================================
    # 第二卷节拍编排（v2后缀，共13个）
    # ================================================================

    def _beat_opening_v2(self, ctx, sub, total):
        """Vol2 Opening: 觉醒界初探——东方修仙世界。"""
        ctx.world_name = '东方修仙'
        ctx.add_character('林朔', emotional_state='投入→警觉')
        ctx.tension_level = 6

        if sub == 1:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_opening_v2', '穿越通道的另一端，是一个林朔从未见过的世界。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_opening_v2', '天不是蓝色的——是青中透紫。远处有山悬浮在云海之上，山腰间缠绕的不是云雾，是肉眼可见的灵气流——淡金色的，像无数条丝带在风中飘动。偶尔有一道银光从云层中划出——不是飞机，是人御剑飞行的轨迹。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_opening_v2', '位面适配完成。墟核报告。当前世界规则：东方修仙体系。科技武器降级为凡铁。所有穿越者必须按该世界修炼体系成长。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_opening_v2', '林朔低头看了看自己的手——他的GM面板还在，但所有数值旁边都多了一列：灵气亲和度、境界、灵根属性。面板底部有一行小字：该世界源界碎片已定位。形态：仙器。状态：封印中。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.EMOTION, intensity=3),
            ]
        elif sub == 2:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_opening_v2', '玩家们的反应比林朔预想的快得多。修仙世界的概念在地球流行文化里根深蒂固——降落到这个世界的第一批玩家，只花了不到半小时就接受了这里是修仙世界的现实。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_opening_v2', '有人在频道里狂发我筑基了——林朔查了一下面板，他其实只是炼气三层。但没人纠正他——因为三分钟内，又有十二个人在频道里宣布自己筑基了。')),
                _VoiceOperation(_OpType.PLAYER, count=2, type='daily'),
            ]
        else:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_opening_v2', '林朔开始研究灵气体系。墟核的分析结果显示，这个世界的源界碎片形态与众不同——不是魔剑那种半激活的武器，而是一件被历代大能层层封印的仙器。要回收它，需要先解封——而解封的钥匙，需要通过修炼提升到这个世界的认可等级。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_opening_v2', '换句话说，林朔不能像在武侠世界那样以GM身份直接回收碎片。他必须真的在这里修炼——从炼气期开始。')),
                _VoiceOperation(_OpType.EMOTION, intensity=2),
            ]

    def _beat_midpoint_v2(self, ctx, sub, total):
        """Vol2 Midpoint: 千层饼3-4层 + 终局预演战。"""
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='警觉→震撼')
        ctx.tension_level = 9

        if sub == 1:
            return [
                _VoiceOperation(_OpType.REVEAL, layer=3),
                _VoiceOperation(_OpType.EMOTION, intensity=5),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_midpoint_v2', '万界体系不是自然形成的。墟核的文字变成了红色——这是第二次。它是源为测试文明可能性而设计的实验场。每一个世界、每一种生命形态——都是源的实验变量。包括你回收的碎片——每一片都记录了源对文明演化的设计参数。')),
            ]
        elif sub == 3:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_midpoint_v2', '归墟星图上，觉醒界的四个光点同时亮了起来。不是解锁——是警报。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_midpoint_v2', '检测到大规模代理人集结。墟核的声音里——如果它有声音——第一次出现了一种林朔只能描述为紧张的语速。数量：超过两百。目标：修仙世界的仙器碎片。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_midpoint_v2', '林朔打开了全服广播。他犹豫了不到一秒——然后发出了他作为GM以来最重要的一条公告：\n全体玩家注意。这不是活动。这不是测试。所有在线玩家——前往坐标(仙域·中央平原)。这不是请求。')),
                _VoiceOperation(_OpType.EMOTION, intensity=5),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_midpoint_v2', '十分钟内，修仙世界上空出现了四千多个传送门。那是玩家——第一次以军队的形态出现。')),
            ]
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_midpoint_v2_t', f'终局预演的第{sub}天。修仙世界的天空不再青紫——被代理人的能量场染成了不祥的暗灰色。但林朔看着玩家频道里那些还在发沙雕表情包的人——忽然不那么怕了。', sub=sub)),
            _VoiceOperation(_OpType.EMOTION, intensity=3),
        ]

    def _beat_break_2_v2(self, ctx, sub, total):
        """Vol2 Break2: 唐川觉醒 + 觉醒界全解锁。"""
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='重新坚定')
        ctx.add_character('唐川', emotional_state='觉醒→盟友')
        ctx.tension_level = 7

        if sub == 1:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_break_2_v2', '唐川站在归墟里——不是以玩家的身份通过VR设备，而是林朔用墟核开启的特殊通道。这是第一个被允许进入归墟的玩家。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_break_2_v2', '他看着那些发光的星图、断裂的石柱、悬浮的墟核——他的表情从震撼变成了沉默。沉默了很长时间。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_break_2_v2', '所以。唐川最后说。不是问句。叶琳。苍云山。那些被魔剑杀死的人——他们是真的。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_break_2_v2', '林朔点了点头。唐川的拳头握紧了一下——然后松开了。我现在能做什么？他问。不是为什么骗我们——是我能做什么。')),
                _VoiceOperation(_OpType.EMOTION, intensity=4),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_break_2_v2', '林朔看着这个22岁的大学生。在代理人大军压境的前夕，他得到了一个真正的盟友。')),
            ]
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_break_2_v2_t', '觉醒界的四个世界全部解锁。归墟星图上，第二层花瓣发出了完整的金色光芒。而第三层——神陨界——四个暗红色的光点开始微微闪烁。那是警告。也是邀请。')),
            _VoiceOperation(_OpType.EMOTION, intensity=3),
        ]

    def _beat_theme_v2(self, ctx, sub, total):
        """Vol2 Theme: 适应修仙世界规则。"""
        ctx.world_name = '东方修仙'
        ctx.add_character('林朔', emotional_state='投入→警觉')
        ctx.tension_level = 5
        scenes = {
            1: [_VoiceOperation(_OpType.TEXT, text=self._t('_beat_theme_v2', '修仙世界的规则比武侠世界复杂得多。不是简单的打怪升级——墟核的分析报告显示，这个世界的修炼体系有九个大境界，每一个都细分为前中后三期。而碎片的目标——那件仙器——需要在至少元婴期的修为才能触及封印。')),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_theme_v2', '林朔不是一个人。玩家们已经在疯狂修炼了。有人在频道里分享了冥想的技巧——不是游戏技巧，是真的打坐方法。有人两天没睡——不是肝游戏，是真的一直在引气入体。林朔看着他们的数据，忽然想到一个问题：如果修炼不仅仅是游戏机制呢？如果他们在修炼的是这个世界真实的力量——那回到地球之后，他们还能用吗？'))],
            2: [_VoiceOperation(_OpType.TEXT, text=self._t('_beat_theme_v2', '白夜的声音从混沌海传来——比之前更清晰了。他已经能投射出半身虚影。\n代理人来了。白夜说。他的语气不像警告——更像是在陈述一件早已发生的事情。\n修仙世界的代理人——和废土的不一样。祂们派来的是渗透型。已经混入了一个修仙宗门。')),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_theme_v2', '林朔的手指在面板上停下来。渗透型——可模仿原住民形态。这意味着他永远不知道哪个NPC——不是NPC，哪个真实的修士——是被替代的。'))],
            3: [_VoiceOperation(_OpType.TEXT, text=self._t('_beat_theme_v2', '林朔自己也开始修炼了。不是为了变强——是为了理解。他坐在一座无名的山峰上，按墟核给的基础吐纳法门，第一次尝试引灵气入体。那种感觉很陌生——不是代码运行，不是数据分析。是一种温热的、流动的感觉从丹田升起。他不知道这算不算炼气第一层——但他知道自己正在改变。不是身体——是某种更根本的东西。'))],
        }
        return scenes.get(sub, scenes[1])

    def _beat_inciting_v2(self, ctx, sub, total):
        """Vol2 Inciting: 代理人遭遇升级——渗透型代理人第一次正面交锋。"""
        ctx.world_name = '东方修仙'
        ctx.add_character('林朔', emotional_state='警觉→战斗')
        ctx.tension_level = 8
        if sub == 1:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_inciting_v2', '事情的转折发生在一个普通的早晨。一个在修仙宗门做杂役弟子的玩家——ID叫修行不如修bug——发了一条消息：他宗门里的二师兄昨天还跟他一起挑水，今天早上坐在正殿里，说话的语气、坐姿、甚至端茶杯的动作——全变了。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_inciting_v2', '林朔调出了那个玩家的数据——然后看到了让他脊背一凉的画面。二师兄的能量读数不是人类的。不是修士的。是代理人的。渗透型已经替换了原住民——而且不知道替换了多久。')),
            ]
        elif sub == 3:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_inciting_v2', '林朔没有发出公告。他知道如果告诉玩家们有一个NPC被外星存在替换了，后果可能比代理人本身更危险——恐慌会散播得比敌人快。他选择了另一种策略。他以墨先生的身份找到了那个叫修行不如修bug的玩家——给了他一个支线任务：监视二师兄，记录他每一天的异常行为。奖励是一颗筑基丹的配方。')),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_inciting_v2', '玩家欣然接受。他不知道自己在为GM当间谍。而林朔看着那个任务链上的每一个数据点——第一次觉得玩家不只是工具。他们是这个世界的免疫系统。')),
            ]
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_inciting_v2_t', f'第{sub}个异常报告传来的时候，林朔正在核对修仙世界的时间线。渗透型代理人的行动有规律——它们在接近碎片封印的位置。不是在攻击——是在测绘。它们想打开封印。', sub=sub)),
            _VoiceOperation(_OpType.EMOTION, intensity=3),
        ]

    def _beat_debate_v2(self, ctx, sub, total):
        """Vol2 Debate: 多世界并行管理的困境。"""
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='疲惫→警觉')
        ctx.tension_level = 5
        scenes = {
            1: [_VoiceOperation(_OpType.TEXT, text=self._t('_beat_debate_v2', '管理四个世界比管理一个世界难的不是四倍——是指数级。武侠世界的碎片需要定期维护——魔剑的残余能量仍在缓慢侵蚀苍云山。废土世界的能量核心稳定性持续下降。修仙世界的渗透型代理人还在潜伏。而第四个觉醒界——星际殖民——刚刚连通，它的碎片形态是一种量子核心，已经在地底深处自行运转了两百年。')),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_debate_v2', '林朔第一次有了摊子太大的感觉。墟核的源能储备显示：同时维持四个世界的连接消耗，只剩下不到30%的余量。每一次传送、每一次复活、每一次扫描——都在消耗那个百分比。'))],
            3: [_VoiceOperation(_OpType.DIALOGUE, scene_type='gm_player', participants=['GM', '唐川']),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_debate_v2', '唐川在那次对话之后做了一件事。他把四个世界的公会会长拉进了一个私密频道——不是GM建的，是玩家自己建的。跨世界情报共享网络。林朔第一次知道这件事的时候，已经运行了一周。一周内，玩家们自己交换的情报比墟核自动采集的还多。'))],
            5: [_VoiceOperation(_OpType.TEXT, text=self._t('_beat_debate_v2', '林朔在归墟星图前站了很久。星图上的四个觉醒界光点都在闪烁——不是警报，是连接请求。每个世界都有碎片需要回收，每个世界都有玩家需要管理，每个世界都有代理人在渗透。他不能同时出现在四个地方。但玩家可以。')),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_debate_v2', '他决定做一件前46个锚定者从未做过的事：把部分GM权限下放给玩家。不是全部——但足够让他们自己管理自己的世界。墟核的警告弹了三次。他全部忽略了。'))],
        }
        return scenes.get(sub, scenes[1])

    def _beat_break_1_v2(self, ctx, sub, total):
        """Vol2 Break1: 进入星际殖民世界——碎片是量子核心。"""
        ctx.world_name = '星际殖民'
        ctx.add_character('林朔', emotional_state='警觉→震撼')
        ctx.tension_level = 7
        if sub == 1:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_break_1_v2', '星际殖民世界的第一印象让林朔忘了呼吸。他站在一艘废弃的殖民母舰的舰桥上，舷窗外是无尽的星海。每一颗星星都是一个太阳——但他看到的不是星星，是星图。不是归墟的星图——是真实的、物理意义上的恒星。他伸手去触摸舷窗——玻璃是冷的。这不是模拟。这些星星是真的。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_break_1_v2', '墟核的报告显示：这个世界的源界碎片形态是一颗量子核心，埋在一颗气态巨行星的地核深处。回收需要一艘能承受行星级压力的飞船——而这艘船上的人已经死了。死了两百年。舰桥的座位上还坐着一具骸骨，手里握着一枚已经暗淡的全息徽章。')),
            ]
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_break_1_v2_t', '林朔开始研究这艘殖民母舰的系统。它的AI核心还在运转——用最后的一点备用能源维持着生命维持系统。当林朔用墟核接通它的界面时，AI说了一句话——用源界文明的语言：欢迎回家。锚定者。')),
            _VoiceOperation(_OpType.EMOTION, intensity=4),
        ]

    def _beat_b_story_v2(self, ctx, sub, total):
        """Vol2 B-Story: 星际世界的原住民——AI与最后的人类后裔。"""
        ctx.world_name = '星际殖民'
        ctx.add_character('林朔', emotional_state='投入')
        ctx.tension_level = 4
        scenes = {
            1: [_VoiceOperation(_OpType.TEXT, text=self._t('_beat_b_story_v2', '舰载AI的名字叫导航者。它已经独自运行了两百年——维持着最后一批殖民者的冷冻舱。二十七个冷冻舱——二十五个已经失效。剩下两个里面的人还活着，但AI不知道还能维持多久。它问林朔是否愿意接管舰队权限。林朔看着那二十七个名字——二十五个已经灰了——他点了确认。')),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_b_story_v2', '那两个活着的人——一男一女，四十多岁——醒过来的时候，以为只过了一夜。林朔不知道该怎么告诉他们：你们睡了两百年，而在这两百年里，人类的殖民舰队已经全部失联了。'))],
            3: [_VoiceOperation(_OpType.TEXT, text=self._t('_beat_b_story_v2', '玩家们对这个世界的反应让林朔意外。没有人把冷冻舱里的人当NPC。有人在频道里发起了一个募捐——不是游戏币，是真的在讨论：怎么用这个世界的科技造一艘新船，带这两个人去一个安全的地方。')),
                _VoiceOperation(_OpType.DIALOGUE, scene_type='player_interaction', participants=['唐川', '考据狂魔'])],
        }
        return scenes.get(sub, scenes[1])

    def _beat_fun_games_v2(self, ctx, sub, total):
        """Vol2 Fun-Games: 玩家在修仙世界的沙雕。"""
        ctx.world_name = '东方修仙'
        ctx.add_character('林朔', emotional_state='认可→无奈')
        ctx.tension_level = 3
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_fun_games_v2_t2', f"修仙世界第{sub+40}天。玩家们在修炼之余——如果他们还有之余的话——开始了新一轮沙雕活动。有人发现灵兽可以驯服之后，在宗门门口开了一家灵兽美容院。有人试图用炼丹术炸开一个山洞——成功了，但炸出来的不是宝库，是一窝正在冬眠的妖兽。有人把御剑术的飞行轨迹当成了表演——在天空中用剑气画了一个巨大的表情包。整个宗门的长老看着天空，集体沉默了。", sub40=sub+40)),
            _VoiceOperation(_OpType.PLAYER, count=2, type='daily'),
        ]

    def _beat_bad_guys_v2(self, ctx, sub, total):
        """Vol2 Bad-Guys: 代理人战争——多个祂的内斗 + 渗透型全面暴露。"""
        ctx.world_name = '赛博都市'
        ctx.add_character('林朔', emotional_state='警觉')
        ctx.tension_level = 9
        if sub == 1:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_bad_guys_v2', '赛博都市是一个让林朔脊背发凉的地方——不是因为它的高科技低生活，是因为代理人在这里不是潜伏——是公开的。祂们以企业的形态存在。三个不同的代理人阵营控制了这座城市的三家超企——它们在明面上竞争市场份额，暗地里在争抢碎片。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_bad_guys_v2', '最让林朔不安的发现是：这些代理人之间也在争斗。墟核的分析显示，祂们并非一个统一的敌人。探索型代理人收集数据卖给战斗型，渗透型代理人潜伏在两者的组织中互相策反。祂们之间的内斗——可能是林朔最大的机会。也可能是最大的陷阱。')),
            ]
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_bad_guys_v2_t', f'第{sub}个代理人据点被玩家突袭的记录出现在林朔的面板上。战斗越来越频繁——不是林朔发起的，是玩家们自发组织的。他们把这些代理人当成了世界BOSS。每打掉一个，就在论坛里发攻略。林朔看着攻略帖的评论区——有人在计算掉落率。有人在拼凑代理人的背景故事。没有人知道他们在打的不是BOSS——是真实存在的、来自更高维度的入侵者。', sub=sub)),
            _VoiceOperation(_OpType.EMOTION, intensity=3),
        ]

    def _beat_all_lost_v2(self, ctx, sub, total):
        """Vol2 All-Lost: 唐川发现真相 + 修仙世界碎片失控。"""
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='崩溃')
        ctx.add_character('唐川', emotional_state='震撼→觉醒')
        ctx.tension_level = 10
        if sub == 1:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_all_lost_v2', '唐川发现了真相——不是林朔告诉他的。是他自己拼出来的。修仙世界的渗透型代理人露出了破绽——在它替换的那个二师兄的记忆里，有一段关于天外来客的记录。唐川读完了那份记录。然后他在GM频道发了一个坐标——归墟最深处的壁画区。他已经自己在归墟里探索了很久。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_all_lost_v2', "我知道这不是游戏。唐川的声音在GM频道里是文字，但林朔能听到他声音里的颤抖。那些NPC——那些修士——他们是活的。代理人替换的其中一个——他死之前说的最后一个词是——妈妈。代理人不能用这个词——它们不懂这个词。它们复制了语言，复制不了意义。")),
                _VoiceOperation(_OpType.EMOTION, intensity=5),
            ]
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_all_lost_v2_t', f'修仙世界的仙器封印在第{sub}天被代理人撕开了第一道裂缝。林朔看着墟核面板上跳出的数据——碎片的能量正在爆发性增长，如果不在一周内完成回收，整个修仙世界会在能量反噬中崩塌。三百多万原住民。全在这条线上。', sub=sub)),
            _VoiceOperation(_OpType.EMOTION, intensity=5),
        ]

    def _beat_dark_night_v2(self, ctx, sub, total):
        """Vol2 Dark-Night: 林朔的第二次存在危机——唐川知道后该怎么办。"""
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='崩溃中重组')
        ctx.tension_level = 7
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_dark_night_v2_t', '归墟里只有林朔一个人。墟核的蓝光照着他的脸——比平时暗了。源能储备——19%。四个觉醒界在同时消耗。修仙世界在倒计时。')),
            _VoiceOperation(_OpType.BREAK),
            _VoiceOperation(_OpType.TEXT, text=self._t('_beat_dark_night_v2', '他做了前46个锚定者从未做过的事。他把真相告诉了唐川——全部。不是以GM的身份。是以林朔的身份。从归墟到源界碎片，从锚定者协议到祂们，从白夜到第47次循环。他没有说自己记忆可能是假的——那不在他的承受范围之内。')),
            _VoiceOperation(_OpType.BREAK),
            _VoiceOperation(_OpType.TEXT, text=self._t('_beat_dark_night_v2', '唐川听完之后的反应让林朔意外。他没有崩溃。他只是问了一句：所以我们需要所有玩家——不是当成工具，是当成盟友？林朔看着他——这个22岁的大学生——在最该恐慌的时候，问出了最该问的问题。')),
            _VoiceOperation(_OpType.EMOTION, intensity=4),
        ]

    # ================================================================
    # 第三卷节拍编排（v3后缀，共11个）
    # ================================================================

    def _beat_opening_v3(self, ctx, sub, total):
        """Vol3 Opening: 神陨界初探——诸神黄昏。"""
        ctx.world_name = '诸神黄昏'
        ctx.add_character('林朔', emotional_state='警觉→敬畏')
        ctx.tension_level = 9

        if sub == 1:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_opening_v3', '神陨界的大门打开时，林朔感觉到了一种他从未在归墟中体验过的东西——重力。不是物理意义上的重力——是历史的重量。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_opening_v3', '天空是裂开的。不是比喻——一道巨大的裂隙横贯天际，像是被什么力量从内部撕开的伤口。裂隙的边缘仍在发出微弱的光——那是神明陨落时释放的最后能量，两万年了，仍在燃烧。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_opening_v3', '地面上散落着巨大的骨骸——不是人的，也不是任何已知生物的。神骸。有些骨头比归墟最高的石柱还大。其中一根上面长满了发光的花——花瓣是金属质感的，在风中发出细碎的碰撞声。林朔见过这种花。在他的梦里。紫色草原上的那种。')),
                _VoiceOperation(_OpType.EMOTION, intensity=5),
            ]
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_opening_v3_t', '墟核的神陨界数据加载得很慢——慢到林朔怀疑它在犹豫。当数据终于完整显示时，他明白了为什么：这个世界不是接近源的力量——它就是源的一部分。诸神的陨落——是源解体自己的第一步。')),
            _VoiceOperation(_OpType.EMOTION, intensity=4),
        ]

    def _beat_inciting_v3(self, ctx, sub, total):
        """Vol3 Inciting: 千层饼第5层——循环真相 + 渗透型代理人的真面目。"""
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='警觉→震撼')
        ctx.add_character('白夜', emotional_state='偏执→坦白')
        ctx.tension_level = 9
        if sub == 1:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_inciting_v3', '白夜的虚影第一次完整出现在归墟中——不是残影，是整个上半身。他的左眼机械义眼闪烁着幽蓝的光，右手的能量体在不断重组。他用了很大的力气才维持这个形态。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_inciting_v3', '你想知道祂们的代理人为什么越来越聪明。白夜说——不是问句。\n因为祂们在学习。每一次循环，祂们都会记住。前46次——祂们记住了所有锚定者的策略、所有玩家的行为模式、所有世界的弱点。第47次——也就是我那次——祂们已经开始模仿玩家了。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_inciting_v3', '林朔的血液停了一瞬。模仿玩家——是什么意思？\n白夜的机械义眼暗了一秒——他在犹豫。然后他说了：渗透型代理人——不是从一开始就有的。是第46次循环之后才出现的。它们不是被创造的——是被改造的。祂们改造了前几轮循环的玩家——那些失败的锚定者身边的玩家——把他们变成了渗透者。')),
                _VoiceOperation(_OpType.EMOTION, intensity=5),
            ]
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_inciting_v3_t', f'墟核的深层日志开始解锁。第{sub}条记录显示了一个名字——林朔不认识，但白夜认识。那是他那一轮的玩家领袖。在一次大规模战斗中失踪——所有人都以为他死了。他没有。他被改造成了渗透型代理人。他现在还在某个世界里——以某个NPC的身份——活着。', sub=sub)),
            _VoiceOperation(_OpType.EMOTION, intensity=4),
        ]

    def _beat_debate_v3(self, ctx, sub, total):
        """Vol3 Debate: 前锚定者玩家叛变 + 内部分裂。"""
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='警觉→动摇')
        ctx.tension_level = 7
        scenes = {
            1: [_VoiceOperation(_OpType.TEXT, text=self._t('_beat_debate_v3', '唐川在玩家频道里收到了一个私信。来自一个从未见过的ID——第46次·幸存者。内容是：不要相信GM。他不是你想的那个人。我们曾经也相信过我们的锚定者——然后他放弃了我们。')),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_debate_v3', '唐川把这条私信转给了林朔。两个人沉默了很久。最后唐川打了四个字：他在说谎？\n林朔不知道。他不知道前46次循环的玩家发生了什么。他不知道白夜那一轮究竟是怎么失败的。他只知道一件事：如果前46轮的玩家有一部分变成了渗透者——那他身后的四千多个玩家，有多少会成为祂们的下一个目标？'))],
            3: [_VoiceOperation(_OpType.TEXT, text=self._t('_beat_debate_v3', '渗透开始发生在玩家中。不是物理渗透——是信息渗透。有人在论坛发帖质疑GM的真实身份。有人开始挖归墟壁画上的刻痕——他们说这不是游戏的一部分，这是证据——证明这个世界有过之前的循环。')),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_debate_v3', '林朔没有禁言任何人。不是因为策略——是因为他不知道该不该。如果这些玩家挖出了真相——如果他们知道了自己可能被放弃——他是该阻止，还是该让他们知道？'))],
        }
        return scenes.get(sub, scenes[1])

    def _beat_break_1_v3(self, ctx, sub, total):
        """Vol3 Break1: 克苏鲁深渊——不可名状的知识。"""
        ctx.world_name = '克苏鲁深渊'
        ctx.add_character('林朔', emotional_state='警觉→疯狂边缘')
        ctx.tension_level = 10
        if sub == 1:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_break_1_v3', '克苏鲁深渊不是林朔选择去的——是碎片指引他去的。墟核的扫描显示，最后一个神陨界的碎片在深海之下的拉莱耶——一座角度不对的古城。当林朔第一次通过传送门进入那片海域时，他听到的不是海水——是低语。在他的脑子里。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_break_1_v3', '那声音不是恶意的——这是最可怕的地方。它是中性的。像一个人在给你读一本科普书——只是这本书的内容不应该被任何人类读到。它告诉你宇宙的真相、源的真相、你的真相——而你每听懂一句，理智就碎掉一块。')),
                _VoiceOperation(_OpType.EMOTION, intensity=5),
            ]
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_break_1_v3_t', '墟核的理智监测第一次亮起了黄色预警。林朔在拉莱耶深处发现的东西不是碎片——是一个活的记忆。源的记忆。源不是沉睡——源是把记忆散落在了万界中。而拉莱耶里的记忆碎片告诉林朔一件事：他的梦——那个紫色草原、那个灰衣人——不是幻觉。那是源的最后一段记忆。灰衣人——就是源。')),
            _VoiceOperation(_OpType.EMOTION, intensity=5),
        ]

    def _beat_b_story_v3(self, ctx, sub, total):
        """Vol3 B-Story: 白夜的了断——与前锚定者的最终对话。"""
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='投入→释然')
        ctx.add_character('白夜', emotional_state='偏执→释然')
        ctx.tension_level = 6
        scenes = {
            1: [_VoiceOperation(_OpType.TEXT, text=self._t('_beat_b_story_v3', '白夜站在归墟的壁画前——那面刻着第四十七次，还是失败的墙。他的能量体手指悬停在刻痕上方——没有触碰到石头，但他能感觉到每一道刻痕的温度。那是他刻的——在上一轮循环的最后一刻。')),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_b_story_v3', '你知道我刻这个的时候在想什么吗。白夜说。不是问句。\n我在想——如果下一个锚定者看到这个，他会怎么做。我刻的不是绝望——是警告。不是给下一个人的警告——是给我自己的。我太晚了。但我不想让你也晚。'))],
            3: [_VoiceOperation(_OpType.TEXT, text=self._t('_beat_b_story_v3', '白夜用尽了最后的能量。他的虚影开始消散——从左手的指尖开始，一点一点变成光点。他的机械义眼是最后消失的——在完全熄灭之前，他说了最后一句话。')),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_b_story_v3', '林朔——你不是第48个。你是第0个。编号000——源创造的第一个人——不是锚定者，是锚。源用自己最后的意识造了你——你是祂的最后一个实验。不是测试文明——是测试自己能不能留下一个不会被循环抹除的存在。')),
                _VoiceOperation(_OpType.EMOTION, intensity=5),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_b_story_v3', '白夜消失在归墟的虚空中。壁画上只剩下一句新的刻痕——不是他刻的。是墟核自动留下的：第四十七次——成功。'))],
        }
        return scenes.get(sub, scenes[1])

    def _beat_fun_games_v3(self, ctx, sub, total):
        """Vol3 Fun-Games: 终局前的平静——玩家们的最后日常。"""
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='认可→感伤')
        ctx.tension_level = 2
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_fun_games_v3_t', '终局前的最后一段平静日子。归墟广场上，玩家们像没事一样聊天、交易、争论装备——只有林朔知道，这个广场在接下来的几天里可能会变成战场。他站在监控台后看着这群人——有人在讨论今晚的公会聚餐，有人在办告别派对（一个明天要考试的玩家），有人在弹幕里刷今天天气真好。')),
            _VoiceOperation(_OpType.BREAK),
            _VoiceOperation(_OpType.TEXT, text=self._t('_beat_fun_games_v3', '林朔关掉监控台。走了出去——不是在监控室里看数据，是真的走到归墟广场上，以一个普通NPC的身份，看了这群人十分钟。没有人认出他。但他记住了每一个人的脸。')),
            _VoiceOperation(_OpType.EMOTION, intensity=2),
        ]

    def _beat_midpoint_v3(self, ctx, sub, total):
        """Vol3 Midpoint: 千层饼第6层——林朔真实身份 + 造物主遗迹。"""
        ctx.world_name = '造物主遗迹'
        ctx.add_character('林朔', emotional_state='震撼→顿悟')
        ctx.tension_level = 10
        if sub == 1:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_midpoint_v3', '造物主遗迹——源的心脏所在。林朔穿过了那条镜子长廊——每一面镜子映出的都是不同的他。不同年龄、不同身份、不同选择。有一个镜子里是游戏策划林朔——坐在办公室里，永远没被选中。有一个镜子里是白夜——不是白夜本人，是白夜那一轮的林朔。有一个镜子里——什么都没有。只有一片蓝色。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_midpoint_v3', '源的心脏悬浮在玻璃容器中央——不是心脏，是一颗被束缚的黑洞。林朔走近的时候，他听到的不是声音——是问题。源在用创造万物之前的语言问他一个问题。他听不懂那道语言——但他知道答案。')),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_midpoint_v3', '白夜说的是对的。他是第0号——源的最后一份意识。不是第48个锚定者——是第1个。他所有的记忆——林朔、28岁、游戏策划——都是真的，也都不是真的。源用祂自己的记忆塑造了林朔——源曾经也是一个人，在一个和地球几乎一样的世界里，做过一个游戏策划。')),
                _VoiceOperation(_OpType.EMOTION, intensity=5),
            ]
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_midpoint_v3_t', '所以我的选择——林朔对着那颗黑洞说。\n黑洞没有回答。但镜子里那个空白的林朔——那个只有一片蓝色的——动了一下。那是源在告诉他：你不是第48个。你是第1个。你的选择——就是源的选择。')),
        ]

    def _beat_bad_guys_v3(self, ctx, sub, total):
        """Vol3 Bad-Guys: 终局大战——全员 vs 祂们。"""
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='坚定→战斗')
        ctx.tension_level = 10
        if sub == 1:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_bad_guys_v3', '祂们来了。不是代理人——是祂们本身。混沌海的裂缝在归墟上空撕开了一道横贯虚空的伤口。从伤口中涌出的不是军队——是存在。不是物理意义的存在——是法则层面的。祂们每前进一步，归墟的物理规则就改变一次。左一步——重力消失。右一步——光速减半。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_bad_guys_v3', '林朔打开了所有世界的传送门——不是归墟到世界，是世界到归墟。武侠世界的剑客、修仙世界的修士、赛博都市的黑客、星际殖民的AI舰队——以及所有还在线的玩家——全部出现在归墟之中。')),
                _VoiceOperation(_OpType.EMOTION, intensity=5),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_bad_guys_v3', '唐川在公屏上发了最后一条公告。不是GM发的——是玩家发的：这不是游戏。但我们可以赢。')),
            ]
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_bad_guys_v3_t', f'战斗的第{sub}天。归墟的地形已经面目全非——重力、空间、时间都在不稳定地波动。但玩家们还在。不是四千个——是三千两百个。倒下的不是全部能复活——源能耗尽了。但剩下的每一个都还在战斗。', sub=sub)),
            _VoiceOperation(_OpType.EMOTION, intensity=4),
        ]

    def _beat_all_lost_v3(self, ctx, sub, total):
        """Vol3 All-Lost: 终极代价——源能耗尽，归墟开始崩塌。"""
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='绝望→牺牲')
        ctx.tension_level = 10
        if sub == 1:
            return [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_all_lost_v3', '源能归零了。墟核的蓝光——永远没有温度、永远闪烁、永远回答公事公办的问题——第一次，完全暗了下去。林朔站在黑暗的归墟中，看着星图上的光点开始熄灭。不是一个接一个——是连锁反应。武侠世界的光最先灭。然后是修仙世界。废土世界。赛博都市。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_all_lost_v3', '所有人——撤。回地球。林朔发出了作为GM的最后一条指令。他用了归墟最后的备用能量——不是传送，是强制弹出——把还活着的一千八百多个玩家，全部弹回了地球。他们的身体会在各自的房间里醒来——以为自己做了一个很长很长的梦。')),
                _VoiceOperation(_OpType.EMOTION, intensity=5),
            ]
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_all_lost_v3_t', '归墟还剩最后一点结构没有崩塌。墟核暗着——但它没有碎。林朔把手放在水晶上——冰凉。他想起第一次触碰它的时候——静电般的刺痛。现在没有痛感了。也没有温度。只是冰凉。像一块普通的石头。')),
        ]

    def _beat_dark_night_v3(self, ctx, sub, total):
        """Vol3 Dark-Night: 终极选择——维持/摧毁/重建。"""
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='崩溃→顿悟')
        ctx.tension_level = 9
        return [
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_dark_night_v3_t', '源的黑色心脏在林朔面前缓缓旋转。祂们被挡在了归墟之外——不是被力量，是被林朔的选择。源的最后一道设计是：只有第0号可以做出终极选择。不是源的选择——是第0号的选择。')),
            _VoiceOperation(_OpType.BREAK),
            _VoiceOperation(_OpType.TEXT, text=self._t('_beat_dark_night_v3', '林朔站在那颗黑洞面前，看到了三个选项——不是文字，是画面。\n第一个画面：维持万界体系。归墟重建，玩家重新降临，循环继续。第48次。\n第二个画面：摧毁实验场。万界崩塌，所有世界重归混沌——但祂们也会被毁灭。同归于尽。\n第三个画面：成为新的源。用自己的意识重建万界——不是作为实验场，是作为家。不需要锚定者，不需要代理人，不需要祂们。每一个人——原住民、玩家、甚至那些被改造的前锚定者玩家——都是自由的。')),
            _VoiceOperation(_OpType.BREAK),
            _VoiceOperation(_OpType.TEXT, text=self._t('_beat_dark_night_v3', '林朔想到了唐川在最后一条公告里的话。想到了叶琳第一次叫他前辈的时候。想到了白夜消散前说的最后一句。想到了第47道刻痕旁边的那个新的痕迹——墟核的自动刻痕：第四十七次——成功。')),
            _VoiceOperation(_OpType.EMOTION, intensity=5),
        ]

    def _beat_break_2_v3(self, ctx, sub, total):
        """Vol3 Break2: 结局——林朔的选择。"""
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='顿悟→平静')
        ctx.tension_level = 6
        return [
            _VoiceOperation(_OpType.TEXT, text=self._t('_beat_break_2_v3', '林朔选了第三个。')),
            _VoiceOperation(_OpType.BREAK),
            _VoiceOperation(_OpType.TEXT, text=self._tf('_beat_break_2_v3_t', '当他将手伸入源的心脏——那颗被束缚的黑洞——时，他感受到的不是痛苦。是完整。所有的记忆碎片——第0号的、源的、前47个锚定者的、无数玩家的、十二个世界四十七亿原住民的——全部汇入他的意识。不是被覆盖——是被理解。他理解了源为什么要做实验——不是因为傲慢，是因为孤独。源是万界中唯一的意识——它想知道除了自己，还有没有其他可能。')),
            _VoiceOperation(_OpType.BREAK),
            _VoiceOperation(_OpType.TEXT, text=self._t('_beat_break_2_v3', '林朔——第0号、第48个锚定者、源的最后一份意识——闭上了眼睛。当他再睁开的时候，归墟的星图上不再只有十二个世界。所有曾经崩塌的世界——所有前47次循环中消失的世界——全部亮了回来。不是重建——是重新开始。每个世界都有自己的规则、自己的文明、自己的选择。不再有锚定者。不再有祂们。')),
        ]

    def _beat_epilogue_v3(self, ctx, sub, total):
        """Vol3 Epilogue: 开放结局。"""
        ctx.world_name = '归墟'
        ctx.add_character('林朔', emotional_state='平静→希望')
        ctx.tension_level = 2
        endings = {
            1: [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_epilogue_v3', '尾声。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_epilogue_v3', '唐川在地球的大学宿舍里醒过来。耳机挂在脖子上——《万界》的游戏图标在他的VR设备上闪烁。他盯着那个图标看了很久。然后他点了一下——不是登录，是看玩家列表。历史在线记录：林朔（GM）——最后在线：刚才。状态：离线。但离线原因那一栏写着三个字——不是系统预设的。谢谢你。')),
                _VoiceOperation(_OpType.EMOTION, intensity=1),
            ],
            2: [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_epilogue_v3', '叶琳在苍云山上看到了一道蓝光。不是日落的反光——是一颗新的星星。苍云山从此多了一个传说：每当月圆之夜，山顶上会多出一颗蓝色的星。老药师说那是天人回去的地方。叶琳知道不是。那是他——在看着。')),
            ],
            3: [
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_epilogue_v3', '归墟不再是一座废墟。新的星图上没有暗色区域——没有祂们的侵蚀。墟核悬浮在半空中——蓝光柔和地照着空无一人的大殿。过了一会儿，传送门亮了一下。一个人走出来——不是林朔，不是唐川，不是任何一个玩家。是一个新的人。来自一个林朔创造的新世界。他疑惑地看着墟核。墟核闪烁了一下——然后弹出了四行字。')),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_epilogue_v3', '锚定者协议——已废弃。\n协议替代：自由探索协议。\n欢迎来到归墟。\n你也可以选择离开。一切都是你的选择。')),
                _VoiceOperation(_OpType.BREAK),
                _VoiceOperation(_OpType.TEXT, text=self._t('_beat_epilogue_v3', '那个人站在归墟的中央，看着星图上无数闪烁的光点——每一个都是一个自由的世界。他犹豫了一下。然后他向前走了一步。')),
            ],
        }
        return endings.get(sub, endings[3])
