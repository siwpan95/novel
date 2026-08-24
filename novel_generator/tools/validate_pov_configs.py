# -*- coding: utf-8 -*-
"""POV 配置词库校验器（Phase 3 验收：JSON 配置入口与校验）。

校验 word_banks/narrative/ 下 7 个 POV 词库的结构完整性与跨库一致性：
  - pov_types / pov_lenses / interiority / info_asymmetry
  - event_spine / pov_assignment / pov_timeline

作者修改这些 JSON 后，运行本脚本即可确认配置自洽，避免运行时因
缺字段/错角色导致生成异常。退出码非 0 表示存在错误。

用法：
    python tools/validate_pov_configs.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NB = os.path.abspath(os.path.join(HERE, "..", "word_banks", "narrative"))

REQUIRED = {
    "pov_types": {"first_person", "third_limited", "omniscient", "second_person",
                  "unreliable", "deep_pov", "objective_data"},
    "pov_lenses": {"by_role", "by_personality"},
    "interiority": {"soliloquy", "sensory_introspection", "emotion_flow"},
    "info_asymmetry": {"same_event_stances", "cognitive_gap_hooks"},
    "event_spine": {"timeline_events", "convergence_points"},
    "pov_assignment": {"plot_roles", "role_pool_by_attribute"},
    "pov_timeline": {"convergence_defaults", "anti_chaos", "arc_stage_thresholds", "beat_intervals"},
}

ERRORS = []


def _err(msg):
    ERRORS.append(msg)


def _load(name):
    p = os.path.join(NB, name + ".json")
    if not os.path.exists(p):
        _err("缺失文件: %s" % name)
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception as e:
        _err("JSON 解析失败 %s: %s" % (name, e))
        return None


def _nonempty_strlist(d, key, where):
    v = d.get(key)
    if not isinstance(v, list) or not v:
        _err("%s.%s 应为非空列表" % (where, key))
        return []
    if not all(isinstance(x, str) and x for x in v):
        _err("%s.%s 含非字符串或空条目" % (where, key))
    return v


def main():
    banks = {n: _load(n) for n in REQUIRED}

    # 1) 结构校验
    for name, d in banks.items():
        if d is None:
            continue
        missing = REQUIRED[name] - set(d.keys())
        if missing:
            _err("%s 缺顶层键: %s" % (name, sorted(missing)))

    # 2) 跨库一致性
    banks.get("pov_types")
    pl = banks.get("pov_lenses")
    ia = banks.get("info_asymmetry")
    es = banks.get("event_spine")
    pa = banks.get("pov_assignment")
    ptl = banks.get("pov_timeline")

    # pov_lenses.by_role / by_personality 的 header/footer 模板
    if pl:
        for grp in ("by_role", "by_personality"):
            for role, spec in (pl.get(grp) or {}).items():
                if not isinstance(spec, dict):
                    _err("pov_lenses.%s.%s 应为对象" % (grp, role))
                    continue
                for fld in ("header", "footer", "style", "adds"):
                    if fld not in spec:
                        _err("pov_lenses.%s.%s 缺字段 %s" % (grp, role, fld))

    # info_asymmetry 的 stance.role 必须落在 pov_lenses.by_role 中
    if ia and pl:
        valid_roles = set((pl.get("by_role") or {}).keys())
        for ev in (ia.get("same_event_stances") or []):
            for st in ev.get("stances", []):
                r = st.get("role")
                if r not in valid_roles:
                    _err("info_asymmetry 立场 role=%r 不在 pov_lenses.by_role 中" % r)

    # event_spine.timeline_events 字段
    if es:
        for ev in (es.get("timeline_events") or []):
            for fld in ("type", "id", "name", "trigger_time"):
                if fld not in ev:
                    _err("event_spine.timeline_events 缺字段 %s" % fld)
        for cp in (es.get("convergence_points") or []):
            for fld in ("convergence_id", "label", "line_ids", "trigger_phase", "pov_sequence"):
                if fld not in cp:
                    _err("event_spine.convergence_points 缺字段 %s" % fld)

    # pov_assignment.plot_roles 字段 + 角色名非空
    if pa:
        for rk, spec in (pa.get("plot_roles") or {}).items():
            for fld in ("line_id", "label", "pov_characters", "beat_interval", "priority"):
                if fld not in spec:
                    _err("pov_assignment.plot_roles.%s 缺字段 %s" % (rk, fld))
            if not (spec.get("pov_characters")):
                _err("pov_assignment.plot_roles.%s.pov_characters 为空" % rk)

    # pov_timeline.beat_intervals 键应是 a/b/c/d_plot
    if ptl:
        bi = ptl.get("beat_intervals") or {}
        for k in bi:
            if k not in ("a_plot", "b_plot", "c_plot", "d_plot"):
                _err("pov_timeline.beat_intervals 非法键: %s" % k)
        ac = ptl.get("anti_chaos") or {}
        if "forbid_consecutive_same_pov" not in ac:
            _err("pov_timeline.anti_chaos 缺 forbid_consecutive_same_pov")

    # 报告
    print("POV 配置词库校验")
    print("=" * 48)
    for name in REQUIRED:
        d = banks.get(name)
        if d is None:
            print("  [缺失] %-16s" % name)
        else:
            print("  [OK]   %-16s 顶层键 %d" % (name, len(d)))
    print("=" * 48)
    if ERRORS:
        print("发现 %d 处问题：" % len(ERRORS))
        for e in ERRORS:
            print("  - " + e)
        return 1
    print("全部通过：7 个 POV 词库结构完整且跨库一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
