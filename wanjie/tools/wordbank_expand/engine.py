# -*- coding: utf-8 -*-
"""词库扩充引擎 —— 确定性、stdlib-only、去重/占位符保护/schema 保持。

生成策略：
- 列表型词库：按「题材/键名」选择生成配方，组合式产出海量连贯中文文本。
- 题材术语：形态重组（前缀+核心词+后缀），核心词取自现有词条与联网术语种子，
  绝不产生双词缀怪词。
- 叙事/描写：句模板 + 槽位池填充，产出自包含固定文本（运行时占位符仅保留在
  原始模板条目）。
- 嵌套结构（world_senses / scene_beats / personality_tags 等）：递归处理，
  仅扩充「列表」节点，保持 dict/str 节点原样。
- 确定性：每文件用 djb2(bank) 派生固定随机种子，可复现。
- 体积控制：先慷慨生成，再按「保留现有条目、从末尾裁掉新增条目」贪心裁剪到目标体积。
"""
import json
import os
import random
import string as _string

import pools_common as PC
import pools_genre as PG

# 内容模板（FRAME_TEMPLATES / CHAOS_TEMPLATES / SENSATION_TEMPLATES /
# VOICE_SHORT_TEMPLATES / OPENING_SUFFIXES / SEED_CONTENT_TEMPLATES /
# SEED_RECOVERY_TEMPLATES）已迁至 engine_templates.json，此处统一加载，
# 保持同名模块变量，供下方逻辑直接使用（逻辑零改动）。
import json as _json
_ENGINE_TEMPLATES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "engine_templates.json")
with open(_ENGINE_TEMPLATES_PATH, encoding="utf-8") as _f:
    _ENGINE_TEMPLATES = _json.load(_f)
FRAME_TEMPLATES = _ENGINE_TEMPLATES["FRAME_TEMPLATES"]
CHAOS_TEMPLATES = _ENGINE_TEMPLATES["CHAOS_TEMPLATES"]
SENSATION_TEMPLATES = _ENGINE_TEMPLATES["SENSATION_TEMPLATES"]
VOICE_SHORT_TEMPLATES = _ENGINE_TEMPLATES["VOICE_SHORT_TEMPLATES"]
OPENING_SUFFIXES = _ENGINE_TEMPLATES["OPENING_SUFFIXES"]
SEED_CONTENT_TEMPLATES = _ENGINE_TEMPLATES["SEED_CONTENT_TEMPLATES"]
SEED_RECOVERY_TEMPLATES = _ENGINE_TEMPLATES["SEED_RECOVERY_TEMPLATES"]

SEED_BASE = 20260809
TARGET_BYTES = 1_100_000          # 目标体积（略高于 1MB，留格式开销余量）
GROW = 8                           # 新增条目 = 现有条目 * GROW + BASE
BASE = 400
HARD_CAP = 40000                  # 单列表生成上限，防内存爆炸
OVERGEN = 2.5                     # 逐列表过生成系数（交给 trim_to_target 精确裁剪到目标体积）

SKIP_KEYS = {"planting_beats"}     # 不放大的列表（承载语义，不可随意新增）

GENRE_FILES = set(PG.GENRE_CORES.keys())

SENSE_TYPES = ["visual", "auditory", "olfactory", "tactile", "taste"]

# 后缀族映射（形态重组）
SUFFIX_FOR = {
    "technique": PC.TECH_SUFFIX,
    "item": PG.ITEM_SUFFIX,
    "sect": PG.SECT_SUFFIX,
    "entity": PG.ENTITY_SUFFIX,
    "location": PG.LOC_SUFFIX,
}


# ----------------------------------------------------------------------------
# 工具
# ----------------------------------------------------------------------------
def djb2(s):
    h = 5381
    for c in s:
        h = ((h << 5) + h + ord(c)) & 0xFFFFFFFF
    return h


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_json(p, d):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2, separators=(",", ": "))


def estimate_bytes(d):
    return len(json.dumps(d, ensure_ascii=False, indent=2).encode("utf-8"))


def resolve_field(f):
    m = {
        "m": "modifiers", "m1": "modifiers", "m2": "modifiers", "modifier": "modifiers",
        "elem": "elements", "element": "elements",
        "place": "places", "subj": "subjects", "thing": "things", "pulse": "pulses",
        "emotion": "emotions", "action": "actions",
        "sense_visual": "sense_visual", "sense_auditory": "sense_auditory",
        "sense_olfactory": "sense_olfactory", "sense_tactile": "sense_tactile",
        "sense_taste": "sense_taste",
    }
    return m.get(f)


