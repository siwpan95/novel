# -*- coding: utf-8 -*-
"""词库批量扩充主控。

- 先将原始 JSON 备份到 word_banks/.backup_originals/（仅首次）；
- 逐文件扩充到目标体积（默认 1.1MB），已达标则跳过（幂等）；
- 完成后做 JSON 合法性 + 列表内去重自检，并打印报告。
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import engine  # noqa: E402

WB = os.path.abspath(os.path.join(HERE, "..", "..", "word_banks"))
BACKUP = os.path.join(WB, ".backup_originals")
TARGET = engine.TARGET_BYTES
SKIP_IF_AT_LEAST = 1_050_000  # 已接近目标则跳过，保证幂等
# 生成物索引/manifest 不属于内容词库，扩充会使其计数与实际脱钩；交给 #8 重建
SKIP_FILES = {"content_manifest.json"}
# POV 配置/目录类词库（dict-of-dicts，非"内容池"），由 engine 直接消费，
# 扩展工具按列表逻辑处理会破坏其结构；跳过以保结构完整。
SKIP_POV_CONFIG = {
    "pov_types.json", "pov_lenses.json", "interiority.json", "info_asymmetry.json",
    "event_spine.json", "pov_assignment.json", "pov_timeline.json",
    # dict-of-dicts 配置库（triggers/lenses/scenes、flavours），
    # 非"内容池"，扩容器按列表逻辑处理会破坏结构；跳过以保结构完整。
    "rashomon.json", "voice_flavours.json",
}


def backup_once():
    if os.path.isdir(BACKUP) and os.listdir(BACKUP):
        return
    os.makedirs(BACKUP, exist_ok=True)
    for root, _, files in os.walk(WB):
        if ".backup_originals" in root:
            continue
        for f in files:
            if f.endswith(".json"):
                src = os.path.join(root, f)
                rel = os.path.relpath(src, WB)
                dst = os.path.join(BACKUP, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
    print("已备份原始词库到 .backup_originals/")


def dedup_check(path):
    """返回 (total_lists, lists_with_dupes, max_dup)。"""
    d = json.load(open(path, encoding="utf-8"))
    bad = 0
    maxdup = 0

    def walk(v):
        nonlocal bad, maxdup
        if isinstance(v, dict):
            for kk, vv in v.items():
                walk(vv)
        elif isinstance(v, list):
            if v and isinstance(v[0], str):
                seen = set()
                dup = 0
                for s in v:
                    if s in seen:
                        dup += 1
                    else:
                        seen.add(s)
                if dup:
                    bad += 1
                    maxdup = max(maxdup, dup)
            elif v and isinstance(v[0], dict):
                for item in v:
                    walk(item)

    walk(d)
    return bad, maxdup


def main():
    backup_once()
    files = []
    for root, _, fs in os.walk(WB):
        if ".backup_originals" in root:
            continue
        for f in sorted(fs):
            if f.endswith(".json") and f not in SKIP_FILES and f not in SKIP_POV_CONFIG:
                files.append(os.path.join(root, f))
    print("待处理文件数：%d，目标体积 %.2f MB/文件\n" % (len(files), TARGET / 1024 / 1024))

    total_before = total_after = 0
    skipped = 0
    failures = []
    for p in files:
        bank = os.path.basename(p)[:-5]
        before = os.path.getsize(p)
        total_before += before
        if before >= SKIP_IF_AT_LEAST:
            print("  跳过(已达标) %-42s %6.1f KB" % (bank, before / 1024))
            total_after += before
            skipped += 1
            continue
        try:
            after, meta = engine.expand_file(p, bank)
        except Exception as e:
            failures.append((bank, repr(e)))
            total_after += before
            print("  !! 失败 %-42s %s" % (bank, e))
            continue
        total_after += after
        # 去重自检
        bad, maxdup = dedup_check(p)
        flag = "  [去重异常!]" if bad else ""
        print("  扩充 %-42s %6.1f -> %6.1f KB%s" % (
            bank, before / 1024, after / 1024, flag))

    print("\n==== 汇总 ====")
    print("文件数：%d（跳过 %d，失败 %d）" % (len(files), skipped, len(failures)))
    print("总体积：%.2f MB -> %.2f MB" % (total_before / 1024 / 1024, total_after / 1024 / 1024))
    if failures:
        print("失败文件：")
        for b, e in failures:
            print("  - %s: %s" % (b, e))
    print("备份目录：%s" % BACKUP)


if __name__ == "__main__":
    main()
