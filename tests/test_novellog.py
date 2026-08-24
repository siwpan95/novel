# -*- coding: utf-8 -*-
"""
test_novellog.py —— 小说生成任务日志测试（与 pipelog/genlog 同构）
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PROJ_ROOT = _HERE.parent
if str(_PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT))

from novellog import PipelineLog  # noqa: E402


def test_novellog_append_and_read(tmp_path: Path):
    log = PipelineLog(tmp_path / "pipeline.log")
    log.append("run_start", run_id="r1", mode="scene", target_chars=20000, seed=42)
    log.append("stage_done", stage="generate", run_id="r1", output="out.txt")
    entries = log.read()
    assert len(entries) == 2
    assert entries[0]["type"] == "run_start" and entries[0]["seq"] == 1
    assert entries[1]["stage"] == "generate"


def test_novellog_seq_continues(tmp_path: Path):
    path = tmp_path / "p.log"
    PipelineLog(path).append("run_start", run_id="r1")
    e = PipelineLog(path).append("run_end", run_id="r1", ok=True)
    assert e["seq"] == 2


def test_novellog_empty_when_no_file(tmp_path: Path):
    assert PipelineLog(tmp_path / "missing.log").read() == []
