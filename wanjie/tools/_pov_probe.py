# -*- coding: utf-8 -*-
"""POV 解耦回归探针：给定 seed 跑一段生成，输出拼接文本 + sha256。
用于 Phase2 重构前后行为等价验证（应逐字一致）。
"""
import sys
import hashlib
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from wanjie.engine.word_bank import WordBank
from wanjie.engine.plot_state import PlotState
from wanjie.engine.voice_engine import VoiceEngine
from wanjie.engine.world_state import WorldStateManager
from wanjie.engine.timeline import Timeline
from wanjie.engine.storyline import StoryBoard, StoryBeat
from wanjie.engine.integrated_chapter_generator import IntegratedChapterGenerator
from wanjie.engine.scene_director import SceneDirector
from wanjie.engine.wordcount_director import DEFAULT_WC_CONFIG


def run(seed=123, target=6000, worlds=None):
    worlds = worlds or ['归墟', '武侠·苍云之殇', '末日废土']
    wb = WordBank(seed=seed)
    ps = PlotState()
    VoiceEngine(wb, ps, seed=seed)
    wm = WorldStateManager(wb, seed=seed)
    for w in worlds:
        wm.load_world(w)
    timeline = Timeline.default_timeline(seed=seed)
    storyboard = StoryBoard.default_board(seed=seed)
    ig = IntegratedChapterGenerator(wb, ps, seed=seed)
    cfg = dict(DEFAULT_WC_CONFIG)
    cfg.update(save_every=10, log_every=100, min_passage_chars=200, max_passage_chars=1200)
    od = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output")
    director = SceneDirector(ig, ps, wm, timeline, storyboard, cfg, od, seed=seed)
    total = 0
    pn = 0
    max_p = max(50, (target // cfg['min_passage_chars']) * 3)
    buf = []
    while total < target and pn < max_p:
        wm.tick()
        fired = timeline.tick(wm.global_time, director._build_world_state_snapshot())
        for ev in fired:
            if str(ev.scope) == 'EventScope.WORLD' and 'world' in ev.payload:
                wm.unlock_world(ev.payload['world'])
        beats = storyboard.tick(pn)
        if not beats:
            beats = [StoryBeat(line_id='a_lin_shuo', time_step=pn, beat_type='primary', pov_char='林朔')]
        rem = target - total
        if rem < cfg['min_passage_chars']:
            break
        text = director._render_section(beats, fired, rem)
        total += len(text)
        pn += 1
        buf.append(text)
        director._chars.tick()
    full = "\n\n".join(buf)
    return full


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 123
    full = run(seed=seed)
    h = hashlib.sha256(full.encode("utf-8")).hexdigest()
    print("seed=%d chars=%d sha256=%s" % (seed, len(full), h))
