# -*- coding: utf-8 -*-
"""因果对话引擎：基于角色状态 + 情节上下文 + 角色议程的对话生成。

区别于随机模板对话，因果对话的每句话都：
1. 有角色议程（这个角色想从对话中达成什么）
2. 受角色当前情绪状态影响
3. 推动情节或揭示信息
"""



class CausalDialogueEngine:

    def __init__(self, wb, plot_state):
        self._wb = wb
        self._ps = plot_state
        self._rng = wb.get_rng()

    def generate(self, scene_type, participants, context=None):
        if context is None:
            context = {}
        char_states = {}
        for name in participants:
            state = self._ps.get_char_state(name) or {}
            char_states[name] = {
                'emotional': state.get('emotional_state', '中性'),
                'goal': state.get('current_goal', '未知'),
                'knows_truth': state.get('knows_truth', False),
                'relations': state.get('relations', {}),
            }
        gen = getattr(self, '_gen_' + scene_type, None)
        if gen:
            return gen(participants, char_states, context)
        return self._gen_generic(participants, char_states, context)

    # ======================== GM-玩家对话 ========================
    def _gen_gm_player(self, participants, char_states, context):
        rng = self._rng
        gm_name = participants[0] if participants else 'GM'
        player_name = participants[1] if len(participants) > 1 else '玩家'
        gm_emotion = char_states.get(gm_name, {}).get('emotional', '中性')
        char_states.get(player_name, {}).get('emotional', '兴奋')
        player_knows = char_states.get(player_name, {}).get('knows_truth', False)

        lines = []

        # GM开场
        if gm_emotion in ('疲惫', '警觉'):
            lines.append(rng.choice([
                gm_name + '沉默了两秒才回复：\u201c已收到。请说。\u201d',
                gm_name + '的回复比平时慢了半拍：\u201c在。什么事？\u201d',
                '对话框里跳出一个字：\u201c说。\u201d',
            ]))
        elif gm_emotion in ('认可', '投入'):
            lines.append(rng.choice([
                gm_name + '迅速回复：\u201c唐川，第3小队的探索进度我看了，做得不错。\u201d',
                gm_name + '的语气比平时多了一丝温度：\u201c报告。\u201d',
            ]))
        else:
            lines.append(rng.choice([
                'GM的回复一如既往地公事公办：\u201c请提交你的报告。\u201d',
                gm_name + '在线。\u201d简短的回复从对话框里弹出。',
            ]))

        # 玩家回应
        if player_knows:
            lines.append(rng.choice([
                player_name + '看着那行冰冷的文字，深吸一口气：\u201c林朔……我已经知道了。这不是游戏。\u201d',
                player_name + '犹豫了一下：\u201c你说的那个碎片……是不是和我们的世界也有关？\u201d',
            ]))
        elif char_states.get(player_name, {}).get('relations', {}).get(gm_name, '') and \
             '崇拜' in char_states[player_name]['relations'].get(gm_name, ''):
            lines.append(rng.choice([
                player_name + '兴奋地打字：\u201cGM大大！我发现了一个隐藏区域！是不是彩蛋？\u201d',
                player_name + '秒回：\u201c收到！不过我能问个问题吗……你真的是AI吗？\u201d',
            ]))
        else:
            lines.append(rng.choice([
                player_name + '快速打字：\u201c报告GM，武侠世界第三区域探索完成。有异常能量波动。\u201d',
                player_name + '：\u201cGM，我有个想法——这个世界的地图是无限的？\u201d',
            ]))

        # 林朔的回应
        if gm_emotion == '警觉' and '碎片' in context.get('topic', ''):
            lines.append(gm_name + '顿了顿：\u201c那个波动……不是bug。你遇到的东西，可能很危险。建议标记坐标后撤离。\u201d')
        elif not self._ps.get_plot_flag('first_fragment_recovered'):
            lines.append(gm_name + '：\u201c异常波动是正常现象。继续探索，但要遵守协议第三条——不要单独行动。\u201d')
        else:
            lines.append(gm_name + '：\u201c探索数据已记录。下一个目标坐标已发送到你的面板。保持警惕——这个世界的规则不如表面看起来简单。\u201d')

        # 收束
        if gm_emotion in ('疲惫', '警觉'):
            lines.append(gm_name + '的对话框暗了下去。但他没有离开——他看着' + player_name + '的ID，犹豫了一秒。\n然后他关掉了私聊。')
        else:
            lines.append(gm_name + '发送了新的坐标后，头像变灰。\n' + player_name + '看着那个坐标，心里涌起一种奇怪的感觉——好像GM的每句话后面，都藏着另一个人。')

        return '\n'.join(lines)

    # ======================== 玩家之间对话 ========================
    def _gen_player_interaction(self, participants, char_states, context):
        rng = self._rng
        p1 = participants[0] if participants else '唐川'
        p2 = participants[1] if len(participants) > 1 else '路人玩家'
        truth_revealed = self._ps.get_plot_flag('tangchuan_truth_revealed')
        organized = self._ps.state['characters']['玩家群体'].get('organized_level', 10)

        if truth_revealed:
            return rng.choice([
                p1 + '停下了手里的操作：\u201c' + p2 + '……你有没有觉得，那些NPC的眼神，太真实了？\u201d\n' +
                p2 + '沉默了很久才打字：\u201c我查过了。那个叫叶琳的姑娘……她的任务线不是程序写的。她是活的。\u201d',
                p1 + '苦笑：\u201c所以我们现在怎么办？继续当玩家？还是……\u201d\n' +
                p2 + '：\u201c我不知道。但我知道一件事——如果我们不回收碎片，归墟会崩塌。所有人都会死。包括这些……活着的人。\u201d',
            ])
        elif organized > 50:
            return rng.choice([
                p1 + '在公会频道发了一张地图截图：\u201c标记红圈的位置，碎片能量最强。但守护怪是Lv.45的。\u201d\n' +
                p2 + '：\u201c需要多少战力？\u201d\n' + p1 + '：\u201c至少两个精英小队。让3队从侧翼吸引火力，主力正面突破。\u201d',
                p2 + '：\u201c会长，那个叫叶琳的NPC今天又来找你了。\u201d\n' +
                p1 + '顿了顿：\u201c她不是NPC。至少……不像。\u201d\n' + p2 + '：\u201c？？？会长你怎么了\u201d',
            ])
        else:
            return rng.choice([
                p1 + '在公会频道发了一串表情：\u201c兄弟们！！我发现了一个bug！！\u201d\n' +
                p2 + '：\u201c什么bug？？\u201d\n' +
                p1 + '：\u201c这个游戏的NPC会记仇！！我上次偷了她的药草，今天再去接任务她直接把我赶出来了！！\u201d\n' +
                p2 + '：\u201c哈哈哈哈活该\u201d',
                p1 + '：\u201c有人知道怎么触发隐藏任务吗？我在地图边界发现了一个发光的石碑。\u201d\n' +
                p2 + '：\u201c发坐标！我来看看！\u201d\n' +
                p1 + '：\u201c（坐标）就这里，上面有看不懂的文字。但我的面板显示源能反应：中。\u201d\n' +
                p2 + '：\u201c源能……又是这个词。这游戏的世界观到底有多深啊\u201d',
            ])

    # ======================== NPC遭遇 ========================
    def _gen_npc_encounter(self, participants, char_states, context):
        npc_name = participants[0] if participants else '叶琳'
        other_name = participants[1] if len(participants) > 1 else '林朔'
        corruption = self._ps.get_char_state('叶琳', 'corruption_level') or 0

        if npc_name == '叶琳':
            if corruption > 50:
                lines = [
                    '叶琳的手一直按在剑柄上，指节泛白。',
                    '\u201c' + other_name + '……\u201d她的声音比上次见面时沙哑了很多，\u201c这把剑……在跟我说话。它说，只要我接受它的力量，就能报苍云派的仇。\u201d',
                    '她抬起头，眼眶发红：\u201c我该信它吗？\u201d',
                ]
            elif corruption > 20:
                lines = [
                    '叶琳正在练剑。' + other_name + '走近时，她刚好收招。',
                    '\u201c你来了。\u201d她没有回头，\u201c那些天人……真的是来帮我们的吗？\u201d',
                    '她转过身，眼中有一种不属于她这个年纪的疲惫：\u201c他们说苍云派只是一个副本。副本是什么意思？\u201d',
                ]
            else:
                lines = [
                    '叶琳看到' + other_name + '，眼睛一亮：\u201c前辈！\u201d',
                    '她从怀中掏出一个小布包：\u201c这是我们苍云派的疗伤药。虽然比不上天人的丹药，但……请你收下。\u201d',
                ]
        elif npc_name == '白夜':
            truth = self._ps.state['truth_layer']
            lines = ['白夜的残影在混沌海中凝聚。他的左眼——那个机械义眼——闪烁着幽蓝的光。']
            if truth <= 2:
                lines.append('\u201c你在浪费时间，锚定者。\u201d他的声音像从很远处传来，\u201c回收碎片只是治标。祂们在等你耗尽源能。\u201d')
            elif truth <= 3:
                lines.append('\u201c第47次。\u201d白夜盯着林朔，\u201c我数过。47次循环，47个锚定者。全都失败了。你觉得你特殊？\u201d')
            else:
                lines.append('白夜沉默了很长时间。然后他说了一句让林朔脊背发凉的话：\n\u201c你有没有想过——你记忆中的那个林朔，可能从来就不存在？\u201d')
        else:
            # 其他具名角色（林朔/墟核等）作为对话发起方时的通用 NPC 遭遇分支
            lines = [
                npc_name + '看向' + other_name + '，像是在斟酌从何说起。',
                '\u201c' + other_name + '，\u201d' + npc_name + '的声音很稳，\u201c有些事，我想你现在该知道了。\u201d',
            ]

        return '\n'.join(lines)

    # ======================== 揭示场景 ========================
    def _gen_revelation(self, participants, char_states, context):
        receiver = participants[1] if len(participants) > 1 else '林朔'
        truth_layer = self._ps.state['truth_layer']
        lines = []

        if truth_layer == 1:
            lines.append('墟核的面板上跳出了一行林朔从未见过的文字：')
            lines.append('\u201c锚定者日志·档案封存。日期：源纪元·终末。\u201d')
        elif truth_layer == 2:
            lines.append('墟核投影出一张星图。图上标记着十二个闪烁的光点——每个光点旁都标注着一个世界名。')
            lines.append('而在星图最中央，归墟的坐标上，写着两个字：\u201c前哨站\u201d。')
            lines.append(receiver + '的手指停在了半空中。\u201c前哨站？\u201d他喃喃道，\u201c归墟……只是一个观测点？\u201d')
        elif truth_layer == 3:
            lines.append('墟核的蓝光变成了红色——这是它第一次改变颜色。')
            lines.append('\u201c锚定者，我现在可以告诉你部分真相。\u201d墟核的文字闪现，\u201c万界体系不是自然形成的。它是源为测试文明可能性而设计的实验场。\u201d')
            lines.append('\u201c包括你回收的碎片——每一片都记录了源对文明演化的设计参数。\u201d')
        else:
            lines.append('墟核沉默了——这是它第一次从面板上消失。')
            lines.append('过了很久，一行字缓缓浮现：')
            lines.append('\u201c锚定者林朔。你在第' + str(self._ps.state['current_chapter']) + '章发现的壁画刻痕\n——第四十七次，还是失败——\n是我在上一轮循环后留下的日志。\u201d')

        return '\n'.join(lines)

    # ======================== 冲突场景 ========================
    def _gen_conflict(self, participants, char_states, context):
        source = context.get('conflict_source', '代理人')
        if source == '代理人':
            lines = [
                '混沌海裂开了一道口子。',
                '从裂缝中走出来的东西，看起来像人，但它的影子不跟着它走——影子留在了裂缝的另一边。',
                '\u201c锚定者。\u201d它的声音没有感情，\u201c源界碎片不属于你。交出来。\u201d',
                '林朔的墟核面板上弹出一行红色警告：',
                '「检测到非源界实体。威胁等级：未知。」',
                '「建议：立即撤离。」',
            ]
        elif source == '魔剑':
            lines = [
                '叶琳的惨叫声从苍云山深处传来。',
                '魔剑已经悬浮在她面前，剑身上的古代铭文发出令人作呕的紫光。',
                '那些文字在蠕动——不是刻上去的，是活的。',
            ]
        else:
            lines = [
                '对峙的两人之间，空气几乎凝固了。',
                '谁都没有先动手，但谁都清楚——这一架，躲不掉。',
            ]
        return '\n'.join(lines)

    def _gen_generic(self, participants, char_states, context):
        rng = self._rng
        p1 = participants[0] if participants else 'A'
        p2 = participants[1] if len(participants) > 1 else 'B'
        return rng.choice([
            p1 + '看着' + p2 + '，没有说话。有些话不需要说出口。',
            p2 + '打破了沉默：\u201c我知道你想问什么。答案——我没有。\u201d',
        ])
