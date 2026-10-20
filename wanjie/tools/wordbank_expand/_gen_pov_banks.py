# -*- coding: utf-8 -*-
"""一次性生成 7 个 POV 内容/配置词库到 word_banks/narrative/。

config 类（event_spine / pov_assignment / pov_timeline）逐字搬运现有引擎硬编码
字面量，保证 Phase 2 解耦后行为可等价还原；catalog 类（pov_types / pov_lenses /
interiority / info_asymmetry）为手写有意义中文内容。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
NB = os.path.abspath(os.path.join(HERE, "..", "..", "word_banks", "narrative"))


def dump(name, data):
    p = os.path.join(NB, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("wrote", name, os.path.getsize(p), "bytes")


# 1) pov_types.json —— 视角类型目录（catalog，手写）
pov_types = {
    "first_person": {
        "name": "第一人称",
        "desc": "以'我'的视角叙述，读者直接进入角色感官与思想。",
        "markers": ["我感觉到…", "我以为…", "我记得…"],
        "suited": ["强代入感的个人叙事", "心理悬疑", "成长线"],
        "pitfalls": ["信息天然受限，需另设渠道透露全局", "易显主观片面"],
    },
    "third_limited": {
        "name": "第三人称限知",
        "desc": "跟随单一角色，仅呈现其所见所感，但不使用'我'。",
        "markers": ["他看不见那件事", "她只听到一半"],
        "suited": ["商业小说主流", "悬疑/推理", "避免全知说教"],
        "pitfalls": ["换视角需明确分隔，否则失焦"],
    },
    "omniscient": {
        "name": "第三人称全知",
        "desc": "作者上帝视角，可同时呈现多角色内心与全局信息。",
        "markers": ["无人知晓的是…", "命运在此刻岔开"],
        "suited": ["宏大史诗", "多线群像", "交代背景"],
        "pitfalls": ["易破坏代入感与悬念", "需克制使用"],
    },
    "second_person": {
        "name": "第二人称",
        "desc": "以'你'直接指称读者/角色，制造被卷入感。",
        "markers": ["你睁开眼", "你以为这是终点"],
        "suited": ["互动叙事", "实验文学", "沉浸恐怖"],
        "pitfalls": ["易显刻意", "长篇难以为继"],
    },
    "unreliable": {
        "name": "不可靠叙述者",
        "desc": "叙述者认知/立场有偏，读者需自行辨伪。",
        "markers": ["他当然不会承认…", "我记得很清楚——也许记错了"],
        "suited": ["悬疑反转", "心理惊悚", "讽刺"],
        "pitfalls": ["需埋设可被证伪的破绽"],
    },
    "deep_pov": {
        "name": "深层POV",
        "desc": "完全贴附角色感官与当下意识，过滤作者旁白。",
        "markers": ["世界在他眼里缩减成…", "念头比呼吸先到"],
        "suited": ["情感强度", "动作场面", "亲密关系"],
        "pitfalls": ["需剔除'他想到/他感到'式总结"],
    },
    "objective_data": {
        "name": "客观数据视角",
        "desc": "以系统/日志/档案口吻呈现，剥离情绪。",
        "markers": ["[记录]能量曲线上升12%", "协议条款第47条"],
        "suited": ["科幻设定", "非人实体", "冷峻反差"],
        "pitfalls": ["需与人物视角对照才有张力"],
    },
}
dump("pov_types.json", pov_types)


# 2) pov_lenses.json —— 视角透镜（按角色/属性，通用化 POV_INFO_LENS）
pov_lenses = {
    "by_role": {
        "protagonist": {
            "style": "冷叙事——焦虑与计算并存",
            "adds": "主角知道但读者不知的铺垫，为后续反转蓄力",
            "header": "【{pov}视角】",
            "footer": "{adds}",
        },
        "player_proxy": {
            "style": "热叙事——即时情绪、身体反应、现场细节",
            "adds": "第一手感官信息与现场混乱感",
            "header": "【{pov}视角·现场】",
            "footer": "{adds}",
        },
        "observer": {
            "style": "冷叙事+历史纵深——见过太多循环的麻木",
            "adds": "时间/记忆维度的信息，'第N次了，每次都一样'",
            "header": "【{pov}视角·残影】",
            "footer": "{adds}",
        },
        "bystander": {
            "style": "体感叙事——疼痛、温度、听不清的对话",
            "adds": "被卷入者的无知视角，不知自己面对什么",
            "header": "【{pov}视角】",
            "footer": "{adds}",
        },
        "system": {
            "style": "数据叙事——纯面板日志格式",
            "adds": "冰冷系统数据：能量曲线/同化率/协议条款",
            "header": "【{pov}日志·内部记录】",
            "footer": "{adds}",
        },
    },
    "by_personality": {
        "冷峻": {"style": "克制白描", "adds": "少评语，多事实", "header": "【{pov}·冷眼】", "footer": "{adds}"},
        "热忱": {"style": "情感外放", "adds": "带温度的主观判断", "header": "【{pov}·炽】", "footer": "{adds}"},
        "阴鸷": {"style": "压抑暗流", "adds": "话里有话的威胁感", "header": "【{pov}·暗】", "footer": "{adds}"},
    },
}
dump("pov_lenses.json", pov_lenses)


# 3) interiority.json —— 内省/心理活动（catalog，手写；{pov}/{line} 供引擎填槽）
interiority = {
    "soliloquy": [
        "{pov}在心里对自己说：{line}",
        "如果当时…{pov}把这句话咽了回去。",
        "{pov}忽然不确定了——{line}",
        "他在脑中把刚才的事重放了一遍，每一帧都更冷。",
        "{pov}没有说出来，但那个念头已经生根。",
    ],
    "sensory_introspection": [
        "指尖传来的温度，比任何解释都真实。",
        "耳鸣里，{pov}听见了自己加速的心跳。",
        "光在视网膜上停留的时间，比预想的长。",
        "血的味道先一步到达——然后是痛。",
        "沉默比喊叫更重，压在{pov}的胸口。",
    ],
    "emotion_flow": [
        "怒意来得没有道理，却正确得可怕。",
        "一种说不清的怅然，像退潮后的沙滩。",
        "恐惧不是尖叫，是安静地收紧。",
        "喜悦在抵达之前就被警惕截断了。",
        "{pov}分不清那是释然，还是更深的疲惫。",
    ],
}
dump("interiority.json", interiority)


# 4) info_asymmetry.json —— 同事件多立场/认知差（catalog，手写）
info_asymmetry = {
    "same_event_stances": [
        {
            "event_anchor": "碎片争夺战",
            "stances": [
                {"role": "protagonist", "reading": "这是必须回收的遗物。"},
                {"role": "observer", "reading": "第47次了，每次都一样。"},
                {"role": "bystander", "reading": "他们到底在抢什么？"},
            ],
        },
        {
            "event_anchor": "协议揭晓",
            "stances": [
                {"role": "protagonist", "reading": "代价是我的存在。"},
                {"role": "player_proxy", "reading": "条款还有另一面。"},
                {"role": "system", "reading": "同化进度67%，协议锁定。"},
            ],
        },
        {
            "event_anchor": "真相降临",
            "stances": [
                {"role": "protagonist", "reading": "一切都有了去向。"},
                {"role": "bystander", "reading": "原来我们一直在被观看。"},
                {"role": "system", "reading": "记录终止，理由：超出授权。"},
            ],
        },
    ],
    "cognitive_gap_hooks": [
        "他不知道的是，{hidden}",
        "读者比{pov}先看到{truth}",
        "同一句话，{a}听成承诺，{b}听成威胁",
        "{pov}以为结局已定，但{other}手里还有一步",
        "所有人都相信的，恰恰是那个谎言",
    ],
}
dump("info_asymmetry.json", info_asymmetry)


# 5) event_spine.json —— 事件脊梁（config，逐字搬运引擎硬编码字面量）
event_spine = {
    "timeline_events": [
        {"type": "world", "id": "unlock_wuxia", "name": "武侠世界解锁", "trigger_time": 1,
         "narrative_hint": "world_entry_small", "payload": {"world": "武侠·苍云之殇", "layer": 1},
         "condition": None, "repeatable": False, "cooldown": 0, "duration": 1},
        {"type": "world", "id": "unlock_wasteland", "name": "末日废土解锁", "trigger_time": 300,
         "narrative_hint": "world_entry_medium", "payload": {"world": "末日废土", "layer": 1},
         "condition": None, "repeatable": False, "cooldown": 0, "duration": 1},
        {"type": "world", "id": "unlock_cultivation", "name": "东方修仙世界解锁", "trigger_time": 800,
         "narrative_hint": "world_entry_large", "payload": {"world": "东方修仙", "layer": 2},
         "condition": None, "repeatable": False, "cooldown": 0, "duration": 1},
        {"type": "world", "id": "unlock_cyberpunk", "name": "赛博都市解锁", "trigger_time": 1500,
         "narrative_hint": "world_entry_medium", "payload": {"world": "赛博都市", "layer": 2},
         "condition": None, "repeatable": False, "cooldown": 0, "duration": 1},
        {"type": "world", "id": "unlock_ragnarok", "name": "诸神黄昏解锁", "trigger_time": 3000,
         "narrative_hint": "world_entry_epic", "payload": {"world": "诸神黄昏", "layer": 3},
         "condition": None, "repeatable": False, "cooldown": 0, "duration": 1},
        {"type": "region", "id": "danger_spike", "name": "危险区域遭遇", "trigger_time": 0,
         "narrative_hint": "danger_encounter", "payload": None,
         "condition": "danger>=7", "repeatable": False, "cooldown": 0, "duration": 1},
        {"type": "region", "id": "rare_find", "name": "隐藏路径发现", "trigger_time": 0,
         "narrative_hint": "discovery", "payload": {"discovery_type": "hidden_path"},
         "condition": "visited>=3&category==ruin", "repeatable": False, "cooldown": 0, "duration": 1},
        {"type": "region", "id": "faction_clash", "name": "势力冲突爆发", "trigger_time": 0,
         "narrative_hint": "battle_looming", "payload": None,
         "condition": "danger>=8&category==battlefield", "repeatable": False, "cooldown": 0, "duration": 3},
        {"type": "region", "id": "calm_moment", "name": "宁静时刻", "trigger_time": 0,
         "narrative_hint": "peaceful_interlude", "payload": None,
         "condition": "danger<=2&category==town", "repeatable": False, "cooldown": 0, "duration": 1},
        {"type": "world", "id": "agent_incursion", "name": "代理人渗透增强", "trigger_time": 2000,
         "narrative_hint": "agent_threat_rising", "payload": None,
         "condition": "unlocked_worlds>=3", "repeatable": True, "cooldown": 1000, "duration": 1},
        {"type": "world", "id": "source_fluctuation", "name": "源能波动", "trigger_time": 1500,
         "narrative_hint": "mystery_deepening", "payload": None,
         "condition": None, "repeatable": True, "cooldown": 800, "duration": 1},
    ],
    "convergence_points": [
        {
            "convergence_id": "conv_cangyun", "label": "苍云之殇汇聚",
            "line_ids": ["a_lin_shuo", "c_agents", "d_wuxia_cangyun"],
            "trigger_phase": "CONFLICT", "trigger_progress_min": 0.5,
            "shared_event_description": "苍云山第二块碎片的争夺战——林朔要回收碎片，白夜要阻止代理人，叶琳在两者之间",
            "world_name": "武侠·苍云之殇",
            "pov_sequence": ["林朔", "叶琳", "白夜"], "tension_boost": 4, "one_shot": True,
        },
        {
            "convergence_id": "conv_wasteland", "label": "废土抉择汇聚",
            "line_ids": ["a_lin_shuo", "b_tang_chuan", "c_agents"],
            "trigger_phase": "CHOICE", "trigger_progress_min": 0.6,
            "shared_event_description": "废土避难所——林朔面临锚定者协议的代价：继续锚定将消耗自身存在，不锚定则世界崩塌。唐川从玩家侧发现了协议的另一面。白夜带来了祂们的最后通牒。",
            "world_name": "末日废土",
            "pov_sequence": ["林朔", "唐川", "白夜"], "tension_boost": 5, "one_shot": True,
        },
        {
            "convergence_id": "conv_guixu_final", "label": "归墟终局汇聚",
            "line_ids": ["a_lin_shuo", "b_tang_chuan", "c_agents", "d_wuxia_cangyun"],
            "trigger_phase": "TRANSFORM", "trigger_progress_min": 0.7,
            "shared_event_description": "归墟中枢——墟核揭示了全部真相：46任锚定者、源界文明的逃逸、祂们的真正目的。每一个角色都站在了选择的十字路口。",
            "world_name": "归墟",
            "pov_sequence": ["林朔", "唐川", "白夜", "叶琳"], "tension_boost": 5, "one_shot": True,
        },
    ],
}
dump("event_spine.json", event_spine)


# 6) pov_assignment.json —— plot 角色→POV（config，逐字搬运 A/B/C 默认）
pov_assignment = {
    "plot_roles": {
        "a_plot": {"label": "主线·锚定", "line_id": "a_lin_shuo", "default_pov": "林朔", "pov_characters": ["林朔"],
                   "default_tone": "mysterious", "tension_baseline": 5, "priority": 5, "beat_interval": 1,
                   "can_intersect_with": ["b_tang_chuan", "c_agents"], "preferred_ops": ["scene", "action", "reveal"],
                   "narrative_themes": ["源界碎片", "锚定者", "千层饼真相", "世界解锁"]},
        "b_plot": {"label": "玩家觉醒", "line_id": "b_tang_chuan", "default_pov": "唐川", "pov_characters": ["唐川"],
                   "default_tone": "curious", "tension_baseline": 3, "priority": 3, "beat_interval": 3,
                   "can_intersect_with": ["a_lin_shuo", "d_npc_arc"], "preferred_ops": ["dialogue", "action", "text"],
                   "narrative_themes": ["真相发现", "社区组织", "虚拟vs真实", "玩家自主"]},
        "c_plot": {"label": "暗流涌动", "line_id": "c_agents", "default_pov": "白夜", "pov_characters": ["白夜"],
                   "default_tone": "dark", "tension_baseline": 6, "priority": 2, "beat_interval": 5,
                   "can_intersect_with": ["a_lin_shuo"], "preferred_ops": ["reveal", "battle", "text"],
                   "narrative_themes": ["代理人渗透", "祂们", "源能侵蚀", "循环真相"]},
    },
    "role_pool_by_attribute": {
        "personality_tag": {"冷峻": ["protagonist", "observer"], "热忱": ["player_proxy"],
                             "阴鸷": ["observer", "system"], "温柔": ["bystander"]},
        "knowledge_level": {"high": ["system", "observer"], "low": ["bystander", "player_proxy"]},
    },
}
dump("pov_assignment.json", pov_assignment)


# 7) pov_timeline.json —— 编排/防混乱规则（config，搬运引擎既有常量）
pov_timeline = {
    "convergence_defaults": {"trigger_phase": "CONFLICT", "trigger_progress_min": 0.5,
                             "tension_boost": 3, "one_shot": True},
    "anti_chaos": {
        "max_pov_switch_per_passage": 2,
        "min_arc_continuity": 0.3,
        "forbid_consecutive_same_pov": False,
        "note": "约束 StoryBoard 调度，避免视角失焦与情节断裂（百科所列 POV 坑）",
    },
    "arc_stage_thresholds": {
        "climax_avg_phase_idx": 3.5, "climax_avg_progress": 0.7,
        "converge_avg_phase_idx": 2.5, "rise_avg_phase_idx": 1.5,
        "fall_all_triggered_progress": 0.8,
    },
    "beat_intervals": {"a_plot": 1, "b_plot": 3, "c_plot": 5, "d_plot": 8},
}
dump("pov_timeline.json", pov_timeline)

print("\nPhase 1: 7 POV banks generated.")