# ----------------------------------------------------------------------------
# 通用：从句模板生成固定文本
# ----------------------------------------------------------------------------
def gen_phrases(templates, n, rng, seen):
    out = []
    prepared = []
    for tpl in templates:
        fields = [fn for _, fn, _, _ in _string.Formatter().parse(tpl) if fn]
        pools = []
        ok = True
        for fld in fields:
            pname = resolve_field(fld)
            if pname is None or pname not in PC.SHARED_POOLS:
                ok = False
                break
            pools.append(PC.SHARED_POOLS[pname])
        if not ok or not fields:
            continue
        prepared.append((tpl, fields, [list(p) for p in pools]))
    if not prepared:
        return out
    rng.shuffle(prepared)
    per = min(60000, max(60, n))  # 每个模板最多抽取的组合数（原 1500 会卡住单列表大体积文件如 wanjie_context）
    for tpl, fields, spools in prepared:
        if len(out) >= n:
            break
        drawn = 0
        tries = 0
        cap = per * 4
        while drawn < per and tries < cap and len(out) < n:
            tries += 1
            combo = tuple(rng.choice(p) for p in spools)
            try:
                s = tpl.format(**dict(zip(fields, combo)))
            except Exception:
                continue
            if s not in seen:
                seen.add(s)
                out.append(s)
                drawn += 1
    return out


# ----------------------------------------------------------------------------
# 题材术语：形态重组
# ----------------------------------------------------------------------------
def detect_genre_type(key):
    k = key.lower()
    if k == "atmosphere" or k.endswith("_atmosphere") or k in ("battle_atmosphere", "space_atmosphere"):
        return "atmosphere"
    if "realm" in k:
        return "realm"
    if any(t in k for t in ("technique", "martial", "skill", "spell", "magic")):
        return "technique"
    if any(t in k for t in ("item", "weapon", "gear", "relic")):
        return "item"
    if any(t in k for t in ("sect", "church", "class", "faction", "guild", "academy", "deity")):
        return "sect"
    if any(t in k for t in ("entity", "creature", "beast", "race", "alien", "guardian")):
        return "entity"
    if any(t in k for t in ("location", "ruin", "abyss", "colony", "place")):
        return "location"
    return "general"


def gen_genre_term(bank, key, existing, n, rng, seen):
    typ = detect_genre_type(key)
    if typ == "atmosphere":
        return gen_phrases(PG.ATMOSPHERE_TEMPLATES, n, rng, seen)
    suffix_pool = SUFFIX_FOR.get(typ)
    extra = PG.GENRE_CORES.get(bank, {}).get(key, [])
    if suffix_pool:
        # 形态重组（三词素：修饰前缀 + 核心词 + 后缀），组合空间×修饰词，
        # 足以把题材术语库推过 1MB；不产生双后缀怪词。
        stems = []
        for e in existing:
            for suf in suffix_pool:
                if e.endswith(suf) and len(e) > len(suf):
                    stems.append(e[: -len(suf)])
                    break
            else:
                stems.append(e)
        cores = stems + extra
        out = []
        tries = 0
        cap = n * 8 + 200
        while len(out) < n and tries < cap and cores and suffix_pool:
            tries += 1
            m = rng.choice(PC.MODIFIERS)
            s = rng.choice(cores)
            suf = rng.choice(suffix_pool)
            cand = m + s + suf
            if cand not in seen:
                seen.add(cand)
                out.append(cand)
        return out
    else:
        # 非后缀类型（realm/general 等）：双修饰前缀 + 核心词，组合空间巨大，
        # 足以把题材术语库推过 1MB（如 cultivation 的 realms / cthulhu 的 madness_terms）。
        cores = list(existing) + extra
        out = []
        tries = 0
        cap = n * 12 + 400
        while len(out) < n and tries < cap and cores:
            tries += 1
            m1 = rng.choice(PC.MODIFIERS)
            m2 = rng.choice(PC.MODIFIERS)
            c = rng.choice(cores)
            cand = m1 + m2 + c
            if cand not in seen:
                seen.add(cand)
                out.append(cand)
        return out


# ----------------------------------------------------------------------------
# 帧对象（scene_beats）生成
# ----------------------------------------------------------------------------


def _frame_variations():
    """展开帧模板 × 合法感官槽位组合。"""
    result = []
    for tpl, base_slots in FRAME_TEMPLATES:
        if len(base_slots) == 1:
            for s in SENSE_TYPES:
                result.append((tpl, [s]))
        else:
            for a in SENSE_TYPES:
                for b in SENSE_TYPES:
                    if a == b:
                        continue
                    result.append((tpl, [a, b]))
    return result


FRAME_VARIATIONS = _frame_variations()


def gen_frames(existing, n, rng):
    out = []
    seen = set()
    for o in existing:
        seen.add((o.get("text"), tuple(o.get("slots", []))))
    var = list(FRAME_VARIATIONS)
    rng.shuffle(var)
    for tpl, slots in var:
        if len(out) >= n:
            break
        key = (tpl, tuple(slots))
        if key in seen:
            continue
        seen.add(key)
        out.append({"text": tpl, "slots": list(slots)})
    return out


# ----------------------------------------------------------------------------
# 伏笔种子对象（foreshadowing_pool.seeds.<beat>）生成
# ----------------------------------------------------------------------------


