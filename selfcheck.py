#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""novel 无头自检：词库模板渲染（确定性）+ 时间轴事件推进。

本仓引擎以「依赖 + 继承」方式复用 PyPI 内核 ``novel-generator``；本机
``.venv`` 未安装该包（``pip install -e .`` 才会拉入），按任务约定把同级仓
``G:\\repos\\novel-generator\\src`` 加入 sys.path 即可，不改项目、不装依赖。

不 import ``main.py`` / ``unified_engine.py``：前者会 chdir、建日志并启动长文
生成，都属于入口级副作用。这里只取纯引擎模块：

1. ``WordBank`` + ``TemplateEngine``（``wanjie.engine``）：索引取值、上下文变量、
   ``,N`` 多选去重、同 seed 可复现；
2. ``Timeline``（``wanjie.engine.timeline``）：一次性事件、条件事件、可重复事件
   的冷却推进，以及默认事件脊梁（``word_banks/narrative/event_spine.json``）可加载。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True          # 不在项目里留 .pyc
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
KERNEL_SRC = ROOT.parent / "novel-generator" / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(KERNEL_SRC))


class CheckError(RuntimeError):
    pass


def check(condition, message):
    if not condition:
        raise CheckError(message)


def check_template(WordBank, TemplateEngine):
    bank = WordBank(seed=42)
    names = bank.load("names")
    check(isinstance(names.get("surnames"), list) and names["surnames"],
          "names 词库缺少 surnames")
    surnames = names["surnames"]

    engine = TemplateEngine(bank)
    check(engine.fill("{{names.surnames[0]}}") == surnames[0],
          "模板索引取值 {{bank.key[0]}} 未返回词库首项")
    check(engine.fill("{{主角}}在{{names.surnames[0]}}家", {"主角": "林朔"})
          == f"林朔在{surnames[0]}家", "模板上下文变量替换失败")
    check(engine.fill("{{unknown_placeholder}}") == "{{unknown_placeholder}}",
          "无法解析的占位符应原样保留")

    multi = engine.fill("{{names.surnames,3}}")
    parts = multi.split("、")
    check(len(parts) == 3, f"{{{{names.surnames,3}}}} 未返回 3 项：{multi!r}")
    check(len(set(parts)) == 3, f"多选未去重：{multi!r}")

    template = "{{names.surnames}}{{names.given_name_chars}}"
    bank_a, bank_b = WordBank(seed=2026), WordBank(seed=2026)
    out_a = TemplateEngine(bank_a).fill(template)
    out_b = TemplateEngine(bank_b).fill(template)
    check(out_a == out_b, f"同 seed 模板渲染不可复现：{out_a!r} != {out_b!r}")
    check(len(out_a) >= 2, f"渲染结果过短：{out_a!r}")


def check_timeline(Timeline):
    timeline = Timeline(seed=1)
    timeline.add_world_event("wake", "觉醒", trigger_time=3)
    timeline.add_world_event("danger", "危机", condition="danger >= 7")

    check(timeline.tick(2) == [], "定时事件在触发时刻之前就触发了")
    fired = timeline.tick(3)
    check([event.event_id for event in fired] == ["wake"],
          f"定时事件触发错误：{[e.event_id for e in fired]!r}")
    check(timeline.tick(3) == [], "不可重复事件被重复触发")

    fired = timeline.tick(4, {"danger": 8})
    check("danger" in [event.event_id for event in fired],
          "条件事件在条件满足时未触发")
    check(timeline.tick(5, {"danger": 1}) == [],
          "条件事件在条件不满足时仍触发")

    timeline.add_world_event("pulse", "脉冲", trigger_time=1, repeatable=True, cooldown=2)
    check([event.event_id for event in timeline.tick(1)] == ["pulse"],
          "可重复事件首次未触发")
    check(timeline.tick(2) == [], "可重复事件在冷却期内仍触发")
    check([event.event_id for event in timeline.tick(3)] == ["pulse"],
          "可重复事件冷却结束后未再次触发")

    default = Timeline.default_timeline(seed=42)
    event_count = len(default._events)
    check(event_count > 0, "默认事件脊梁为空（event_spine.json 未加载）")
    default_fired = []
    for step in range(0, 61):
        default_fired.extend(default.tick(step))
    check(default_fired, "默认时间轴在 60 步内没有任何事件触发")
    return event_count, len(default_fired)


def main():
    check(KERNEL_SRC.is_dir(), f"找不到内核同级仓：{KERNEL_SRC}")
    from wanjie.engine.word_bank import WordBank
    from wanjie.engine.template import TemplateEngine
    from wanjie.engine.timeline import Timeline

    check_template(WordBank, TemplateEngine)
    event_count, fired_count = check_timeline(Timeline)
    print(
        "selfcheck ok: word bank + template rendering (index/vars/3-unique/seeded reproducible) "
        "+ timeline progression (one-shot/condition/cooldown) + default spine (%d events, %d fired)"
        % (event_count, fired_count)
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - 自检入口需要把任何失败转成 FAIL + 退出码 1
        print(f"FAIL: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
