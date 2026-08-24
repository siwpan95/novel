# -*- coding: utf-8 -*-
"""题材与内容生成池（数据层 / 仅加载）。

设计：所有后缀族、题材术语种子、句模板等内容已迁至同级 ``pools_genre.json``，
便于后期维护（改内容不必动逻辑）。本模块只负责把 JSON 加载为模块级属性，
对外暴露的接口与改造前完全一致（``PG.VOICE_TEMPLATES`` 等）。

内容包括：
- 后缀族：ITEM_SUFFIX / SECT_SUFFIX / ENTITY_SUFFIX / LOC_SUFFIX
- 题材真实术语种子：GENRE_CORES
- 词汇辅助池：ADJ_STEMS / TERRAIN_CORES / LANDMARK_CORES / BODY_NOUNS /
  EXTRA_SURNAMES / GIVEN_NAME_CHARS / PERSONALITY_EXTRA
- 句模板：CHAPTER_TEMPLATES / HOOK_TEMPLATES / REVEAL_TEMPLATES /
  SHORT_TEMPLATES / SINGLE_CHAR_TEMPLATES / CONNECTOR_TEMPLATES /
  INCOMPLETE_TEMPLATES / SELF_CORRECT_TEMPLATES / ATMOSPHERE_TEMPLATES /
  OPENING_TEMPLATES / BATTLE_TEMPLATES / VOICE_TEMPLATES /
  SENSE_FRAGMENT_TEMPLATES
- 体感/感官扩展字典：BODY_REACTION_EXPAND / SENSE_FALLBACK_EXPAND
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_HERE, "pools_genre.json"), encoding="utf-8") as _f:
    _DATA = json.load(_f)

for _name, _val in _DATA.items():
    globals()[_name] = _val
