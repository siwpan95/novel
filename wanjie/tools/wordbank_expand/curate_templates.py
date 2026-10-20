#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量拆槽：把联网调研 + 各生成器硬编码拆成带 {slot} 槽位的模板骨架，并入 templates/ 词库。

与 template_miner.py 的关系：
  - template_miner.py 负责「联网捞原始候选 → _mined_raw.json」+ 种子模板。
  - 本脚本负责「拆槽」（把原始候选/硬编码转成带槽位模板）+ 补全各生成器槽位值池。

拆槽是 LLM 的判断活，本脚本内置一份人工提炼的 CURATED 模板（来自打斗七公式 /
快慢快节奏 / 辰东句式 / 场景描写时机 等联网调研），确定性落盘。
"""
import os
import json
from pathlib import Path

# 2026-09-23 去本地化：templates 词库目录改由本文件位置推导（原硬编码已不存在）
TPL_DIR = str(Path(__file__).resolve().parents[2] / "word_banks" / "templates")

# ---------------------------------------------------------------------------
# 批量拆槽产物：带 {slot} 槽位的模板骨架（人工提炼）
# ---------------------------------------------------------------------------
CURATED = {
    "battle_action": [
        # 快慢快 · 快：三句内切入
        "刀光闪过。{attacker}来不及思考，身体本能后仰。",
        "没有铺垫。{attacker}的{skill}在{num}息之内已经压到{defender}眼前。",
        "轰隆一声，天地失色。{attacker}的{weapon}已经{action}。",
        # 快慢快 · 慢：慢镜头聚焦
        "刀锋距喉咙只剩{num}寸。这个距离，躲不开了。{attacker}的瞳孔骤缩，时间仿佛被拉长。",
        "零点几秒。{attacker}只有一个选择。",
        # 快慢快 · 快：爆发收尾
        "{attacker}没躲，徒手抓住了刀锋。血从指缝飙出的同时，右拳已砸在{defender}喉结上。",
        "咔嚓。{defender}双眼凸出，缓缓跪倒。",
        # 辰东句式
        "虚空破碎，一道{color}身影踏出，周身{aura}，镇压{scope}。",
        "就在这关键时刻——{attacker}的{skill}悍然{action}，{scope}失色。",
        "这是……传说中的{thing}！",
        # 打斗七公式 · 环境互动
        "{attacker}脚尖在{terrain}上一点，借力跃起，{skill}自上而下{action}。",
        "利用{terrain}的地形，{attacker}身形忽左忽右，{skill}从最刁钻的角度{action}。",
        # 连击链
        "连环三击！第一击{action}，第二击封退路，第三击{action2}，一气呵成。",
        "{attacker}的{weapon}织出一张密不透风的网，招招抢攻，不留半分退路。",
    ],
    "battle_reaction": [
        "{defender}不退反进，{def_skill}迎面而上，两股力量轰然相撞。",
        "{defender}瞳孔骤缩——{moment}之间，他只有一个选择。",
        "{defender}似乎早看穿了{skill}的破绽，只是微微侧头，{weapon}贴耳擦过。",
        "{defender}忽然闭眼，不是放弃，是以耳代目，仅凭风声判断{attacker}的方位。",
        "{defender}一脚跺在{terrain}上，{debris}遮住视线的一瞬，{def_skill}已经{action}。",
        "{defender}避无可避，却双手交叉护在胸前，硬吃了这一记{skill}，骨骼{shake}。",
        "{defender}的应对漂亮得不像临时反应，仿佛等这一记{skill}等了很久。",
        "{defender}面色微变，急使{def_skill}，堪堪{verb}住这致命一击。",
        "{defender}早有防备，{treasure}光华一闪，竟将那{thing}尽数{verb}。",
    ],
    "battle_effect": [
        "两股力量相撞之处，爆发出{color}光芒，整片{terrain}都被震得{shake}。",
        "没有爆炸，没有巨响。越安静的对撞越凶险。",
        "碰撞的中心安静了{moment}，冲击波才{belated}地扩散开。",
        "轰然巨响中，{defender}被震退{num}步，脸上露出{expression}之色。",
        "烟雾散去，{terrain}已面目全非，{attacker}却连看都没看一眼。",
        "这一招余波所及，{terrain}上的{thing}纷纷{verb}，景象{adj}至极。",
        "两股力量僵持了{num}息，终于轰然炸开，{thing}四散飞溅。",
    ],
    "scene_frame": [
        "踏入{landmark}，眼前豁然开朗。{visual}。",
        "{weather}压城，{crowd}。空气里{ambient}。",
        "首次进入{world}，{visual}先于一切建立印象。",
        "这里{visual}，{auditory}，像谁把{world}最{adj}的一面都堆在了这一处。",
        "越往里走，{ambient}越浓，{auditory}隐隐约约，分不清是风声还是别的什么。",
        # 恐怖氛围
        "深处，阴风阵阵。四周漆黑，只有{visual}勉强照亮三米范围。{auditory}。",
        "石壁上爬满青苔，散发着一股{ambient}的气息。",
    ],
    "character_intro": [
        "{modifier}破碎，一道身影缓缓走出，周身{aura}，镇压{scope}。",
        "「{name}，你终于来了。」声音平淡，却如惊雷炸响在每个人心头。",
        "{name}站在那里，{aura}，{visual}，像一柄出鞘的剑。",
        "没人看清{name}是怎么出现的。等众人回过神来，{name}已经在场中了。",
        "{name}的出场没有半点花哨，却让全场安静了半息。",
        "{name}一步一步走来，每一步都像踩在{scope}的心跳上。",
    ],
    "emotion_beat": [
        "{char}眼中燃烧着不甘的火焰，{body_reaction}。",
        "{char}没有说话，只是{body_reaction}，攥紧了拳。",
        "{char}深吸一口气，把{expression}压回眼底。",
        "这一瞬，{char}什么都听不见了，只剩{body_reaction}。",
        "{char}的指尖在发抖，{body_reaction}，{expression}。",
        "「都是我的错……」{char}的声音低到几乎听不见。",
    ],
    "dialogue_exchange": [
        {"a": '"{name_a}，你这是什么{skill}？好生厉害！"', "b": '"{name_b}，{expression}。我这招{skill_name}不过才练了{num}年。你刚才那招{skill2_name}，才真是{adj}至极！"'},
        {"a": '"看来{name_b}的{weapon}果然名不虚传。"', "b": '"{name_a}过奖了。倒是你的{treasure}，让人{verb}不已。"'},
        {"a": '"这一战的胜负，还难说得很呢！"', "b": '"{name_a}，你果然是个值得{verb}的对手。再来！"'},
        {"a": '"小心了！这招{skill_name}，我还从未对人用过！"', "b": '"{name_b}，{expression}。那我也只好全力以赴了！"'},
        {"a": '"{name_b}兄，你我今日在此相遇，也是缘分。不如{action}？"', "b": '"{name_a}说得好！那就让这{terrain}，见证你我这一战吧！"'},
        {"a": '"哼！你只知道{skill_name}的厉害，却不知道它的弱点！"', "b": '"{name_a}，{expression}。那就请赐教吧！"'},
        {"a": '"好！好！好！能遇到{name_b}这样的对手，不枉此行！"', "b": '"{name_a}，你的{weapon}也不差。只是，你还差了一点点……"'},
        {"a": '"三十年河东，三十年河西——"', "b": '"{name_a}，{expression}。话别说得太满。"'},
        {"a": '"你师父没教过你，出手前先报上名来吗？"', "b": '"{name_b}，{expression}。我的名字，你还不配知道。"'},
    ],
}

# 各生成器的槽位值池（从硬编码拆出）
SLOTS = {
    "dialogue_slots": {
        "skill": ["武功", "法术", "绝技", "秘技", "杀招"],
        "expression": ["脸色一变", "微微一笑", "神情严肃", "眼中闪过一丝惊讶",
                        "不由自主地赞叹道", "深吸一口气", "面色凝重"],
        "verb": ["佩服", "赞叹", "忌惮", "向往", "恐惧", "敬仰"],
        "action": ["切磋一场", "比试一番", "分个高下", "点到为止", "全力一战"],
        "adj": ["精妙", "恐怖", "令人窒息", "不可思议", "前所未见"],
    },
    "scene_slots": {
        "directions": ["南方", "北方", "东方", "西方", "东南方", "西北方", "西南方", "东北方"],
    },
    "character_slots": {
        "aura": ["帝威浩荡", "杀气凛然", "气度不凡", "锋芒毕露", "深不可测", "温润如玉"],
        "scope": ["万古诸天", "整个广场", "一山众人", "四方观者", "满堂宾客"],
        "modifier": ["虚空", "长空", "山门", "天际", "夜色"],
        "visual": ["眸光如电", "衣袂无风自动", "周身气机流转", "眸光淡漠"],
    },
}


def _merge_list(bank_name, new_items):
    """合并模板列表（去重、保序）。"""
    path = os.path.join(TPL_DIR, f"{bank_name}.json")
    existing = []
    if os.path.exists(path):
        try:
            existing = json.load(open(path, encoding="utf-8")).get("templates", [])
        except Exception:
            existing = []
    have = set(json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x for x in existing)
    for it in new_items:
        k = json.dumps(it, ensure_ascii=False) if not isinstance(it, str) else it
        if k in have:
            continue
        existing.append(it)
        have.add(k)
    return existing


def main():
    os.makedirs(TPL_DIR, exist_ok=True)
    report = {}

    # 模板骨架（含 dialogue_exchange 这类 list[dict]）
    for bank_name, items in CURATED.items():
        merged = _merge_list(bank_name, items)
        json.dump({"templates": merged},
                  open(os.path.join(TPL_DIR, f"{bank_name}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        report[bank_name] = f"{len(merged)} 条"

    # 槽位值池
    for bank_name, pools in SLOTS.items():
        # 与现有合并（保留已有键，覆盖/新增）
        path = os.path.join(TPL_DIR, f"{bank_name}.json")
        merged = {}
        if os.path.exists(path):
            try:
                merged = json.load(open(path, encoding="utf-8"))
            except Exception:
                merged = {}
        merged.update(pools)
        json.dump(merged, open(path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        report[bank_name] = f"{len(merged)} 类槽位"

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
