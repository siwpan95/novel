#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《万界归墟》GUI 服务 —— Flask + SSE 实时流式生成。

工程参考：同类电台服务端（waitress 生产服务器 / 健康检查 / CORS / 优雅关闭；原宿主目录已失效）

启动: python gui/app.py
访问: http://localhost:5000
"""
from __future__ import annotations
import atexit
import json
import logging
import logging.handlers
import os
import shutil
import signal
import sys
import threading
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify, Response, session

# 配置
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "127.0.0.1"
HTTP_PORT = 5000
OUTPUT_DIR = os.path.join(_BASE, "output")
LOG_FILE = os.path.join(_BASE, "gui_server.log")

from wanjie.engine.word_bank import WordBank
from wanjie.engine.plot_state import PlotState
from wanjie.engine.world_state import WorldStateManager
from wanjie.engine.timeline import Timeline
from wanjie.engine.storyline import StoryBoard, StoryBeat
from wanjie.engine.scene_director import SceneDirector
from wanjie.engine.integrated_chapter_generator import IntegratedChapterGenerator
from wanjie.engine.voice_engine import VoiceEngine
from wanjie.engine.wordcount_director import PRESETS, PRESET_CN, DEFAULT_WC_CONFIG

# ── Flask 初始化 ──
app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

# ── 日志 ──
_logger = logging.getLogger('novel.gui')
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    _fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, encoding='utf-8', maxBytes=5 * 1024 * 1024, backupCount=3)
    _fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    _logger.addHandler(_fh)

# ── 全局生成状态 ──
_gen_lock = threading.Lock()
_gen_state = {
    'running': False,
    'target_chars': 0,
    'current_chars': 0,
    'passage_no': 0,
    'elapsed': 0.0,
    'beat_dist': {},
    'active_world': '归墟',
    'intersections': 0,
    'error': None,
    'started_at': None,
}
_gen_thread = None
_server_started_at = time.time()


def _uptime() -> float:
    return time.time() - _server_started_at


# ── 优雅关闭 ──
def _shutdown():
    with _gen_lock:
        _gen_state['running'] = False
    _logger.info('GUI 服务已停止')


atexit.register(_shutdown)
signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))


# ===================================================================
# 页面路由
# ===================================================================
@app.route('/')
def index():
    return render_template('index.html')


# ===================================================================
# API: 健康检查
# ===================================================================
@app.route('/api/health')
def api_health():
    disk = {'free_gb': None}
    try:
        du = shutil.disk_usage(os.path.dirname(OUTPUT_DIR))
        disk = {'free_gb': round(du.free / 1e9, 2)}
    except Exception:
        pass

    return jsonify({
        'ok': True,
        'running': _gen_state['running'],
        'uptime': round(_uptime()),
        'disk': disk,
        'engine': {
            'target': _gen_state['target_chars'],
            'current': _gen_state['current_chars'],
            'passages': _gen_state['passage_no'],
            'intersections': _gen_state['intersections'],
            'world': _gen_state['active_world'],
        },
    })


# ===================================================================
# API: 生成控制
# ===================================================================
@app.route('/api/generate')
def api_generate():
    """SSE 端点——流式推送生成进度和文本。"""
    target = min(int(request.args.get('target', 2000)), 200_000)
    seed = int(request.args.get('seed', 0))
    if seed == 0:
        seed = int(time.time() * 1000) % (2 ** 31)

    # 已在生成中 → 拒绝
    with _gen_lock:
        if _gen_state['running']:
            def _busy():
                yield f'data: {_event("error", {"msg": "已有生成任务在运行，请等待完成或刷新页面"})}\n\n'
            return Response(_busy(), mimetype='text/event-stream',
                            headers={'Cache-Control': 'no-cache'})

        _gen_state['running'] = True
        _gen_state['target_chars'] = target
        _gen_state['current_chars'] = 0
        _gen_state['passage_no'] = 0
        _gen_state['elapsed'] = 0.0
        _gen_state['beat_dist'] = {}
        _gen_state['active_world'] = '归墟'
        _gen_state['intersections'] = 0
        _gen_state['error'] = None
        _gen_state['started_at'] = time.time()

    def generate():
        t0 = time.time()
        try:
            yield f'data: {_event("status", {"msg": "正在初始化引擎…"})}\n\n'

            wb = WordBank(seed=seed)
            ps = PlotState()
            voice = VoiceEngine(wb, ps, seed=seed)
            wm = WorldStateManager(wb, seed=seed)
            for world in ['归墟', '武侠·苍云之殇', '末日废土']:
                wm.load_world(world)
            timeline = Timeline.default_timeline(seed=seed)
            storyboard = StoryBoard.default_board(seed=seed)
            integrated_gen = IntegratedChapterGenerator(wb, ps, seed=seed)

            config = dict(DEFAULT_WC_CONFIG)
            config['save_every'] = 10
            config['log_every'] = 100
            config['min_passage_chars'] = 200
            config['max_passage_chars'] = 1200

            director = SceneDirector(
                integrated_gen, ps, wm, timeline, storyboard,
                config, OUTPUT_DIR, seed=seed,
            )

            yield f'data: {_event("status", {"msg": "开始生成…"})}\n\n'

            # 流式生成
            total = 0
            passage_no = 0
            max_p = max(50, (target // config['min_passage_chars']) * 3)
            buffer = []

            while total < target and passage_no < max_p and _gen_state['running']:
                wm.tick()
                world_snap = director._build_world_state_snapshot()
                fired = timeline.tick(wm.global_time, world_snap)
                for ev in fired:
                    if str(ev.scope) == 'EventScope.WORLD' and 'world' in ev.payload:
                        wm.unlock_world(ev.payload['world'])

                beats = storyboard.tick(passage_no)
                if not beats:
                    beats = [StoryBeat(line_id='a_lin_shuo', time_step=passage_no,
                                       beat_type='primary', pov_char='林朔')]

                remaining = target - total
                if remaining < config['min_passage_chars']:
                    break

                text = director._render_section(beats, fired, remaining)
                n = len(text)
                total += n
                passage_no += 1
                buffer.append(text)

                with _gen_lock:
                    _gen_state['current_chars'] = total
                    _gen_state['passage_no'] = passage_no
                    _gen_state['beat_dist'] = storyboard.line_distribution()
                    _gen_state['intersections'] = len(storyboard._intersection_points)
                    _gen_state['active_world'] = wm._active_world

                beat_info = []
                for b in beats:
                    line = storyboard.line(b.line_id)
                    beat_info.append({
                        'line': line.label if line else b.line_id,
                        'type': b.beat_type,
                        'pov': b.pov_char,
                        'intersects': b.intersects_with,
                    })

                yield f'data: {_event("progress", {
                    "chars": total, "total": target, "passage": passage_no,
                    "progress": round(min(100, total / target * 100), 1),
                    "text": text, "beats": beat_info,
                    "world": wm._active_world,
                    "dist": storyboard.line_distribution(),
                    "intersections": len(storyboard._intersection_points),
                })}\n\n'

                director._chars.tick()
                if passage_no % config['save_every'] == 0:
                    director._ps.state['current_chars'] = total
                    director._ps.state['current_passage'] = passage_no
                    director._ps.save()

            # 保存最终文件
            full = '\n\n'.join(buffer)
            ts = time.strftime('%Y%m%d_%H%M%S')
            out_path = os.path.join(OUTPUT_DIR,
                                    f'万界归墟_GUI_{total}字_{ts}.txt')
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(full)

            with _gen_lock:
                _gen_state['elapsed'] = time.time() - t0
                _gen_state['running'] = False

            yield ('data: ' + _event('complete', {
                'chars': total, 'elapsed': round(_gen_state['elapsed'], 1),
                'intersections': _gen_state['intersections'],
                'path': out_path,
            }) + '\n\n')

        except Exception as e:
            _logger.exception('生成异常')
            with _gen_lock:
                _gen_state['running'] = False
                _gen_state['error'] = str(e)
            yield f'data: {_event("error", {"msg": f"生成异常: {e}"})}\n\n'

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@app.route('/api/stop', methods=['POST'])
def api_stop():
    """停止当前生成任务。"""
    with _gen_lock:
        was_running = _gen_state['running']
        _gen_state['running'] = False
    return jsonify({'ok': True, 'was_running': was_running})


@app.route('/api/status')
def api_status():
    with _gen_lock:
        s = dict(_gen_state)
    s['uptime'] = round(_uptime())
    return jsonify(s)


@app.route('/api/presets')
def api_presets():
    return jsonify({
        '短篇': PRESETS['tiny'],
        '中篇': PRESETS['small'],
        '长篇': PRESETS['book'],
    })


# ===================================================================
# CORS — 仅允许本机 GUI 跨源（非通配符）
# ===================================================================
@app.after_request
def _cors(resp):
    if request.path.startswith('/api/'):
        origin = request.headers.get('Origin', '')
        if origin in ('http://127.0.0.1:5000', 'http://localhost:5000', ''):
            resp.headers['Access-Control-Allow-Origin'] = origin or 'http://127.0.0.1:5000'
            resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return resp


# ===================================================================
# 工具函数
# ===================================================================
def _event(event_type: str, data: dict) -> str:
    return json.dumps({'type': event_type, **data}, ensure_ascii=False)


# ===================================================================
# 启动入口
# ===================================================================
def main():
    print(f'\n{"=" * 55}')
    print(f'  《万界归墟》GUI 棋盘生成器')
    print(f'  控制面板 : http://localhost:{HTTP_PORT}/')
    print(f'  健康检查 : http://localhost:{HTTP_PORT}/api/health')
    print(f'  输出目录 : {OUTPUT_DIR}')
    print(f'  按 Ctrl+C 停止')
    print(f'{"=" * 55}\n')

    try:
        from waitress import serve
        _logger.info('使用 waitress 生产服务器')
        serve(app, host=HOST, port=HTTP_PORT, threads=8, channel_timeout=120)
    except ImportError:
        _logger.info('使用 Flask 开发服务器（生产环境建议: pip install waitress）')
        app.run(host=HOST, port=HTTP_PORT, threaded=True, debug=False)


if __name__ == '__main__':
    main()
