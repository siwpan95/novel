# -*- coding: utf-8 -*-
"""storyline.py Phase2 解耦：A/B/C 三线 POV 与汇聚点改从 JSON 加载。"""
import re
import sys
from pathlib import Path

# 2026-09-23 去本地化：目标文件与导入根改由本文件位置推导（原 G:\novel 硬编码已不存在）
_TOOLS_DIR = Path(__file__).resolve().parent   # novel_generator/tools/
_LIB_ROOT = _TOOLS_DIR.parent                  # novel_generator/
_REPO_ROOT = _LIB_ROOT.parent                  # 仓根（含 novel_generator 包）
sys.path.insert(0, str(_REPO_ROOT))
p = str(_LIB_ROOT / "engine" / "storyline.py")
s = open(p, encoding="utf-8").read()

# 1) imports
assert "import json" not in s and "import os" not in s
s = s.replace("import random\n", "import random\nimport json\nimport os\n", 1)

# 2) 模块级加载器（插在 class ArcPhase 之前）
loader = (
    "# POV 编排内容（选角/事件脊梁）已外置到 word_banks/narrative/，\n"
    "# 便于维护与扩展；此处统一加载。\n"
    "_POV_CONF_DIR = os.path.join(\n"
    "    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),\n"
    "    'word_banks', 'narrative')\n"
    "def _load_pov_json(name):\n"
    "    with open(os.path.join(_POV_CONF_DIR, name), encoding='utf-8') as _f:\n"
    "        return json.load(_f)\n"
    "_POV_ASSIGNMENT = _load_pov_json('pov_assignment.json')\n"
    "_EVENT_SPINE = _load_pov_json('event_spine.json')\n"
    "\n"
)
s = s.replace("class ArcPhase", "\n" + loader + "class ArcPhase", 1)

# 3) default_board A/B/C -> 从 JSON 读取
old_abc = re.compile(r"# A-plot: 林朔.*?\n        # D-plot: 世界NPC线", re.DOTALL)
assert old_abc.search(s), "A/B/C block 未匹配"
new_abc = (
    "# A/B/C 三线：POV 角色与编排参数来自 pov_assignment.json（默认林朔/唐川/白夜），\n"
    "# 作者可改 JSON 调整选角与编排，无需动代码。B-plot 世界名动态取首个启用世界。\n"
    "_ROLE_TYPE = {'a_plot': StorylineType.A_PLOT, 'b_plot': StorylineType.B_PLOT, 'c_plot': StorylineType.C_PLOT}\n"
    "for _rk in ('a_plot', 'b_plot', 'c_plot'):\n"
    "    _r = _POV_ASSIGNMENT['plot_roles'][_rk]\n"
    "    _world_name = _r.get('world_name') or (b_world if _rk == 'b_plot' else '')\n"
    "    board.add_line(Storyline(\n"
    "        line_id=_r['line_id'],\n"
    "        line_type=_ROLE_TYPE[_rk],\n"
    "        label=_r['label'],\n"
    "        world_name=_world_name,\n"
    "        pov_characters=list(_r['pov_characters']),\n"
    "        default_tone=_r['default_tone'],\n"
    "        tension_baseline=_r['tension_baseline'],\n"
    "        priority=_r['priority'],\n"
    "        beat_interval=_r['beat_interval'],\n"
    "        can_intersect_with=list(_r['can_intersect_with']),\n"
    "        preferred_ops=list(_r['preferred_ops']),\n"
    "        narrative_themes=list(_r['narrative_themes']),\n"
    "    ))\n"
    "\n"
    "        # D-plot: 世界NPC线"
)
s = old_abc.sub(new_abc, s, count=1)

# 4) default_for_wanjie 汇聚点 -> 从 event_spine.json 读取
old_conv = re.compile(r"# 汇聚点1：苍云山——碎片争夺战.*?\n        return mgr\n", re.DOTALL)
assert old_conv.search(s), "convergence block 未匹配"
new_conv = (
    "# 汇聚点来自 event_spine.json（默认万界归墟三汇聚），作者可改 JSON 调整。\n"
    "        _phase_map = {_p.name: _p for _p in ArcPhase}\n"
    "        for _cp in _EVENT_SPINE['convergence_points']:\n"
    "            mgr.add_convergence(ConvergencePoint(\n"
    "                convergence_id=_cp['convergence_id'],\n"
    "                label=_cp['label'],\n"
    "                line_ids=list(_cp['line_ids']),\n"
    "                trigger_phase=_phase_map[_cp['trigger_phase']],\n"
    "                trigger_progress_min=_cp['trigger_progress_min'],\n"
    "                shared_event_description=_cp['shared_event_description'],\n"
    "                world_name=_cp['world_name'],\n"
    "                pov_sequence=list(_cp['pov_sequence']),\n"
    "                tension_boost=_cp['tension_boost'],\n"
    "                one_shot=_cp.get('one_shot', True),\n"
    "            ))\n"
    "\n"
    "        return mgr\n"
)
s = old_conv.sub(new_conv, s, count=1)

open(p, "w", encoding="utf-8").write(s)
print("storyline.py 已改写")

# 验证
import importlib
import novel_generator.engine.storyline as SL
importlib.reload(SL)
b = SL.StoryBoard.default_board(seed=123)
print("lines:", list(b._lines.keys()))
print("a pov:", b.line("a_lin_shuo").pov_characters,
      " b pov:", b.line("b_tang_chuan").pov_characters,
      " c pov:", b.line("c_agents").pov_characters)
print("b world_name:", b.line("b_tang_chuan").world_name)
m = SL.NarrativeArcManager.default_for_wanjie()
print("convergence points:", [c.convergence_id for c in m._convergence_points])
print("conv1 pov_sequence:", m._convergence_points[0].pov_sequence,
      " phase:", m._convergence_points[0].trigger_phase)