def gen_seeds(bank, beat, existing, n, rng):
    out = []
    seen_ids = {o.get("id") for o in existing}
    base = djb2(bank + beat)
    pool_c = list(SEED_CONTENT_TEMPLATES)
    pool_r = list(SEED_RECOVERY_TEMPLATES)
    rng.shuffle(pool_c)
    rng.shuffle(pool_r)
    i = 0
    while len(out) < n:
        sid = "fs_auto_%d_%d" % (base % 100000, i)
        if sid in seen_ids:
            i += 1
            continue
        seen_ids.add(sid)
        mod = rng.choice(PC.MODIFIERS)
        content = rng.choice(pool_c).format(modifier=mod)
        rec = rng.choice(pool_r).format(modifier=mod)
        a = rng.randint(2, 6)
        b = a + rng.randint(3, 6)
        out.append({
            "id": sid,
            "content": content,
            "recovery_offset": [a, b],
            "recovery_text": rec,
        })
        i += 1
        if i > n + 50:
            break
    return out


# ----------------------------------------------------------------------------
# 玩家乱象（player_chaos）
# ----------------------------------------------------------------------------
PLAYER_COMBO_LIKE = {"reason", "announcement", "consequence", "debate_topic",
                     "discovery", "belongings", "currency"}


def gen_chaos(key, existing, n, rng, seen):
    if key == "chaos_templates":
        out = []
        pools = {"name": PC.SUBJECTS, "location": PC.PLACES, "thing": PC.THINGS,
                 "action": PC.ACTIONS, "reason": PG.REVEAL_TEMPLATES and PC.NOUNS,
                 "debate_topic": PC.NOUNS, "discovery": PC.NOUNS,
                 "announcement": PC.NOUNS, "consequence": PC.NOUNS,
                 "belongings": PC.THINGS, "currency": PC.NOUNS}
        tpls = CHAOS_TEMPLATES
        import itertools
        combo = []
        for tpl in tpls:
            fields = [fn for _, fn, _, _ in _string.Formatter().parse(tpl) if fn]
            sp = [list(pools[f]) for f in fields]
            for c in itertools.islice(itertools.product(*sp), 0, 2000):
                combo.append((tpl, fields, c))
        rng.shuffle(combo)
        for tpl, fields, c in combo:
            if len(out) >= n:
                break
            s = tpl.format(**dict(zip(fields, c)))
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out
    if key == "player_names":
        out = []
        suffixes = ["玩家", "侠", "佬", "怪", "王", "帝", "神", "仙", "魔", "徒", "本尊", "菌"]
        combo = [(m, s) for m in PC.MODIFIERS for s in suffixes]
        rng.shuffle(combo)
        for m, s in combo:
            if len(out) >= n:
                break
            cand = m + s
            if cand not in seen:
                seen.add(cand)
                out.append(cand)
        return out
    if key in PLAYER_COMBO_LIKE:
        # 组合现有短语，产出连贯新句
        out = []
        if len(existing) >= 2:
            idx = list(range(len(existing)))
            rng.shuffle(idx)
            for i in range(0, len(idx) - 1, 1):
                if len(out) >= n:
                    break
                a = existing[idx[i]]
                b = existing[idx[i + 1]]
                cand = "%s——%s。" % (a, b)
                if cand not in seen:
                    seen.add(cand)
                    out.append(cand)
        # 若不够，再用修饰前缀补充
        if len(out) < n:
            for m in PC.MODIFIERS:
                if len(out) >= n:
                    break
                for e in existing:
                    if len(out) >= n:
                        break
                    cand = m + e
                    if cand not in seen:
                        seen.add(cand)
                        out.append(cand)
        return out
    # location / thing / action 等名词型：修饰前缀 + 现有核心
    out = []
    combo = [(m, e) for m in PC.MODIFIERS for e in existing]
    rng.shuffle(combo)
    for m, e in combo:
        if len(out) >= n:
            break
        cand = m + e
        if cand not in seen:
            seen.add(cand)
            out.append(cand)
    return out


# ----------------------------------------------------------------------------
# 词汇（vocab）生成
# ----------------------------------------------------------------------------
def gen_adjective(n, rng, seen):
    # 高容量：引入三修饰词模板 + 更大切片，确保单子列表也能产出 1.5 万+ 不重复条目
    # （否则 4 个子列表各自上限仅 ~6k，整文件到不了 1MB）。
    out = []
    tpls = ["{m1}{m2}的", "{m1}{m2}{m3}的", "{m1}{m2}{adj}的",
            "{m1}{adj}的", "{adj}的"]
    import itertools
    combo = []
    for tpl in tpls:
        fields = [fn for _, fn, _, _ in _string.Formatter().parse(tpl) if fn]
        sp = []
        for f in fields:
            if f == "adj":
                sp.append(PG.ADJ_STEMS)
            else:
                sp.append(PC.MODIFIERS)
        # 三修饰词模板组合空间 60^3，切片放大到 30000 保证容量
        slice_n = 30000 if len(fields) >= 3 else 10000
        for c in itertools.islice(itertools.product(*sp), 0, slice_n):
            combo.append((tpl, fields, c))
    rng.shuffle(combo)
    for tpl, fields, c in combo:
        if len(out) >= n:
            break
        s = tpl.format(**dict(zip(fields, c)))
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def gen_body(key, n, rng, seen):
    nouns = PG.BODY_NOUNS.get(key, ["身形"])
    out = []
    combo = [(m1, m2, nn) for m1 in PC.MODIFIERS for m2 in PC.MODIFIERS for nn in nouns]
    rng.shuffle(combo)
    for m1, m2, nn in combo:
        if len(out) >= n:
            break
        cand = "%s%s的%s" % (m1, m2, nn)
        if cand not in seen:
            seen.add(cand)
            out.append(cand)
    return out


