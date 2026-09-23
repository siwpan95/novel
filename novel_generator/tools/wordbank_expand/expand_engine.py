#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""词库每日联网扩充引擎（万界归墟·棋盘生成器）。

流程：Glob 内容库 → 每文件一次 Tavily 联网检索真实语料 → 按各子列表 schema
（list[str] 或 list[dict]）抽取候选 → 去重+旋转词护栏 → 安全追加(原子写) →
滚动健康校验 → 写增长日志。

用法:
    python expand_engine.py [--cap 60] [--results 10] [--max-searches 60] [--dry-run]
"""
import sys
import os
import json
import re
import math
import time
import datetime
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tavily_search import search  # noqa

# 2026-09-28 去本地化：词库根与增长日志改由本文件位置推导（原 G:/novel 硬编码已不存在）
_LIB_ROOT = Path(__file__).resolve().parents[2]   # novel_generator/
ROOT = str(_LIB_ROOT / "word_banks")
LOG_PATH = str(_LIB_ROOT / "docs" / "wordbank_growth_log.md")

SKIP_RELS = {
    "content_manifest.json",
    "narrative/event_spine.json",
    "narrative/info_asymmetry.json",
    "narrative/interiority.json",
    "narrative/pov_assignment.json",
    "narrative/pov_lenses.json",
    "narrative/pov_timeline.json",
    "narrative/rashomon.json",
    "voice/voice_flavours.json",
    "vocab/names.json",
}

GENRE = {
    "creator_ruins": "创世遗迹", "cthulhu": "克苏鲁", "cultivation": "修仙",
    "cyberpunk": "赛博朋克", "deep_sea_ruins": "深海遗迹", "high_civ_lab": "高维文明实验室",
    "infinite_flow": "无限流", "lowmagic_medieval": "低魔中世纪", "magic_academy": "魔法学院",
    "mech_divinity": "机械神域", "modern_china": "现代都市国术", "post_apocalyptic": "末日废土",
    "ragnarok": "诸神黄昏", "scifi": "科幻星际", "steampunk": "蒸汽朋克",
    "sword_magic": "剑与魔法", "wuxia": "武侠",
}

ROT2 = ["远古", "太古", "混沌", "归墟", "蚀月", "溟蒙", "荒古", "虚空", "星辰",
        "时空", "因果", "幽蓝", "赤红", "鸿蒙", "亘古", "浑沌", "九幽", "幽冥", "苍冥", "鸿宇"]
# 仅这些单字作为「的/地/般」修饰语时才算病句（如「蚀气的他」）。
# 注意：归墟/幽渊/神墟/星渊 是本作合法世界观专有名词，墟/渊/幽 不得列入。
ROT1 = ["蚀", "溟", "荒", "鸿", "亘", "冥", "沌"]
FUNC = set("的了着过在地得和与及或但是因为所以如果就也还都极很更最被把让使于对从往朝向用给同跟比等着啊吗呢吧呀哦哟哎哼嘛啦咯喽嘞呗咦嘻喂嗬嗨噢喔呸唔嗯咦哟之其而以故且夫盖尝曾辄复遂乃则即咸皆俱并况窃谨敬敢忍")

# ---------- 查询构造 ----------
def file_query(rel):
    if rel.startswith("genre_terms/"):
        g = rel.split("/")[1].replace("_terms.json", "")
        return f"{GENRE.get(g, g)} 世界观 术语 专有名词 描写 词汇"
    tbl = {
        "vocab/adjectives.json": "小说 外貌 品质 场景 形容词 描写 词汇",
        "vocab/equipment.json": "武侠修仙 功法 招式 法宝 兵器 名称 词汇",
        "vocab/locations.json": "小说 地名 地貌 建筑 秘境 景观 名称 词汇",
        "vocab/body_parts.json": "人体 部位 名称 词汇 解剖",
        "world/scene_locations.json": "小说 各题材 场景 地点 秘境 名称 词汇",
        "world/world_openings.json": "小说 各题材 世界 开场 背景 描写 句子",
        "world/wanjie_context.json": "归墟 万界 苍凉 世界观 背景 描写 句子",
        "narrative/beat_narratives.json": "小说 情节 段落 叙事 描写 句子",
        "narrative/chapter_enrichments.json": "小说 章节 润色 描写 句子",
        "narrative/foreshadowing_pool.json": "小说 伏笔 铺垫 句子",
        "narrative/hook_templates.json": "小说 钩子 悬念 开头 句子",
        "narrative/player_chaos.json": "玩家 混乱 搞笑 沙雕 发言 句子",
        "narrative/quality_fragments.json": "小说 写作 句式 片段 连接 词汇",
        "narrative/scene_beats.json": "小说 场景 节拍 描写 句子",
        "narrative/truth_reveals.json": "小说 反转 真相 揭露 句子",
        "voice/personality_voice.json": "小说 人物 性格 语气 说话 风格 口头禅 句子",
        "voice/personality_tags.json": "小说 人物 性格 标签 对话 风格 词汇",
        "voice/voice_helpers_body_parts.json": "人体 部位 描写 词汇",
        "voice/voice_helpers_body_reaction.json": "人体 身体 反应 描写 句子",
        "voice/voice_helpers_sensations.json": "感官 知觉 描写 词汇",
        "voice/voice_helpers_sense_fallbacks.json": "感官 替代 描写 句子",
    }
    if rel in tbl:
        return tbl[rel]
    if rel.startswith("world/senses/"):
        return "小说 氛围 环境 感官 战斗 描写 句子"
    return rel + " 词汇 描写"


def is_phrase_file(rel):
    if rel.startswith("narrative/"):
        return True
    if rel.startswith("world/senses/"):
        return True
    if rel in ("world/wanjie_context.json", "world/world_openings.json"):
        return True
    if rel in ("voice/personality_voice.json", "voice/voice_helpers_body_reaction.json",
               "voice/voice_helpers_sense_fallbacks.json"):
        return True
    return False


# ---------- 旋转词护栏 ----------
def polluted(p):
    # 只拦截真正的病句：单字旋转字（蚀/溟/荒/鸿/亘/墟/冥/沌/渊/幽）作「的/地/般」修饰语
    # （如「蚀气的他开口…」）。双字旋转词（虚空/混沌/远古/幽蓝/赤红…）作正常形容词放行。
    s = p.strip()
    for r in ROT1:
        if (r + "的") in s or (r + "地") in s or (r + "般") in s:
            return True
    return False


# ---------- 候选抽取 ----------
def extract_terms(results):
    cnt = {}
    for r in results:
        text = r.get("content", "") or ""
        for m in re.findall(r'[\u4e00-\u9fff]{2,6}', text):
            if "的" in m or "了" in m:
                continue
            if all(ch in FUNC for ch in m):
                continue
            cnt[m] = cnt.get(m, 0) + 1
    return [w for w, _ in sorted(cnt.items(), key=lambda x: -x[1])]


def extract_phrases(results):
    out, seen = [], set()
    for r in results:
        text = r.get("content", "") or ""
        for part in re.split(r'[。！？!?\n；;]', text):
            p = re.sub(r'\s+', '', part)
            cn = len(re.findall(r'[\u4e00-\u9fff]', p))
            if cn < 4 or cn > 30:
                continue
            if polluted(p):
                continue
            if p in seen:
                continue
            seen.add(p)
            out.append(p)
    return out


def find_text_field(d0):
    for k, v in d0.items():
        if isinstance(v, str):
            return k
    return None


# ---------- 主流程 ----------
def main():
    args = sys.argv[1:]
    CAP = 60
    MAXR = 10
    MAX_SEARCHES = 60
    DRY = "--dry-run" in args
    for a in args:
        if a.startswith("--cap="):
            CAP = int(a.split("=")[1])
        elif a.startswith("--results="):
            MAXR = int(a.split("=")[1])
        elif a.startswith("--max-searches="):
            MAX_SEARCHES = int(a.split("=")[1])

    ONLY = None
    for a in args:
        if a.startswith("--only="):
            ONLY = set(a.split("=", 1)[1].split(","))

    files = []
    for dp, dn, fn in os.walk(ROOT):
        if ".backup_originals" in dp:
            continue
        for f in fn:
            if not f.endswith(".json"):
                continue
            rel = os.path.relpath(os.path.join(dp, f), ROOT).replace("\\", "/")
            if rel in SKIP_RELS:
                continue
            files.append(rel)
    files.sort()
    if ONLY:
        files = [f for f in files if f in ONLY]

    searches_used = 0
    file_stats = []
    search_failed = []
    added_poll = 0  # 仅统计本次新增短语中违反旋转词护栏的条数

    for rel in files:
        path = os.path.join(ROOT, rel)
        try:
            old_size = os.path.getsize(path)
            d = json.load(open(path, encoding="utf-8"))
        except Exception as e:
            file_stats.append((rel, 0, 0, 0, [f"读取失败:{e}"], "no"))
            continue
        if not isinstance(d, dict):
            file_stats.append((rel, old_size, old_size, 0, ["非dict跳过"], "no"))
            continue
        phrase = is_phrase_file(rel)
        if searches_used >= MAX_SEARCHES:
            file_stats.append((rel, old_size, old_size, 0, ["搜索预算耗尽跳过"], "no"))
            continue
        q = file_query(rel)
        time.time()
        res = search(q, MAXR)
        searches_used += 1
        if "error" in res:
            search_failed.append((rel, res["error"]))
            file_stats.append((rel, old_size, old_size, 0, [f"检索失败:{res['error'][:60]}"], "no"))
            continue
        results = res.get("results", [])
        if not results:
            file_stats.append((rel, old_size, old_size, 0, ["无结果"], "no"))
            continue
        pool = extract_phrases(results) if phrase else extract_terms(results)
        used = set()
        added_total = 0
        notes = []
        for key, val in d.items():
            if not isinstance(val, list) or not val:
                continue
            target = min(math.ceil(len(val) * 0.10), CAP)
            if target <= 0:
                target = 1
            if isinstance(val[0], dict):
                tf = find_text_field(val[0])
                if not tf:
                    notes.append(f"{key}:list[dict]无文本字段跳过")
                    continue
                exist = {(x.get(tf) or "") for x in val}
                new_items = []
                for c in pool:
                    if c in used or c in exist:
                        continue
                    if len(new_items) >= target:
                        break
                    if phrase and polluted(c):
                        added_poll += 1
                        continue
                    new_items.append({tf: c, **{k: "" for k in val[0].keys() if k != tf}})
                    used.add(c); exist.add(c)
                if new_items:
                    d[key] = val + new_items
                    added_total += len(new_items)
            else:
                exist = set(val)
                new_items = []
                for c in pool:
                    if c in used or c in exist:
                        continue
                    if len(new_items) >= target:
                        break
                    if phrase and polluted(c):
                        added_poll += 1
                        continue
                    new_items.append(c)
                    used.add(c); exist.add(c)
                if new_items:
                    d[key] = val + new_items
                    added_total += len(new_items)
        if added_total > 0 and not DRY:
            tmp = path + ".tmp"
            try:
                json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
                json.load(open(tmp, encoding="utf-8"))
                os.replace(tmp, path)
                new_size = os.path.getsize(path)
            except Exception as e:
                if os.path.exists(tmp):
                    os.remove(tmp)
                notes.append(f"写入校验失败:{e}")
                added_total = 0
                new_size = old_size
        else:
            new_size = old_size
        file_stats.append((rel, old_size, new_size, added_total, notes, "yes"))

    # ---------- 滚动健康校验 ----------
    # (a) 已写文件结构有效：写入时已 json.load 校验通过。
    # (b) 去重自检：各被改写列表 len == len(set)。
    # (c) 污染自检：仅统计【本次新增】短语中违反旋转词护栏的条数（既有库含合法设定词如归墟/幽渊，不计入）。
    dedup_viol = 0
    for rel in files:
        path = os.path.join(ROOT, rel)
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        for key, val in d.items():
            if not isinstance(val, list):
                continue
            vals = [str(x) for x in val] if (val and isinstance(val[0], dict)) else val
            if len(vals) != len(set(vals)):
                dedup_viol += 1
    poll_viol = added_poll

    total_added = sum(s[3] for s in file_stats)
    total_old = sum(s[1] for s in file_stats)
    total_new = sum(s[2] for s in file_stats)
    health_ok = (dedup_viol == 0 and poll_viol == 0)
    conclusion = "全部一致 ✅" if health_ok else "存在偏差 ❌"

    # ---------- 写增长日志 ----------
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"\n## {now}（手动验证运行 · CAP={CAP} MAXR={MAXR} 搜索={searches_used}）",
             f"- 处理内容库：{len([s for s in file_stats if s[5]=='yes'])} 个；检索失败：{len(search_failed)} 个",
             f"- 总新增条目：**{total_added}**；体积 {total_old/1048576:.2f}MB → {total_new/1048576:.2f}MB",
             f"- 健康校验：去重异常 {dedup_viol} · 旋转词污染 {poll_viol} → {conclusion}"]
    for rel, o, n, a, notes, ok in file_stats:
        if a > 0 or notes:
            lines.append(f"  - {rel}: +{a} 条 ({o/1048576:.3f}→{n/1048576:.3f}MB) {'; '.join(notes)}")
    if search_failed:
        lines.append("  - 检索失败: " + "; ".join(f"{r}:{e[:40]}" for r, e in search_failed))
    lines.append("")

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))

    summary = {
        "files_processed": len([s for s in file_stats if s[5] == "yes"]),
        "search_failed": len(search_failed),
        "searches_used": searches_used,
        "total_added": total_added,
        "size_mb": [round(total_old/1048576, 2), round(total_new/1048576, 2)],
        "dedup_violations": dedup_viol,
        "pollution_violations": poll_viol,
        "conclusion": conclusion,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("LOG:", LOG_PATH)


if __name__ == "__main__":
    main()
