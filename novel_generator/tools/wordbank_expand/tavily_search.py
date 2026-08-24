#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tavily 联网检索助手（零第三方依赖，仅用标准库）。

供「词库每日联网扩充」自动化调用：从 Tavily API 取真实语料。
密钥读取顺序：环境变量 TAVILY_API_KEY → 同目录 tavily.key 文件。
用法:
    python tavily_search.py "<查询>" [max_results]
输出:
    JSON {"results":[{"title","url","content"}]} 或 {"error":"..."}
"""
import sys
import os
import json
import urllib.request
import urllib.error

KEY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tavily.key")
API_URL = "https://api.tavily.com/search"


def get_key():
    if os.environ.get("TAVILY_API_KEY"):
        return os.environ["TAVILY_API_KEY"].strip()
    try:
        with open(KEY_PATH, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def search(query, max_results=8, topic="general"):
    key = get_key()
    if not key:
        return {"error": "Tavily API key 未配置（环境变量 TAVILY_API_KEY 或 tavily.key 均缺失）"}
    payload = {
        "api_key": key,
        "query": query,
        "max_results": int(max_results),
        "search_depth": "advanced",
        "topic": topic,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        return {"error": f"HTTP {e.code}: {body[:500]}"}
    except Exception as e:  # 超时 / 无网络等
        return {"error": f"{type(e).__name__}: {e}"}
    results = []
    for r in out.get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
        })
    return {"results": results}


if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print(json.dumps({"error": "usage: tavily_search.py <query> [max_results]"},
                         ensure_ascii=False))
        sys.exit(2)
    q = sys.argv[1]
    mr = sys.argv[2] if len(sys.argv) > 2 else "8"
    try:
        mr = int(mr)
    except Exception:
        mr = 8
    out = search(q, mr)
    print(json.dumps(out, ensure_ascii=False))