def gen_equip(key, existing, n, rng, seen):
    # weapon_prefix / weapon_type / weapon_suffix / skill_* / treasure_*
    # 高容量改写：前缀用三修饰词，类型/词身用「双修饰词+核心」，后缀用「双修饰词+后缀词」，
    # 使 9 个子列表各自可产出 1 万+ 不重复条目（原实现前缀仅 60^2=3600，整文件到不了 1MB）。
    if key.endswith("_prefix"):
        out = []
        import itertools
        for c in itertools.islice(
                itertools.product(PC.MODIFIERS, PC.MODIFIERS, PC.MODIFIERS), 0, n * 2):
            cand = c[0] + c[1] + c[2]
            if cand not in seen:
                seen.add(cand)
                out.append(cand)
            if len(out) >= n:
                break
        return out
    if key.endswith("_suffix"):
        suf_words = ["之刃", "残月", "无锋", "归墟", "断罪", "裂空", "镇魂", "噬血",
                     "惊鸿", "流光", "碎星", "焚天", "沉寂", "余烬", "破晓", "长夜",
                     "霜寒", "燎原", "寂灭", "星陨", "听风", "葬歌", "沧海", "孤鸿",
                     "断空", "轮回", "噬魂", "惊雷", "碎玉", "流霜"]
        out = []
        import itertools
        for c in itertools.islice(
                itertools.product(PC.MODIFIERS, PC.MODIFIERS, suf_words), 0, n * 2):
            cand = c[0] + c[1] + c[2]
            if cand not in seen:
                seen.add(cand)
                out.append(cand)
            if len(out) >= n:
                break
        return out
    # weapon_type / skill_body / treasure_type 等「核心」型：双修饰词 + 核心
    cores = list(existing) + PC.WEAPON_TYPES + PC.MATERIALS + PC.BEASTS + PC.ELEMENTS
    out = []
    import itertools
    for c in itertools.islice(
            itertools.product(PC.MODIFIERS, PC.MODIFIERS, cores), 0, n * 2):
        cand = c[0] + c[1] + c[2]
        if cand not in seen:
            seen.add(cand)
            out.append(cand)
        if len(out) >= n:
            break
    return out


def gen_location_key(key, existing, n, rng, seen):
    if key == "terrain_prefix" or key == "landmark_prefix" or key == "scene_quality":
        return gen_adjective(n, rng, seen)
    if key == "terrain_type":
        cores = list(existing) + PG.TERRAIN_CORES
        out = []
        for m in PC.MODIFIERS:
            for c in cores:
                if len(out) >= n: break
                cand = m + c
                if cand not in seen: seen.add(cand); out.append(cand)
        return out[:n]
    if key == "landmark_type":
        cores = list(existing) + PG.LANDMARK_CORES
        out = []
        for m in PC.MODIFIERS:
            for c in cores:
                if len(out) >= n: break
                cand = m + c
                if cand not in seen: seen.add(cand); out.append(cand)
        return out[:n]
    if key == "scene_like":
        cores = list(existing) + PC.PLACES + PG.TERRAIN_CORES
        out = []
        for m in PC.MODIFIERS:
            for c in cores:
                if len(out) >= n: break
                cand = "宛如%s%s" % (m, c)
                if cand not in seen: seen.add(cand); out.append(cand)
        return out[:n]
    if key == "secrets_hint":
        cores = list(existing) + PC.PLACES
        out = []
        for m in PC.MODIFIERS:
            for c in cores:
                if len(out) >= n: break
                cand = "传说%s%s曾在此现世。" % (m, c)
                if cand not in seen: seen.add(cand); out.append(cand)
        return out[:n]
    return []


def gen_names(key, existing, n, rng, seen):
    if key == "surnames":
        add = PG.EXTRA_SURNAMES + PC.MODIFIERS
        out = []
        for s in add:
            if len(out) >= n: break
            if s not in seen: seen.add(s); out.append(s)
        return out
    if key == "given_name_chars":
        add = PG.GIVEN_NAME_CHARS
        out = []
        for s in add:
            if len(out) >= n: break
            if s not in seen: seen.add(s); out.append(s)
        return out
    return []


# ----------------------------------------------------------------------------
# 感官 / 语音 / 体感 短语
# ----------------------------------------------------------------------------


