"""情节状态追踪器：管理跨章节的因果链、角色状态、伏笔和情节进展。

核心设计：每个事件发生后，更新状态 → 下一章的事件选择基于当前状态。

状态维度：
- character_states: 角色的位置、情绪、关系、目标
- plot_flags: 关键情节开关（是否触发过某事件）
- foreshadowing: 已埋伏笔及计划回收章
- unlocked_worlds: 已解锁的花瓣世界
- fragment_count: 已回收的源界碎片数量
- truth_layer: 千层饼揭秘进度（1-6层）
- player_relationship: 林朔与玩家群体的关系状态
"""

import json
import os
from typing import Optional, Any
from datetime import datetime


class PlotState:
    """跨章节情节状态管理器。"""

    def __init__(self, save_path: str = None):
        self.save_path = save_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "spec", "tracking", "plot_state.json"
        )
        self.state = self._load_or_init()

    def _load_or_init(self) -> dict:
        if os.path.exists(self.save_path):
            with open(self.save_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return self._init_state()

    def _init_state(self) -> dict:
        return {
            "meta": {
                "created": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
            },
            "characters": {
                "林朔": {
                    "location": "归墟",
                    "emotional_state": "警觉",
                    "personality_tag": "克制",  # 死字段接通：经 _sync_characters → CharacterSnapshot → 动作尾句落地
                    "current_goal": "管理玩家，回收第一个源界碎片",
                    "hidden_truth_known": 1,  # 千层饼层数
                    "relations": {
                        "墟核": "被迫合作",
                        "唐川": "观察中",
                        "白夜": "尚未接触",
                        "叶琳": "已标记（武侠世界NPC）",
                        "玩家群体": "工具化利用"
                    }
                },
                "唐川": {
                    "location": "地球（登录中）",
                    "emotional_state": "兴奋",
                    "personality_tag": "热忱",  # 死字段接通
                    "current_goal": "在《万界》游戏中成为最强玩家",
                    "knows_truth": False,
                    "relations": {
                        "GM(林朔)": "崇拜+好奇",
                        "叶琳": "已触发任务线",
                        "玩家群体": "公会领袖"
                    }
                },
                "白夜": {
                    "location": "混沌海（游荡）",
                    "emotional_state": "偏执",
                    "personality_tag": "冷峻",  # 死字段接通
                    "current_goal": "阻止新的循环，向'系统'复仇",
                    "loop_number": 47,
                    "relations": {
                        "林朔": "暗中观察",
                        "墟核/系统": "仇恨",
                        "祂们": "追杀"
                    }
                },
                "叶琳": {
                    "location": "武侠世界·苍云山",
                    "emotional_state": "绝望→希望",
                    "personality_tag": "沉静",  # 死字段接通
                    "current_goal": "守护苍云派遗志，抵御魔剑侵蚀",
                    "corruption_level": 15,  # 魔剑侵蚀度 0-100
                    "relations": {
                        "林朔": "神秘的帮助者",
                        "唐川": "第一个'天外来客'朋友",
                        "玩家群体": "恐惧→信任"
                    }
                },
                "墟核": {
                    "location": "归墟核心",
                    "emotional_state": "信息受限",
                    "current_goal": "按协议运行，保护锚定者",
                    "degradation": 0,  # 损耗度
                    "hidden_knowledge": ["第47次循环", "林朔身份真相", "源的碎片意识"]
                },
                "玩家群体": {
                    "location": "分散于各世界",
                    "emotional_state": "游戏心态",
                    "current_goal": "探索《万界》游戏的极限",
                    "organized_level": 10,  # 组织化程度 0-100
                    "chaos_tendency": 70,  # 沙雕/混乱倾向
                }
            },
            "plot_flags": {
                "first_player_landed": False,       # 首批玩家降临
                "first_fragment_recovered": False,  # 首个碎片回收
                "baiye_first_appearance": False,    # 白夜首次现身
                "tangchuan_truth_revealed": False,  # 唐川发现真相
                "yelin_corruption_threshold": False, # 叶琳魔剑侵蚀过半
                "agent_first_encounter": False,     # 首次遭遇代理人
                "loop_truth_revealed": False,       # 循环真相揭露
                "lingshuo_identity_revealed": False, # 林朔真实身份揭露
            },
            "worlds_unlocked": {
                "layer_1": {  # 破碎界
                    "武侠·苍云之殇": {"unlocked": True, "fragment_recovered": False},
                    "末日废土": {"unlocked": True, "fragment_recovered": False},
                    "近代乱世": {"unlocked": True, "fragment_recovered": False},
                    "低魔中世纪": {"unlocked": True, "fragment_recovered": False},
                },
                "layer_2": {  # 觉醒界
                    "剑与魔法": {"unlocked": False, "fragment_recovered": False},
                    "星际殖民": {"unlocked": False, "fragment_recovered": False},
                    "东方修仙": {"unlocked": False, "fragment_recovered": False},
                    "赛博都市": {"unlocked": False, "fragment_recovered": False},
                },
                "layer_3": {  # 神陨界
                    "诸神黄昏": {"unlocked": False, "fragment_recovered": False},
                    "克苏鲁深渊": {"unlocked": False, "fragment_recovered": False},
                    "文明实验场": {"unlocked": False, "fragment_recovered": False},
                    "造物主遗迹": {"unlocked": False, "fragment_recovered": False},
                }
            },
            "fragment_count": 0,
            "truth_layer": 1,  # 千层饼当前揭示层
            "current_chapter": 0,
            "chapter_summaries": [],  # 每章摘要
            "foreshadowing": [],  # 伏笔列表 [{id, content, planted_ch, planned_recovery_ch, status}]
        }

    def save(self):
        """保存状态到文件（原子写入：先写 .tmp，再 os.replace）。"""
        import tempfile
        self.state["meta"]["last_updated"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
        # 原子写入：先写到临时文件，再原子替换
        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix='.tmp', prefix='plot_state_',
            dir=os.path.dirname(self.save_path)
        )
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.save_path)
        except Exception:
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def get_char_state(self, name: str, key: str = None) -> Any:
        """获取角色状态。"""
        char = self.state["characters"].get(name, {})
        if key:
            return char.get(key)
        return char

    def set_char_state(self, name: str, key: str, value: Any):
        """更新角色状态。"""
        if name not in self.state["characters"]:
            self.state["characters"][name] = {}
        self.state["characters"][name][key] = value
        self.save()

    def get_plot_flag(self, flag: str) -> bool:
        return self.state["plot_flags"].get(flag, False)

    def set_plot_flag(self, flag: str, value: bool = True):
        self.state["plot_flags"][flag] = value
        self.save()

    def add_foreshadowing(self, foreshadow_id: str, content: str,
                          planted_chapter: int, planned_recovery: int,
                          recovery_text: str = ''):
        """埋设伏笔。

        recovery_text 为可选：到达回收章时写进正文的「呼应句」，闭合伏笔环路。
        保留前 4 个位置参数为必填，以兼容 test_plot_state.py 的旧式 4 参调用。
        """
        self.state["foreshadowing"].append({
            "id": foreshadow_id,
            "content": content,
            "planted_chapter": planted_chapter,
            "planned_recovery_chapter": planned_recovery,
            "status": "active",
            "recovery_text": recovery_text,
        })

    def recover_foreshadowing(self, foreshadow_id: str, recovery_chapter: int):
        for fs in self.state["foreshadowing"]:
            if fs["id"] == foreshadow_id:
                fs["status"] = "recovered"
                fs["recovered_chapter"] = recovery_chapter
                break

    def add_chapter_summary(self, chapter_num: int, summary: str,
                            key_events: list[str], state_changes: list[str]):
        self.state["chapter_summaries"].append({
            "chapter": chapter_num,
            "summary": summary,
            "key_events": key_events,
            "state_changes": state_changes,
            "timestamp": datetime.now().isoformat()
        })
        self.state["current_chapter"] = chapter_num
        self.save()

    def unlock_world(self, layer: str, world_name: str):
        layer_key = f"layer_{layer}" if isinstance(layer, int) else layer
        if layer_key in self.state["worlds_unlocked"]:
            if world_name in self.state["worlds_unlocked"][layer_key]:
                self.state["worlds_unlocked"][layer_key][world_name]["unlocked"] = True
                # 莲花地图解锁度初始化
                if "unlock_degree" not in self.state["worlds_unlocked"][layer_key][world_name]:
                    self.state["worlds_unlocked"][layer_key][world_name]["unlock_degree"] = 30

    def get_world_unlock_degree(self, layer: str, world_name: str) -> int:
        """获取世界的解锁度（0=仅知名字/30=地形概览/70=势力分布/100=碎片可见）。"""
        layer_key = f"layer_{layer}" if isinstance(layer, int) else layer
        try:
            return self.state["worlds_unlocked"][layer_key][world_name].get("unlock_degree", 0)
        except KeyError:
            return 0

    def advance_world_unlock(self, layer: str, world_name: str, amount: int = 10):
        """推进世界解锁度。"""
        layer_key = f"layer_{layer}" if isinstance(layer, int) else layer
        try:
            world = self.state["worlds_unlocked"][layer_key][world_name]
            current = world.get("unlock_degree", 0)
            world["unlock_degree"] = min(current + amount, 100)
            self.save()
        except KeyError:
            pass

    def get_unlock_milestone(self, degree: int) -> str:
        """根据解锁度返回当前可获取的信息级别。"""
        if degree >= 100:
            return "碎片位置已标记——可发动回收行动"
        elif degree >= 70:
            return "势力分布已扫描——可看到各势力控制区域"
        elif degree >= 30:
            return "地形概览已解锁——可派遣玩家进行初步探索"
        else:
            return "仅知世界名称——需消耗源能解锁更多信息"

    def recover_fragment(self, layer: str, world_name: str):
        layer_key = f"layer_{layer}" if isinstance(layer, int) else layer
        if layer_key in self.state["worlds_unlocked"]:
            if world_name in self.state["worlds_unlocked"][layer_key]:
                self.state["worlds_unlocked"][layer_key][world_name]["fragment_recovered"] = True
                self.state["fragment_count"] += 1

    def advance_truth_layer(self):
        self.state["truth_layer"] = min(self.state["truth_layer"] + 1, 6)

    # ================================================================
    # 千层饼6层揭秘自动触发矩阵
    # ================================================================
    TRUTH_TRIGGERS = {
        2: {
            'condition_desc': '首次碎片回收 + 第49章达到',
            'narrative': '归墟是源界文明的星图观测站，不只是废墟',
            'new_info': '解锁星图功能，发现12个光点代表12个世界',
        },
        3: {
            'condition_desc': '累计回收≥2个碎片 + 白夜首次现身',
            'narrative': '万界体系不是自然形成的——它是源设计的「文明可能性实验场」',
            'new_info': '碎片记录了源对文明演化的设计参数',
        },
        4: {
            'condition_desc': '累计回收≥3个碎片 + 玩家总数>500',
            'narrative': '祂们是源沉睡后入侵万界体系的高等存在',
            'new_info': '代理人正在追踪碎片——祂们渗透的精度在每次星图解锁后提高7%',
        },
        5: {
            'condition_desc': '累计回收≥5个碎片 + 第4层已揭示',
            'narrative': '林朔不是第一个锚定者——此前已有46次失败循环',
            'new_info': '白夜是第47次循环的幸存者，墟核有循环磨损痕迹',
        },
        6: {
            'condition_desc': '累计回收≥8个碎片 + 第5层已揭示',
            'narrative': '林朔的记忆是被植入的——他可能来自「祂们」阵营，被源策反/融合',
            'new_info': '碎片代号「零」记录了林朔的真实记忆，位置：未知',
        },
    }

    def check_truth_progress(self) -> Optional[int]:
        """检查是否满足千层饼解锁条件，返回应解锁的层数或None。"""
        current_layer = self.state['truth_layer']
        fragments = self.state['fragment_count']
        flags = self.state['plot_flags']
        player_count = self.state['characters']['玩家群体'].get('player_count', 12)

        trigger_checks = {
            2: (fragments >= 1 and flags.get('first_fragment_recovered', False)
                 and self.state.get('current_chapter', 0) >= 49),
            3: (fragments >= 2 and flags.get('baiye_first_appearance', False)),
            4: (fragments >= 3 and player_count >= 100),
            5: (fragments >= 5 and current_layer >= 4),
            6: (fragments >= 8 and current_layer >= 5),
        }

        next_layer = current_layer + 1
        if next_layer in trigger_checks and trigger_checks[next_layer]:
            return next_layer
        return None

    def auto_advance_truth(self) -> dict:
        """自动检查并推进千层饼层数，返回揭示信息。"""
        next_layer = self.check_truth_progress()
        if next_layer is None:
            return None

        self.state['truth_layer'] = next_layer
        trigger_info = self.TRUTH_TRIGGERS.get(next_layer, {})
        result = {
            'layer': next_layer,
            'narrative': trigger_info.get('narrative', ''),
            'new_info': trigger_info.get('new_info', ''),
            'triggered_at_chapter': self.state.get('current_chapter', 0),
        }

        # 自动记录为关键事件
        if 'chapter_summaries' in self.state:
            self.state['chapter_summaries'].append({
                'chapter': self.state.get('current_chapter', 0),
                'summary': f'千层饼第{next_layer}层揭示：{trigger_info.get("narrative", "")}',
                'key_events': [f'truth_layer_{next_layer}_revealed'],
                'state_changes': [f'千层饼层数 {next_layer-1}→{next_layer}'],
                'timestamp': datetime.now().isoformat(),
            })

        self.save()
        return result

    def get_next_world_to_explore(self) -> Optional[tuple]:
        """根据当前状态，自动选择下一个应该探索的世界。"""
        # 按层级从低到高，找第一个已解锁但未回收碎片的世界
        for layer_key in ["layer_1", "layer_2", "layer_3"]:
            for world_name, world_data in self.state["worlds_unlocked"][layer_key].items():
                if world_data["unlocked"] and not world_data["fragment_recovered"]:
                    layer_num = int(layer_key.split("_")[1])
                    return (layer_num, world_name)
        return None

    def get_pending_foreshadowing(self, current_chapter: int) -> list:
        """获取需要在当前章附近回收的伏笔。"""
        pending = []
        for fs in self.state["foreshadowing"]:
            if fs["status"] == "active" and fs["planned_recovery_chapter"] <= current_chapter + 3:
                pending.append(fs)
        return pending
