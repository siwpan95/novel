# -*- coding: utf-8 -*-
"""共享槽位池（数据层 / 仅加载）。

设计：所有中文词素、共享池内容已迁至同级 ``pools_common.json``，便于后期维护
（改内容不必动逻辑）。本模块只负责把 JSON 加载为模块级属性，并重建
``SHARED_POOLS`` 映射，对外暴露的接口与改造前完全一致：

    MODIFIERS / ELEMENTS / BEASTS / MATERIALS / PLACES / ACTIONS / EMOTIONS /
    BODY_PARTS / SUBJECTS / COLORS / WEATHER / FACTIONS / TITLES / WEAPON_TYPES /
    TECH_SUFFIX / TECH_VERB / REALM_WORDS / NOUNS / THINGS / PULSES /
    SENSE_FRAGMENTS / NARRATIVE_TEMPLATES / SHARED_POOLS

消费方（engine 等）继续按 ``PC.<NAME>`` 引用，逻辑零改动。
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_HERE, "pools_common.json"), encoding="utf-8") as _f:
    _DATA = json.load(_f)

_POOLS = _DATA["pools"]
_SHARED_REF = _DATA["shared_pools"]

# 把每个池暴露为模块级属性（与原 Python 字面量等价，顺序由 JSON 决定）
for _name, _val in _POOLS.items():
    globals()[_name] = _val

# 重建 SHARED_POOLS（供 gen_phrases 按槽位名取池）
SHARED_POOLS = {}
for _field, _ref in _SHARED_REF.items():
    if isinstance(_ref, list):
        # 形如 ["SENSE_FRAGMENTS", "visual"]：嵌套取子键
        _v = _POOLS
        for _k in _ref:
            _v = _v[_k]
        SHARED_POOLS[_field] = _v
    else:
        SHARED_POOLS[_field] = _POOLS[_ref]