def gen_sensation(n, rng, seen):
    out = []
    combo = [(m1, m2) for m1 in PC.SAFE_MODIFIERS for m2 in PC.SAFE_MODIFIERS]
    rng.shuffle(combo)
    tpls = SENSATION_TEMPLATES + VOICE_SHORT_TEMPLATES
    res = []
    for tpl in tpls:
        for m1, m2 in combo:
            if len(res) >= n * 3: break
            res.append(tpl.format(m=m1, m2=m2))
    rng.shuffle(res)
    for s in res:
        if len(out) >= n: break
        if s not in seen: seen.add(s); out.append(s)
    return out


def _gen_voice_all(rng, n, seen):
    """生成 personality_voice 风格的自包含语气短语。

    支持 VOICE_TEMPLATES 中的 {modifier}/{subj}/{action}/{thing}/{place} 字段，
    遇到含额外槽位的模板时从共享池取词填充；确定性（固定 rng）、去重。
    """
    combo = [(m, s) for m in PC.SAFE_MODIFIERS for s in PC.SUBJECTS]
    rng.shuffle(combo)
    res = []
    extra_pools = {"action": PC.ACTIONS, "thing": PC.THINGS, "place": PC.PLACES}
    for tpl in PG.VOICE_TEMPLATES:
        fields = [fn for _, fn, _, _ in _string.Formatter().parse(tpl) if fn]
        if not fields:
            continue
        # 仅处理已知字段的模板，未知字段一律跳过，避免 KeyError
        if not all(f in ("modifier", "subj", "action", "thing", "place") for f in fields):
            continue
        for m, s in combo:
            vals = {"modifier": m, "subj": s}
            for fld in ("action", "thing", "place"):
                if fld in fields:
                    vals[fld] = rng.choice(extra_pools[fld])
            try:
                res.append(tpl.format(**vals))
            except Exception:
                continue
    rng.shuffle(res)
    out = []
    for s in res:
        if len(out) >= n:
            break
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def gen_voice(n, rng, seen):
    return _gen_voice_all(rng, n, seen)


# ----------------------------------------------------------------------------
# 世界感官碎片
# ----------------------------------------------------------------------------
def gen_sense_fragment(sense, n, rng, seen):
    tpls = PG.SENSE_FRAGMENT_TEMPLATES.get(sense, PG.SENSE_FRAGMENT_TEMPLATES["visual"])
    out = []
    combo = [(m, m2) for m in PC.SAFE_MODIFIERS for m2 in PC.SAFE_MODIFIERS]
    rng.shuffle(combo)
    res = []
    for tpl in tpls:
        for m, m2 in combo:
            res.append(tpl.format(modifier=m, m2=m2))
    rng.shuffle(res)
    for s in res:
        if len(out) >= n: break
        if s not in seen: seen.add(s); out.append(s)
    return out


# ----------------------------------------------------------------------------
# 世界开篇横幅（world_openings，按世界名生成）
# ----------------------------------------------------------------------------


def gen_openings(world, existing, n, rng, seen):
    base = [tpl.format(world=world) for tpl in PG.OPENING_TEMPLATES]
    cands = list(base)
    for m in PC.MODIFIERS:
        for suf in OPENING_SUFFIXES:
            cands.append("%s%s%s" % (world, m, suf))
    rng.shuffle(cands)
    out = []
    for s in cands:
        if len(out) >= n:
            break
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


# ----------------------------------------------------------------------------
# 性格标签（personality_tags）特殊处理：保证 列表 与 字典 一致
# ----------------------------------------------------------------------------
def _gen_voice_phrases(rng, n, existing=None):
    seen = set(existing) if existing else set()
    return _gen_voice_all(rng, n, seen)


