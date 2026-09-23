#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模板挖掘流水线：联网搜网文写作公式 → 拆模板骨架 → 写 templates/ 词库。

姊妹流水线（两者互补）：
  - expand_engine.py  负责「词库量」（每日联网扩充内容条目）
  - template_miner.py 负责「模板骨架」（带 {slot} 槽位的句式模板）

产出：
  word_banks/templates/*.json
    - battle_action / battle_reaction / battle_effect  打斗三段式模板（快慢快公式）
    - battle_opening / battle_ending                    战斗开场/收尾模板
    - battle_slots                                      槽位值池（color/action/verb/... 从 battle.py 硬编码迁入）
    - scene_frame / character_intro / emotion_beat      场景/人物出场/情绪模板

模板槽位约定（与 BattleGenerator 的 str.replace 兼容）：
  {attacker} {defender} {skill} {weapon} {def_skill} {treasure} {terrain}
  {color} {action} {action2} {verb} {thing} {expression} {lunge} {shake}
  {debris} {moment} {spring} {gear} {damage} {belated} {lack} {gaze} {focus}
  {num} {num2}
  （scene/character/emotion 用：{world} {landmark} {visual} {auditory} {weather}
   {crowd} {ambient} {name} {aura} {scope} {char} {body_reaction} {modifier}）

确定性：同 seed 同输出（仅 Tavily 检索部分依赖网络，失败则只保留种子模板）。
用法：python template_miner.py [--results 8] [--dry-run]
"""
import sys
import os
import json
import re
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tavily_search import search  # noqa

# 2026-09-23 去本地化：词库根改由本文件位置推导（原 G:/novel 硬编码已不存在）
ROOT = str(Path(__file__).resolve().parents[2] / "word_banks")
TPL_DIR = os.path.join(ROOT, "templates")

# ---------------------------------------------------------------------------
# 种子模板骨架（联网调研提炼：打斗七公式 / 快慢快节奏 / 辰东句式 / 场景描写时机）
# ---------------------------------------------------------------------------
SEED = {
    "battle_action": [
        "{attacker}猛然施展{skill}，{action}，直取{defender}的要害！",
        "刀光闪过。{attacker}来不及思考，身体本能后仰。",
        "轰隆一声，天地失色。{attacker}的{skill}已经{action}！",
        "{attacker}抬手，{skill}镇压而下，整片{terrain}都{shake}。",
        "{attacker}脚尖一点，整个人如{spring}般{lunge}向{defender}，{weapon}已经抵住咽喉。",
        "{attacker}故意卖出破绽，中门大开——{defender}抢攻的瞬间，{weapon}已封住所有退路。",
        "第一招——{skill}；第二招——{weapon}回旋{action}；第三招——借力再起，三招一气呵成！",
        "{attacker}的动作突然慢了半拍，不是力竭，是诱敌。",
        "没有喊话，没有试探。{attacker}的{skill}直接压了上去。",
        "{attacker}把重心压到几乎贴地，下一个呼吸，{weapon}已经出鞘。",
        "一寸长一寸强——{attacker}的{weapon}在距离上完全压制了{defender}。",
        "一寸短一寸险——{attacker}不退反进，欺入{defender}的{weapon}死角，{skill}贴身{action}。",
    ],
    "battle_reaction": [
        "{defender}不退反进，{def_skill}迎面而上，两股力量轰然相撞！",
        "{defender}瞳孔骤缩——{moment}之间，他只有一个选择。",
        "{defender}似乎早已看穿了{skill}的破绽，只是微微侧头，{weapon}贴着他的耳朵擦过。",
        "{defender}忽然闭上了眼睛，不是放弃，是以耳代目。",
        "{defender}一脚跺在{terrain}上，{debris}里，{attacker}的视线被挡了{moment}。",
        "{defender}避无可避，却双手交叉护在胸前，硬吃了这一记{skill}。",
        "{defender}的应对漂亮得不像临时反应，仿佛他等这一记{skill}已经等了很久。",
        "{defender}丝毫不慌，{def_skill}迎上，两股力量轰然相撞！",
        "{defender}早有防备，{treasure}光华一闪，竟将那{thing}尽数{verb}。",
    ],
    "battle_effect": [
        "两股力量相撞之处，爆发出{color}的光芒，整片{terrain}都被震得{shake}。",
        "没有爆炸，没有巨响。两股力量在{terrain}上方无声地抵消了——越安静的对撞越凶险。",
        "碰撞的中心安静了{moment}，然后冲击波才{belated}地扩散开来。",
        "轰然巨响中，{defender}被震退了{num}步，脸上露出{expression}之色。",
        "烟雾散去后，两人脚下的{terrain}已经面目全非，但{attacker}连看都没看一眼。",
        "两股力量在空中僵持了{num}息的功夫，终于轰然炸开，{thing}四散飞溅。",
        "这一招余波所及，{terrain}上的{thing}纷纷{verb}，景象{adj}至极。",
    ],
    "battle_opening": [
        "两人对峙片刻，{attacker}率先出手！",
        "战斗一触即发！{attacker}与{defender}同时发动攻击！",
        "{terrain}上的空气先绷紧了半息——然后{attacker}动了。",
        "谁都没有先说话。{attacker}和{defender}同时判断出了彼此的距离，然后同时踏了出去。",
        "{defender}后撤半步，把{terrain}的地形让给了对手。{attacker}没有客气。",
    ],
    "battle_ending": [
        "经过{num}回合的激战，两人各自后退几步，彼此眼中都多了几分凝重。",
        "这一战打得天昏地暗，{terrain}之上已是面目全非。",
        "两人相视一眼，同时收招——这一场，平手。",
        "{terrain}安静下来，只剩下两个人的喘息，一长一短，错着拍子。",
        "打到第{num}回合，双方都清楚了一件事——今天分不出胜负。",
    ],
    "scene_frame": [
        "踏入{landmark}，眼前豁然开朗。{visual}。",
        "{weather}压城，{crowd}。空气里{ambient}。",
        "首次进入{world}，{visual}先于一切建立印象。",
        "这里{visual}，{auditory}，像谁把{world}最{adj}的一面都堆在了这一处。",
        "越往里走，{ambient}越浓，{auditory}隐隐约约，分不清是风声还是别的什么。",
    ],
    "character_intro": [
        "{modifier}破碎，一道身影缓缓走出，周身{aura}，镇压{scope}。",
        "「{name}，你终于来了。」声音平淡，却如惊雷炸响在每个人心头。",
        "{name}站在那里，{aura}，{visual}，像一柄出鞘的剑。",
        "没人看清{name}是怎么出现的。等众人回过神来，{name}已经在场中了。",
    ],
    "emotion_beat": [
        "{char}眼中燃烧着不甘的火焰，{body_reaction}。",
        "{char}没有说话，只是{body_reaction}，攥紧了拳。",
        "{char}深吸一口气，把{expression}压回眼底。",
        "这一瞬，{char}什么都听不见了，只剩{body_reaction}。",
    ],
    "battle_slots": {
        "color": ["金", "银", "红", "蓝", "紫", "青", "白", "黑", "七彩", "混沌"],
        "action": ["呼啸而出", "疾射而去", "翻涌而至", "狂卷而来", "劈头盖脸砸下", "铺天盖地涌来", "排山倒海压下"],
        "action2": ["横扫而出", "反卷回来", "倒撞而下", "斜切而入", "自下而上挑起", "贴地扫过"],
        "verb": ["抵挡", "化解", "格挡", "避开", "硬接", "弹开", "消融"],
        "expression": ["惊骇", "凝重", "苍白", "难看", "难以置信", "铁青", "恐惧"],
        "adj": ["壮观", "恐怖", "绚烂", "惨烈", "激烈", "震撼"],
        "thing": ["闪电", "狂风", "烈焰", "寒冰", "雷霆", "飞剑", "巨石", "星辰"],
        "spring": ["弹簧", "离弦的箭", "绷断的弓弦", "被松开的机括", "挣脱锁链的兽"],
        "lunge": ["撞", "扑", "欺", "蹿", "劈", "刺", "顶"],
        "shake": ["嗡嗡作响", "微微开裂", "碎屑纷落", "晃了一下", "扬起一层灰", "低低震了很久"],
        "debris": ["碎石飞溅", "尘土腾起", "碎屑打着旋", "一片扬灰", "崩开的渣子四散", "地面炸开的粉末"],
        "moment": ["一秒", "半息", "一瞬", "两个呼吸", "一刹那", "小半个弹指"],
        "belated": ["后知后觉", "迟了半拍", "慢了一步", "姗姗来迟", "不情不愿", "沉闷"],
        "lack": ["恐惧", "犹豫", "退意", "慌乱", "半分服软"],
        "gaze": ["战意", "杀意", "冷静", "疯狂", "执拗", "兴奋"],
        "focus": ["对方的下一个动作", "彼此的呼吸节奏", "对手握兵器的那只手", "对方脚下的重心", "对面那双眼睛"],
        "gear": ["袖口", "衣襟", "护腕", "肩甲", "下摆", "手背", "领口"],
        "damage": ["一道口子", "一片焦痕", "一层白霜", "几缕裂纹", "一道血痕", "半个焦黑的掌印"],
    },
}

# 联网检索主题 → 目标模板文件（只做「捞语料」，不做低质量自动拆槽）
QUERIES = {
    "battle_action": "网文 打斗 出手 描写 句式 模板 动作 凌厉",
    "battle_effect": "网文 打斗 余波 描写 句式 天地失色 环境破坏",
    "scene_frame": "网文 场景描写 句式 环境 氛围 模板 例子",
    "character_intro": "网文 人物出场 描写 句式 模板 气度",
    "emotion_beat": "网文 情绪 描写 句式 模板 愤怒 不甘 绝望",
}


def _extract_clauses(results, min_cn=6, max_cn=40):
    """从 Tavily 结果抽取候选中文短句（与 expand_engine 同思路）。"""
    out, seen = [], set()
    for r in results:
        text = r.get("content", "") or ""
        for part in re.split(r'[。！？!?\n；;]', text):
            p = re.sub(r'\s+', '', part)
            cn = len(re.findall(r'[\u4e00-\u9fff]', p))
            if cn < min_cn or cn > max_cn:
                continue
            if p in seen:
                continue
            seen.add(p)
            out.append(p)
    return out


def _load_or_seed(name):
    path = os.path.join(TPL_DIR, f"{name}.json")
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            pass
    if name == "battle_slots":
        return dict(SEED["battle_slots"])
    return {"templates": list(SEED.get(name, []))}


def _merge_templates(existing, mined):
    """把联网捞到的候选并入模板列表（去重、截断上限）。"""
    pool = existing.get("templates", [])
    have = set(pool)
    for c in mined:
        if c in have:
            continue
        pool.append(c)
        have.add(c)
    # 上限 200 条，防止失控
    return {"templates": pool[:200]}


def main():
    args = sys.argv[1:]
    MAXR = 8
    DRY = "--dry-run" in args
    for a in args:
        if a.startswith("--results="):
            MAXR = int(a.split("=")[1])

    os.makedirs(TPL_DIR, exist_ok=True)
    report = {}
    mined_raw = {}  # 联网捞到的原始句子（无槽位），供 LLM 二次拆槽，不混入槽位模板

    for name, query in QUERIES.items():
        existing = _load_or_seed(name)
        mined = []
        try:
            res = search(query, MAXR)
            if "error" in res:
                report[name] = f"检索失败: {res['error'][:50]}"
            else:
                mined = _extract_clauses(res.get("results", []))
                report[name] = f"捞到 {len(mined)} 条候选"
        except Exception as e:
            report[name] = f"异常: {e}"

        # 槽位模板保持纯净（仅种子，联网候选单独存档，不混入）
        if not DRY:
            json.dump({"templates": existing.get("templates", [])},
                      open(os.path.join(TPL_DIR, f"{name}.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
        if mined:
            mined_raw[name] = mined

    # battle_slots（纯种子，无联网主题，但也要落盘）
    slots = _load_or_seed("battle_slots")
    if not DRY:
        json.dump(slots, open(os.path.join(TPL_DIR, "battle_slots.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    report["battle_slots"] = f"槽位 {len(slots)} 类"

    # battle_opening / battle_ending / battle_reaction（纯种子）
    for extra in ("battle_opening", "battle_ending", "battle_reaction"):
        d = _load_or_seed(extra)
        if not DRY:
            json.dump(d, open(os.path.join(TPL_DIR, f"{extra}.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
        report[extra] = f"{len(d.get('templates', []))} 条"

    # 联网原始候选单独存档（供 LLM 拆槽，不污染槽位模板）
    if mined_raw and not DRY:
        json.dump(mined_raw, open(os.path.join(TPL_DIR, "_mined_raw.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        report["_mined_raw"] = f"存档 {sum(len(v) for v in mined_raw.values())} 条原始候选"

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("TPL_DIR:", TPL_DIR)


if __name__ == "__main__":
    main()
