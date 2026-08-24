# -*- coding: utf-8 -*-
"""内容库清单生成器。

扫描 word_banks/ 下所有 JSON 词库，递归统计每个库的：
  - 分类（所在子目录）
  - 顶层/嵌套键及其条目数
  - 总条目数
并写入 word_banks/content_manifest.json，供文档与工具消费。

用法：
    python build_manifest.py

注意：content_manifest.json 自身是 JSON，会被自动排除在本次扫描之外，
重复运行不会污染清单。
"""
import json
import glob
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELF_NAME = "content_manifest.json"


def iter_list_counts(node, prefix=""):
    """递归收集所有「列表型节点」的条目数，键路径用 / 连接。"""
    out = {}
    if isinstance(node, list):
        label = prefix or "(root)"
        out[label] = len(node)
    elif isinstance(node, dict):
        for k, sub in node.items():
            if isinstance(sub, list):
                out[k] = len(sub)
            elif isinstance(sub, dict):
                for kk, n in iter_list_counts(sub, k).items():
                    out[f"{k}/{kk}"] = n
    return out


def main():
    banks = []
    total_all = 0
    for fp in sorted(glob.glob(str(HERE / "**" / "*.json"), recursive=True)):
        p = Path(fp)
        if p.name == SELF_NAME:
            continue
        if ".backup_originals" in p.parts:
            continue
        rel = p.relative_to(HERE)
        data = json.load(open(p, encoding="utf-8"))
        desc = data.get("description") if isinstance(data, dict) else None
        keys = iter_list_counts(data)
        total = sum(keys.values())
        total_all += total
        banks.append({
            "path": str(rel).replace("\\", "/"),
            "category": rel.parts[0],
            "description": desc if isinstance(desc, str) else None,
            "keys": keys,
            "total_entries": total,
        })

    manifest = {
        "generated_by": "build_manifest.py",
        "summary": {
            "bank_count": len(banks),
            "total_entries": total_all,
            "categories": sorted({b["category"] for b in banks}),
        },
        "banks": banks,
    }
    out = HERE / SELF_NAME
    json.dump(manifest, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"写入 {out}")
    print(f"  词库数: {len(banks)}  总条目数: {total_all}")
    for c in manifest["summary"]["categories"]:
        cat_total = sum(b["total_entries"] for b in banks if b["category"] == c)
        print(f"  {c:12s} {cat_total}")


if __name__ == "__main__":
    main()