def _expand_inner_lists(obj, rng, seen):
    """递归地把 dict 内所有 list 节点扩充（用于 personality_tags 的 dialogue_styles 等）。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, list) and v and isinstance(v[0], str):
                gen = _gen_voice_phrases(rng, target_for(len(v)), v)
                obj[k] = v + gen
            elif isinstance(v, (dict, list)):
                _expand_inner_lists(v, rng, set(v) if isinstance(v, list) else set())
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                _expand_inner_lists(item, rng, set())


def _diff_meta(orig, new):
    """比较两个同构 dict/list，返回 {path: {"exist": 原长, "gen": 新增数}}。"""
    meta = {}
    def walk(o, n, path):
        if isinstance(n, dict) and isinstance(o, dict):
            for k in n:
                walk(o.get(k, [] if isinstance(n[k], list) else {}), n[k], path + "/" + k)
        elif isinstance(n, list) and isinstance(o, list):
            if n and isinstance(n[0], (str, dict)):
                meta[path] = {"exist": len(o), "gen": max(0, len(n) - len(o))}
            else:
                for i in range(min(len(o), len(n))):
                    walk(o[i], n[i], path)
    walk(orig, new, "")
    return meta


def expand_personality_tags(path):
    rng = random.Random(SEED_BASE + djb2("personality_tags"))
    orig = load_json(path)
    data = json.loads(json.dumps(orig))  # 深拷贝，用于 diff 计算 meta
    seen_tags = set(data.get("personality_tags", []))
    new_tags = [t for t in PG.PERSONALITY_EXTRA if t not in seen_tags]
    data["personality_tags"] = data["personality_tags"] + new_tags
    tone_pool = ["惜字如金，每句话不过八字", "话里有话，每句都像在暗示什么",
                 "永远不把话说死", "声若洪钟，笑声响亮", "句末叹号率偏高",
                 "擅用反问", "慢条斯理，却句句在点", "冷淡里藏着算计"]
    for t in new_tags:
        if "dialogue_styles" in data and t not in data["dialogue_styles"]:
            data["dialogue_styles"][t] = {
                "openings": _gen_voice_phrases(rng, 14),
                "responses": _gen_voice_phrases(rng, 14),
                "tone": rng.choice(tone_pool),
            }
        if "battle_preferences" in data and t not in data["battle_preferences"]:
            data["battle_preferences"][t] = {
                "openings": _gen_voice_phrases(rng, 14),
                "responses": _gen_voice_phrases(rng, 14),
                "tone": rng.choice(tone_pool),
            }
        if "quirks" in data and t not in data["quirks"]:
            data["quirks"][t] = {
                "openings": _gen_voice_phrases(rng, 14),
                "responses": _gen_voice_phrases(rng, 14),
                "tone": rng.choice(tone_pool),
            }
    # 扩充既有性格的内部列表（openings/responses 等），以既有内容去重避免重复
    for sub in ("dialogue_styles", "battle_preferences", "quirks"):
        if sub in data and isinstance(data[sub], dict):
            for name, d in data[sub].items():
                if isinstance(d, dict):
                    for k, v in d.items():
                        if isinstance(v, list) and v and isinstance(v[0], str):
                            gen = _gen_voice_phrases(rng, target_for(len(v)), v)
                            d[k] = v + gen
    meta = _diff_meta(orig, data)
    trim_to_target(data, meta, TARGET_BYTES)
    save_json(path, data)
    return estimate_bytes(data), meta


# ----------------------------------------------------------------------------
# 中枢分发
# ----------------------------------------------------------------------------
def target_for(existing_len):
    # 慷慨生成，再由 trim_to_target 精确裁剪到目标体积；
    # 每个列表至少尝试 25000 条，确保多列表文件能显著超过 1.1MB。
    return min(HARD_CAP, max(existing_len, 25000))


def _gen_strlist(bank, key, existing, rng, seen, per_list=None):
    n = per_list if per_list else target_for(len(existing))
    if key in SKIP_KEYS:
        return []
    # 题材术语
    if bank in GENRE_FILES:
        return gen_genre_term(bank, key, existing, n, rng, seen)
    # 各叙事/描写词库
    if bank == "beat_narratives":
        return gen_phrases(PC.NARRATIVE_TEMPLATES, n, rng, seen)
    if bank == "chapter_enrichments":
        if key in ("theme", "debate", "epilogue", "opening", "interlude", "climax", "fallout"):
            return gen_phrases(PG.CHAPTER_TEMPLATES, n, rng, seen)
        return gen_phrases(PC.NARRATIVE_TEMPLATES, n, rng, seen)
    if bank == "hook_templates":
        return gen_phrases(PG.HOOK_TEMPLATES, n, rng, seen)
    if bank == "truth_reveals":
        return gen_phrases(PG.REVEAL_TEMPLATES + PC.NARRATIVE_TEMPLATES, n, rng, seen)
    if bank == "quality_fragments":
        mapping = {
            "short_patterns": PG.SHORT_TEMPLATES,
            "single_char_lines": PG.SINGLE_CHAR_TEMPLATES,
            "long_sentence_connectors": PG.CONNECTOR_TEMPLATES,
            "incomplete_sentence_templates": PG.INCOMPLETE_TEMPLATES,
            "self_correction_templates": PG.SELF_CORRECT_TEMPLATES,
        }
        if key in mapping:
            return gen_phrases(mapping[key], n, rng, seen)
        return gen_phrases(PC.NARRATIVE_TEMPLATES, n, rng, seen)
    if bank == "wanjie_context":
        return gen_phrases(PG.ATMOSPHERE_TEMPLATES, n, rng, seen)
    if bank == "world_senses_ambient":
        return gen_sense_fragment(key, n, rng, seen)  # key 即感官类型
    if bank == "world_senses_battle":
        return gen_phrases(PG.BATTLE_TEMPLATES, n, rng, seen)
    if bank == "world_openings":
        return gen_openings(key, existing, n, rng, seen)  # key = 世界名
    if bank == "scene_locations":
        cores = list(existing) + PC.PLACES
        out = []
        for m in PC.MODIFIERS:
            for c in cores:
                if len(out) >= n: break
                cand = m + c
                if cand not in seen: seen.add(cand); out.append(cand)
        return out[:n]
    if bank == "scene_beats":
        if key == "world_anchor":
            cores = list(existing) + PC.PLACES
            out = []
            for m in PC.MODIFIERS:
                for c in cores:
                    if len(out) >= n: break
                    cand = m + c
                    if cand not in seen: seen.add(cand); out.append(cand)
            return out[:n]
        if key in ("calm", "tense", "dark"):
            return gen_phrases(PG.SHORT_TEMPLATES, n, rng, seen)
        return gen_phrases(PG.ATMOSPHERE_TEMPLATES, n, rng, seen)
    if bank == "player_chaos":
        return gen_chaos(key, existing, n, rng, seen)
    if bank == "adjectives":
        return gen_adjective(n, rng, seen)
    if bank == "body_parts":
        return gen_body(key, n, rng, seen)
    if bank == "equipment":
        return gen_equip(key, existing, n, rng, seen)
    if bank == "locations":
        return gen_location_key(key, existing, n, rng, seen)
    if bank == "names":
        return gen_names(key, existing, n, rng, seen)
    if bank == "personality_voice":
        return gen_voice(n, rng, seen)
    if bank == "voice_helpers_sensations":
        return gen_sensation(n, rng, seen)
    if bank == "voice_helpers_body_parts":
        return gen_voice(n, rng, seen)
    # 兜底：修饰前缀 + 现有核心（安全修饰池，避免旋转词破坏句子语法）
    out = []
    for m in PC.SAFE_MODIFIERS:
        for e in existing:
            if len(out) >= n: break
            cand = m + e
            if cand not in seen: seen.add(cand); out.append(cand)
    return out[:n]


# ----------------------------------------------------------------------------
# 递归展开 + 记录 floors
# ----------------------------------------------------------------------------
def _is_broaden_dict(bank, key, value):
    if not value:
        return False
    if all(isinstance(v, str) for v in value.values()):
        if bank == "voice_helpers_body_reaction" and key == "body_reaction":
            return True
        if bank == "voice_helpers_sense_fallbacks" and key == "sense_fallbacks":
            return True
    return False


def _broaden_dict(bank, key, value, rng):
    new = dict(value)
    if bank == "voice_helpers_body_reaction":
        for k, v in PG.BODY_REACTION_EXPAND.items():
            if k not in new:
                new[k] = v
    elif bank == "voice_helpers_sense_fallbacks":
        for k, v in PG.SENSE_FALLBACK_EXPAND.items():
            if k not in new:
                new[k] = v
    return new


def _object_kind(bank, key, value):
    if not value:
        return None
    if bank == "scene_beats" and key in ("frames", "spot_frames", "single_sense_frames"):
        return "frame"
    if bank == "foreshadowing_pool" and key in ("seeds",):
        return "seed"
    # 通用：含 id/content 视为 seed；含 text/slots 视为 frame
    first = value[0]
    if isinstance(first, dict):
        if "text" in first and "slots" in first:
            return "frame"
        if "id" in first and "content" in first:
            return "seed"
    return None


def _expand(value, bank, key, path, rng, budget=None):
    budget = budget or {}
    if isinstance(value, dict):
        if _is_broaden_dict(bank, key, value):
            return _broaden_dict(bank, key, value, rng), {}
        new = {}
        meta = {}
        for k, v in value.items():
            nv, sub = _expand(v, bank, k, path + "/" + k, rng, budget)
            new[k] = nv
            meta.update(sub)
        return new, meta
    if isinstance(value, list):
        if value and isinstance(value[0], dict):
            kind = _object_kind(bank, key, value)
            per = budget.get(path)
            n = per if per else target_for(len(value))
            if kind == "frame":
                gen = gen_frames(value, n, rng)
                return value + gen, {path: {"exist": len(value), "gen": len(gen)}}
            if kind == "seed":
                gen = gen_seeds(bank, key, value, n, rng)
                return value + gen, {path: {"exist": len(value), "gen": len(gen)}}
            return value, {}
        # list of str
        new_entries = _gen_strlist(bank, key, value, rng, set(value), budget.get(path))
        return value + new_entries, {path: {"exist": len(value), "gen": len(new_entries)}}
    return value, {}


# ----------------------------------------------------------------------------
# 裁剪到目标体积
# ----------------------------------------------------------------------------
def _collect_lists(d, path, refs):
    if isinstance(d, dict):
        for k, v in d.items():
            _collect_lists(v, path + "/" + k, refs)
    elif isinstance(d, list):
        if d and isinstance(d[0], dict):
            refs[path] = d  # 帧/种子对象列表
        else:
            refs[path] = d


def trim_to_target(data, meta, target):
    import heapq
    refs = {}
    _collect_lists(data, "", refs)
    size = estimate_bytes(data)
    if size <= target:
        return
    # 每条目平均字节（含缩进/分隔符开销）近似估计，用于增量扣减，
    # 避免每次 pop 都整体重新序列化（旧实现 O(pops × 文件字节) 会 OOM/卡死）。
    # 精确测量每条列表的「实际」每条字节代价（含其在父结构中的缩进/分隔符）：
    # 临时把该列表清空后整体重序列化，求字节差。每列表仅一次序列化，O(列表数)，
    # 远优于逐条重序列化（旧实现 O(pops×文件字节) 会 OOM/卡死）。
    # 用真实代价计数，贪心裁剪才能停在目标体积附近，残余由末尾精确校正兜底。
    full = size
    cost = {}
    for p, lst in refs.items():
        if len(lst) <= 1:
            cost[p] = 64
            continue
        saved = lst[:]
        lst[:] = []
        sz_empty = estimate_bytes(data)
        lst[:] = saved
        bytes_of_list = max(1.0, full - sz_empty)
        cost[p] = max(8.0, bytes_of_list / len(lst))
    heap = [(-meta[p]["gen"], p) for p in meta if meta[p]["gen"] > 0 and p in refs]
    heapq.heapify(heap)
    guard = 0
    maxpop = sum(m["gen"] for m in meta.values()) + 16
    while size > target and heap and guard < maxpop:
        guard += 1
        neg, p = heapq.heappop(heap)
        lst = refs[p]
        floor = meta[p]["exist"]
        if len(lst) > floor:
            lst.pop()
            size -= cost.get(p, 8)
            meta[p]["gen"] -= 1
            if len(lst) > floor:
                heapq.heappush(heap, (-meta[p]["gen"], p))
    # 增量估计可能略偏，做一次精确校正（此时待裁剪量很小，开销可忽略）
    if estimate_bytes(data) > target:
        exact = [(-meta[p]["gen"], p) for p in meta if meta[p]["gen"] > 0 and p in refs]
        heapq.heapify(exact)
        while estimate_bytes(data) > target and exact:
            neg, p = heapq.heappop(exact)
            lst = refs[p]
            floor = meta[p]["exist"]
            if len(lst) > floor:
                lst.pop()
                meta[p]["gen"] -= 1
                if len(lst) > floor:
                    heapq.heappush(exact, (-meta[p]["gen"], p))


def _list_avg_entry_bytes(lst):
    """估算单条目的平均字节（含序列化缩进/分隔符近似）。"""
    if not lst:
        return 20.0
    if isinstance(lst[0], str):
        samples = lst[-5:] if len(lst) >= 5 else lst
        return sum(len(json.dumps(x, ensure_ascii=False).encode("utf-8")) for x in samples) / len(samples)
    # 对象列表（帧/种子）：用尾部条目序列化均值
    tail = lst[-3:] if len(lst) >= 3 else lst
    K = len(tail)
    return max(1.0, (len(json.dumps(tail, ensure_ascii=False).encode("utf-8")) - 2) / K)


def _compute_budget(data, factor=OVERGEN):
    """逐列表字节预算。

    每个列表按其自身条目字节大小，把「(目标缺口 / 列表数) * 过量系数」换算成
    该列表专属的目标条数。这样即使同文件内各列表条目大小差异悬殊（如 atmosphere
    短语 ~100B vs entities ~12B），短条目列表也能获得足够条数达到目标体积，
    长条目列表不会因单一平均值被低估而欠生成。

    factor 可放大（重试时用），补偿「生成条目比现有条目更短」导致的字节缺口。

    返回 (budget: {path: per_list_count}, num_lists)。
    """
    refs = {}
    _collect_lists(data, "", refs)
    num_lists = len(refs)
    if num_lists == 0:
        return {}, 0
    cur = estimate_bytes(data)
    need = max(0.0, TARGET_BYTES - cur)
    budget = {}
    for p, lst in refs.items():
        avg = _list_avg_entry_bytes(lst)
        # 该列表专属字节份额（等份额分配，兼顾广度：小列表也获得同等生长机会）
        want_bytes = (need / num_lists) * factor
        per = int(want_bytes / avg) if avg > 0 else 0
        per = max(0, min(HARD_CAP, per))
        # 单列表生成体积安全上限（≈8MB），防止大体积对象列表（seed 字典）撑爆内存
        per = min(per, 8_000_000 // max(1, int(avg)))
        budget[p] = per
    return budget, num_lists


def expand_file(path, bank):
    if bank == "personality_tags":
        return expand_personality_tags(path)
    data = load_json(path)          # 原始数据（_expand 不修改 data）
    best = None
    # 重试：首次用基准过量系数；若因「生成条目比现有更短」而欠生成，
    # 则放大系数重试（最多 4 次），直到达到目标的 95% 或尽力而为。
    for attempt in range(4):
        f = OVERGEN * (1.7 ** attempt)
        rng = random.Random(SEED_BASE + djb2(bank) + attempt * 1000003)
        budget, _ = _compute_budget(data, f)
        new_data, meta = _expand(data, bank, "", "", rng, budget)
        trim_to_target(new_data, meta, TARGET_BYTES)
        sz = estimate_bytes(new_data)
        if best is None or sz > best[0]:
            best = (sz, new_data)
        if sz >= TARGET_BYTES * 0.95:
            break
    save_json(path, best[1])
    return best[0], {}


# 供 run.py 调用：批量处理一组 (path, bank)
def run_batch(items):
    results = []
    for path, bank in items:
        before = os.path.getsize(path)
        after, meta = expand_file(path, bank)
        results.append((bank, before, after, sum(m["gen"] for m in meta.values())))
    return results
