#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《万界归墟》桌面生成器

启动: python gui_tk.py

本文件作为统一入口，自动检测可用 GUI 框架：
  1. tkinter（Python 自带，轻量）→ 优先
  2. PyQt5（需 pip install PyQt5）→ 备选

当前环境：
  tkinter: 不可用（_tkinter C 扩展未编译入当前 Python 3.14.6）
  PyQt5:  可用

修复 tkinter: 重新运行 Python 安装器并勾选「tcl/tk and IDLE」选项，
  或使用: python gui_qt.py 直接启动 PyQt5 版。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 检测可用 GUI 框架 ──
_tk_ok = False
_qt_ok = False

try:
    import tkinter as tk
    _tk_ok = True
except ModuleNotFoundError:
    pass

try:
    from PyQt5.QtWidgets import QApplication
    _qt_ok = True
except ModuleNotFoundError:
    pass


def _launch_tk():
    """启动 tkinter 桌面 GUI。"""
    import time
    import random
    import threading
    import queue as tqueue
    import tkinter as tk
    from tkinter import ttk

    from wanjie.engine.word_bank import WordBank
    from wanjie.engine.plot_state import PlotState
    from wanjie.engine.world_state import WorldStateManager
    from wanjie.engine.timeline import Timeline
    from wanjie.engine.storyline import StoryBoard, StoryBeat
    from wanjie.engine.scene_director import SceneDirector
    from wanjie.engine.integrated_chapter_generator import IntegratedChapterGenerator
    from wanjie.engine.voice_engine import VoiceEngine
    from wanjie.engine.wordcount_director import PRESETS, DEFAULT_WC_CONFIG

    PRESET_CN = {'短篇': 20000, '中篇': 50000, '长篇': 200000}
    _GEN_QUEUE = tqueue.Queue()

    class NovelGUI:
        def __init__(self, root):
            self.root = root
            root.title('万界归墟 · 棋盘生成器')
            root.geometry('1100x750')
            root.minsize(800, 500)
            root.configure(bg='#fafaf8')

            # 字体
            font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     'KeShiLuGangBiHeTi', 'I-PenCrane-B-2.ttf')
            if not os.path.exists(font_path):
                font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         'gui', 'static', 'font.ttf')
            self._font_family = 'Microsoft YaHei'
            if os.path.exists(font_path):
                try:
                    from ctypes import windll, create_unicode_buffer
                    windll.gdi32.AddFontResourceExW(create_unicode_buffer(font_path), 0x10, 0)
                    self._font_family = 'I-PenCrane-B'
                except Exception:
                    pass

            self._build_ui()
            self._gen_active = False
            self._poll_queue()

        def _f(self, size=11, bold=False):
            return (self._font_family, size, 'bold' if bold else 'normal')

        def _build_ui(self):
            header = tk.Frame(self.root, bg='#fafaf8', height=36)
            header.pack(fill='x', padx=16, pady=(10, 0))
            header.pack_propagate(False)
            tk.Label(header, text='万界归墟 · 棋盘生成器', font=self._f(14, True),
                     bg='#fafaf8', fg='#2c2c28').pack(side='left')
            self._status = tk.Label(header, text='就绪', font=self._f(9),
                                     bg='#fafaf8', fg='#888780')
            self._status.pack(side='right')

            main = tk.PanedWindow(self.root, orient='horizontal', bg='#fafaf8',
                                    sashwidth=4, sashrelief='flat')
            main.pack(fill='both', expand=True, padx=12, pady=8)

            left = tk.Frame(main, bg='#ffffff')
            right = tk.Frame(main, bg='#ffffff')
            main.add(left, minsize=200)
            main.add(right, minsize=200)
            self._panel(left)
            self._output(right)
            # 设置初始分隔位置（左侧面板 300px）
            main.after(10, lambda: main.sash_place(0, 300, 0))

        def _panel(self, outer):
            outer = tk.Frame(outer, bg='#ffffff')
            outer.pack(fill='both', expand=True)

            # 可滚动画布
            canvas = tk.Canvas(outer, bg='#ffffff', highlightthickness=0, width=280)
            sb = tk.Scrollbar(outer, orient='vertical', command=canvas.yview)
            canvas.configure(yscrollcommand=sb.set)

            p = tk.Frame(canvas, bg='#ffffff', padx=14, pady=14)
            win_id = canvas.create_window((0, 0), window=p, anchor='nw', tags='inner')

            # 让 canvas 窗口宽度跟随 canvas 宽度变化
            def _on_canvas_resize(event):
                canvas.itemconfig(win_id, width=event.width)
            canvas.bind('<Configure>', _on_canvas_resize)

            # p 配置变化时更新滚动区域
            def _update_scroll(_=None):
                canvas.configure(scrollregion=canvas.bbox('all'))
            p.bind('<Configure>', _update_scroll, add='+')

            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
            canvas.bind('<Enter>', lambda _: canvas.bind_all('<MouseWheel>', _on_mousewheel))
            canvas.bind('<Leave>', lambda _: canvas.unbind_all('<MouseWheel>'))

            canvas.pack(side='left', fill='both', expand=True)
            sb.pack(side='right', fill='y')

            # ── 所有控件使用 pack，让 p 自动撑高 ──

            # 预设规模
            tk.Label(p, text='预设规模', font=self._f(10), bg='#ffffff',
                     fg='#888780').pack(anchor='w')
            pf = tk.Frame(p, bg='#ffffff')
            pf.pack(fill='x', pady=(2, 10))
            self._preset_var = tk.StringVar(value='短篇')
            for cn, val in [('短篇', '2万'), ('中篇', '5万'), ('长篇', '20万')]:
                rb = tk.Radiobutton(pf, text=f'{cn}\n{val}', variable=self._preset_var,
                                    value=cn, font=self._f(9), bg='#ffffff', fg='#534AB7',
                                    selectcolor='#EEEDFE', indicatoron=False, relief='flat',
                                    padx=6, pady=3, command=lambda: self._target_var.set(
                                        str(PRESET_CN.get(self._preset_var.get(), 2000))))
                rb.pack(side='left', padx=2)

            # 目标字数
            tk.Label(p, text='目标字数', font=self._f(10), bg='#ffffff',
                     fg='#888780').pack(anchor='w')
            self._target_var = tk.StringVar(value='2000')
            tk.Entry(p, textvariable=self._target_var, font=self._f(11), bg='#fafaf8',
                     relief='solid', borderwidth=1).pack(fill='x', pady=(2, 10), ipady=4)

            # 随机种子
            tk.Label(p, text='随机种子（零则随机）', font=self._f(10), bg='#ffffff',
                     fg='#888780').pack(anchor='w')
            self._seed_var = tk.StringVar(value='42')
            tk.Entry(p, textvariable=self._seed_var, font=self._f(11), bg='#fafaf8',
                     relief='solid', borderwidth=1).pack(fill='x', pady=(2, 12), ipady=4)

            # 按钮
            bf = tk.Frame(p, bg='#ffffff')
            bf.pack(fill='x')
            self._start_btn = tk.Button(bf, text='开始生成', font=self._f(11),
                                         bg='#534AB7', fg='white', relief='flat',
                                         padx=16, pady=8, command=self._start)
            self._start_btn.pack(side='left', fill='x', expand=True)
            self._stop_btn = tk.Button(bf, text='停止', font=self._f(11),
                                        bg='#993C1D', fg='white', relief='flat',
                                        padx=16, pady=8, command=self._stop, state='disabled')
            self._stop_btn.pack(side='left', padx=(6, 0))

            # 进度条
            self._progress = ttk.Progressbar(p, length=270, mode='determinate')
            self._progress.pack(fill='x', pady=(12, 0))
            self._prog_lbl = tk.Label(p, text='', font=self._f(9), bg='#ffffff', fg='#888780')
            self._prog_lbl.pack(anchor='w', pady=(0, 10))

            # 统计卡片 2x2 网格
            self._stat_lbls = {}
            stats = [('已生成字', 'sc', '〇'), ('段落数', 'sp', '〇'),
                      ('活跃世界', 'sw', '归墟'), ('交叉点', 'si', '〇')]
            stat_outer = tk.Frame(p, bg='#ffffff')
            stat_outer.pack(fill='x')
            for i, (label, key, default) in enumerate(stats):
                row = i // 2
                col = i % 2
                card = tk.Frame(stat_outer, bg='#fafaf8', relief='solid', borderwidth=1,
                                width=132, height=48)
                card.grid(row=row, column=col, padx=(0, 4) if col == 0 else (0, 0),
                          pady=(0, 4))
                card.pack_propagate(False)
                val = tk.Label(card, text=default, font=self._f(14, True),
                               bg='#fafaf8', fg='#2c2c28')
                val.pack(pady=(2, 0))
                tk.Label(card, text=label, font=self._f(8), bg='#fafaf8',
                         fg='#888780').pack()
                self._stat_lbls[key] = val

            # ── 世界与角色配置（可折叠） ──
            world_header = tk.Frame(p, bg='#ffffff')
            world_header.pack(fill='x', pady=(14, 0))
            tk.Label(world_header, text='世界与角色配置', font=self._f(12, True),
                     bg='#ffffff', fg='#2c2c28').pack(side='left')
            self._world_expand_var = tk.BooleanVar(value=False)
            self._world_expand_btn = tk.Button(world_header, text='展开 ▼',
                font=self._f(9), bg='#fafaf8', relief='flat', padx=8, pady=2,
                command=self._toggle_world_cfg)
            self._world_expand_btn.pack(side='right')

            # 可折叠配置区
            self._world_cfg_frame = tk.Frame(p, bg='#ffffff')
            self._build_world_cfg(self._world_cfg_frame)
            # 初始隐藏

            # 存储画布和内部 frame 引用
            self._panel_canvas = canvas
            self._panel_inner = p

        def _toggle_world_cfg(self):
            if self._world_expand_var.get():
                self._world_expand_var.set(False)
                self._world_expand_btn.config(text='展开 ▼')
                self._world_cfg_frame.pack_forget()
            else:
                self._world_expand_var.set(True)
                self._world_expand_btn.config(text='收起 ▲')
                self._world_cfg_frame.pack(fill='x', pady=(2, 6))
            # 触发滚动区域更新
            self._panel_canvas.configure(scrollregion=self._panel_canvas.bbox('all'))

        def _build_world_cfg(self, p):
            """构建世界配置面板——列表式选择，非填空。"""
            self._world_rows = []
            self._phase_map_vars = {}

            # 从词库动态发现可用世界
            self._KNOWN_WORLDS = ['归墟', '武侠·苍云之殇', '末日废土',
                                  '赛博都市', '东方修仙', '剑与魔法', '星际殖民',
                                  '克苏鲁深渊', '近代乱世', '低魔中世纪', '诸神黄昏',
                                  '高等文明实验场', '造物主遗迹', '深海遗迹',
                                  '机械神域', '蒸汽朋克', '无限流',
                                  '魔法学院', '修仙界']
            self._KNOWN_POVS = ['林朔', '唐川', '白夜', '叶琳', '无']

            DEFAULT_WORLDS = [
                {'name': '归墟',             'pov': '林朔', 'enabled': True},
                {'name': '武侠·苍云之殇',    'pov': '叶琳', 'enabled': True},
                {'name': '末日废土',         'pov': '无',   'enabled': True},
            ]
            PHASE_LABELS = [
                ('ESTABLISH', '探索期'),
                ('REVEAL',    '揭示期'),
                ('CONFLICT',  '冲突期'),
                ('CHOICE',    '抉择期'),
                ('TRANSFORM', '蜕变期'),
            ]
            DEFAULT_PHASE_MAP = {
                'ESTABLISH': '归墟',
                'REVEAL': '归墟',
                'CONFLICT': '武侠·苍云之殇',
                'CHOICE': '末日废土',
                'TRANSFORM': '归墟',
            }

            # ===== 世界列表（可增删） =====
            list_header = tk.Frame(p, bg='#fafaf8')
            list_header.pack(fill='x', pady=(0, 2))
            tk.Label(list_header, text='世界观列表', font=self._f(9, True),
                     bg='#fafaf8', fg='#2c2c28').pack(side='left')
            add_btn = tk.Button(list_header, text='+ 添加', font=self._f(8),
                                bg='#534AB7', fg='white', relief='flat',
                                padx=8, pady=1,
                                command=lambda: self._add_world_row(self._world_list_frame))
            add_btn.pack(side='right')

            # 世界行容器
            self._world_list_frame = tk.Frame(p, bg='#ffffff')
            self._world_list_frame.pack(fill='x')

            def _mk_world_row(parent, name='', pov='', enabled=True):
                """创建一行世界配置。"""
                row = tk.Frame(parent, bg='#ffffff')
                row.pack(fill='x', pady=1)
                en_var = tk.BooleanVar(value=enabled)
                tk.Checkbutton(row, variable=en_var, bg='#ffffff',
                               selectcolor='#EEEDFE').pack(side='left')
                # 世界名：下拉选择
                name_var = tk.StringVar(value=name)
                name_cb = ttk.Combobox(row, textvariable=name_var,
                                       values=self._KNOWN_WORLDS,
                                       font=self._f(9), width=14, state='readonly')
                name_cb.pack(side='left', padx=(4, 2))
                # 允许手动输入自定义世界名
                name_cb.bind('<Double-Button-1>',
                             lambda e, cb=name_cb: cb.config(state='normal'))
                name_cb.bind('<FocusOut>',
                             lambda e, cb=name_cb: cb.config(state='readonly'))
                # POV：下拉选择
                pov_var = tk.StringVar(value=pov)
                pov_cb = ttk.Combobox(row, textvariable=pov_var,
                                      values=self._KNOWN_POVS,
                                      font=self._f(9), width=6, state='readonly')
                pov_cb.pack(side='left', padx=2)
                pov_cb.bind('<Double-Button-1>',
                            lambda e, cb=pov_cb: cb.config(state='normal'))
                pov_cb.bind('<FocusOut>',
                            lambda e, cb=pov_cb: cb.config(state='readonly'))
                # 删除按钮
                del_btn = tk.Button(row, text='✕', font=self._f(8),
                                    bg='#ffffff', fg='#993C1D', relief='flat',
                                    padx=3, pady=0, bd=0,
                                    command=lambda r=row: self._del_world_row(r))
                del_btn.pack(side='right')
                record = {'enabled': en_var, 'name': name_var, 'pov': pov_var,
                          'row': row, 'name_cb': name_cb}
                self._world_rows.append(record)
                return record

            # 初始行
            for w in DEFAULT_WORLDS:
                _mk_world_row(self._world_list_frame,
                              name=w['name'], pov=w['pov'], enabled=w['enabled'])

            # 分隔线
            sep = tk.Frame(p, bg='#e0e0d8', height=1)
            sep.pack(fill='x', pady=(10, 6))

            # ===== A线阶段→世界映射 =====
            tk.Label(p, text='A线（林朔）阶段→世界映射',
                     font=self._f(9, True), bg='#ffffff', fg='#2c2c28').pack(anchor='w')

            self._phase_map_frame = tk.Frame(p, bg='#ffffff')
            self._phase_map_frame.pack(fill='x', pady=(2, 0))

            def _refresh_phase_options():
                """根据当前世界列表刷新阶段映射的下拉选项。"""
                names = [r['name'].get() for r in self._world_rows
                         if r['enabled'].get()]
                if not names:
                    names = ['归墟']
                for phase_key, var in self._phase_map_vars.items():
                    cur = var.get()
                    if cur not in names:
                        var.set(names[0])
                    # 重新创建 OptionMenu（tkinter 不支持动态更新 values）
                    for child in self._phase_map_frame.winfo_children():
                        child.destroy()
                self._build_phase_rows(names)

            def _build_phase_rows(world_names):
                for phase_key, phase_label in PHASE_LABELS:
                    brow = tk.Frame(self._phase_map_frame, bg='#ffffff')
                    brow.pack(fill='x', pady=2)
                    tk.Label(brow, text=phase_label, font=self._f(8),
                             bg='#ffffff', fg='#888780', width=8,
                             anchor='e').pack(side='left')
                    var = self._phase_map_vars.get(phase_key)
                    if var is None:
                        var = tk.StringVar(
                            value=DEFAULT_PHASE_MAP.get(phase_key, '归墟'))
                        self._phase_map_vars[phase_key] = var
                    if var.get() not in world_names:
                        var.set(world_names[0])
                    opt = tk.OptionMenu(brow, var, *world_names)
                    opt.config(font=self._f(9), bg='#fafaf8', relief='solid',
                               borderwidth=1, padx=4)
                    opt.pack(side='left', padx=(6, 0), fill='x', expand=True)

            _build_phase_rows([w['name'] for w in DEFAULT_WORLDS])
            # 保存刷新函数供增删行时调用
            self._refresh_phase_options = _refresh_phase_options

        def _add_world_row(self, parent):
            """添加一行新世界。"""
            row = tk.Frame(parent, bg='#ffffff')
            row.pack(fill='x', pady=1)
            en_var = tk.BooleanVar(value=True)
            tk.Checkbutton(row, variable=en_var, bg='#ffffff',
                           selectcolor='#EEEDFE').pack(side='left')
            name_var = tk.StringVar(value='')
            name_cb = ttk.Combobox(row, textvariable=name_var,
                                   values=self._KNOWN_WORLDS,
                                   font=self._f(9), width=14, state='readonly')
            name_cb.pack(side='left', padx=(4, 2))
            name_cb.bind('<Double-Button-1>',
                         lambda e, cb=name_cb: cb.config(state='normal'))
            name_cb.bind('<FocusOut>',
                         lambda e, cb=name_cb: cb.config(state='readonly'))
            pov_var = tk.StringVar(value='无')
            pov_cb = ttk.Combobox(row, textvariable=pov_var,
                                  values=self._KNOWN_POVS,
                                  font=self._f(9), width=6, state='readonly')
            pov_cb.pack(side='left', padx=2)
            pov_cb.bind('<Double-Button-1>',
                        lambda e, cb=pov_cb: cb.config(state='normal'))
            pov_cb.bind('<FocusOut>',
                        lambda e, cb=pov_cb: cb.config(state='readonly'))
            del_btn = tk.Button(row, text='✕', font=self._f(8),
                                bg='#ffffff', fg='#993C1D', relief='flat',
                                padx=3, pady=0, bd=0,
                                command=lambda r=row: self._del_world_row(r))
            del_btn.pack(side='right')
            self._world_rows.append({
                'enabled': en_var, 'name': name_var, 'pov': pov_var,
                'row': row, 'name_cb': name_cb,
            })

        def _del_world_row(self, row):
            """删除一行世界配置。"""
            # 从 world_rows 中移除对应条目
            self._world_rows = [r for r in self._world_rows if r['row'] is not row]
            row.destroy()
            self._refresh_phase_options()

        def _output(self, parent):
            f = tk.Frame(parent, bg='#ffffff')
            f.pack(fill='both', expand=True, padx=8, pady=8)
            tb = tk.Frame(f, bg='#ffffff')
            tb.pack(fill='x', pady=(0, 6))
            tk.Label(tb, text='实时输出', font=self._f(10), bg='#ffffff',
                     fg='#888780').pack(side='left')
            tk.Button(tb, text='清空', font=self._f(9), bg='#fafaf8',
                      relief='flat', padx=10, pady=2,
                      command=lambda: self._text.delete('1.0', 'end')).pack(side='right')
            tf = tk.Frame(f, bg='#ffffff')
            tf.pack(fill='both', expand=True)
            self._text = tk.Text(tf, font=self._f(12), bg='#fafaf8', fg='#2c2c28',
                                  wrap='word', relief='solid', borderwidth=1,
                                  padx=14, pady=10, spacing2=3, spacing3=5)
            sb = tk.Scrollbar(tf, command=self._text.yview)
            self._text.configure(yscrollcommand=sb.set)
            self._text.pack(side='left', fill='both', expand=True)
            sb.pack(side='right', fill='y')

        def _start(self):
            if self._gen_active:
                return
            target = int(self._target_var.get() or 2000)
            seed = int(self._seed_var.get() or 0)
            if seed == 0:
                seed = int(time.time() * 1000) % (2 ** 31)

            # 收集世界配置
            worlds_config = []
            for row in self._world_rows:
                worlds_config.append({
                    'name': row['name'].get().strip(),
                    'enabled': bool(row['enabled'].get()),
                    'pov': row['pov'].get().strip(),
                })
            phase_world_map = {
                k: v.get().strip()
                for k, v in self._phase_map_vars.items()
            }

            self._gen_active = True
            self._start_btn.config(state='disabled', text='生成中…')
            self._stop_btn.config(state='normal')
            self._status.config(text='正在生成…')
            self._progress['value'] = 0
            self._text.delete('1.0', 'end')

            threading.Thread(target=self._worker,
                             args=(target, seed, worlds_config, phase_world_map),
                             daemon=True).start()

        def _stop(self):
            self._gen_active = False
            self._start_btn.config(state='normal', text='开始生成')
            self._stop_btn.config(state='disabled')
            self._status.config(text='已停止')

        def _worker(self, target, seed, worlds_config=None, phase_world_map=None):
            try:
                _GEN_QUEUE.put(('status', '初始化引擎…'))
                wb = WordBank(seed=seed)
                ps = PlotState()
                VoiceEngine(wb, ps, seed=seed)
                wm = WorldStateManager(wb, seed=seed)
                # 仅加载启用的世界
                enabled_worlds = [w['name'] for w in (worlds_config or [])
                                  if w.get('enabled', True)]
                if not enabled_worlds:
                    enabled_worlds = ['归墟']  # 保证至少有一个世界
                for w in enabled_worlds:
                    wm.load_world(w)
                timeline = Timeline.default_timeline(seed=seed)
                storyboard = StoryBoard.default_board(seed=seed, worlds_config=worlds_config)
                ig = IntegratedChapterGenerator(wb, ps, seed=seed)
                cfg = dict(DEFAULT_WC_CONFIG)
                cfg.update(save_every=10, log_every=100, min_passage_chars=200, max_passage_chars=1200)
                od = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
                director = SceneDirector(ig, ps, wm, timeline, storyboard, cfg, od, seed=seed,
                                         phase_world_map=phase_world_map)

                _GEN_QUEUE.put(('status', '开始生成…'))
                total = 0
                pn = 0
                max_p = max(50, (target // cfg['min_passage_chars']) * 3)
                buf = []
                while total < target and pn < max_p and self._gen_active:
                    wm.tick()
                    fired = timeline.tick(wm.global_time, director._build_world_state_snapshot())
                    for ev in fired:
                        if str(ev.scope) == 'EventScope.WORLD' and 'world' in ev.payload:
                            wm.unlock_world(ev.payload['world'])
                    beats = storyboard.tick(pn) or [StoryBeat(line_id='a_lin_shuo', time_step=pn, beat_type='primary', pov_char='林朔')]
                    rem = target - total
                    if rem < cfg['min_passage_chars']:
                        break
                    text = director._render_section(beats, fired, rem)
                    n = len(text)
                    total += n
                    pn += 1
                    buf.append(text)
                    _GEN_QUEUE.put(('progress', {'chars': total, 'total': target, 'passage': pn, 'progress': min(100, total/target*100), 'text': text, 'world': wm._active_world, 'dist': dict(storyboard.line_distribution()), 'intersections': len(storyboard._intersection_points)}))
                    director._chars.tick()

                full = '\n\n'.join(buf)
                ts = time.strftime('%Y%m%d_%H%M%S')
                op = os.path.join(od, f'万界归墟_tk_{total}字_{ts}.txt')
                os.makedirs(od, exist_ok=True)
                with open(op, 'w', encoding='utf-8') as f:
                    f.write(full)
                _GEN_QUEUE.put(('complete', {'chars': total, 'intersections': len(storyboard._intersection_points), 'path': op}))
            except Exception as e:
                _GEN_QUEUE.put(('error', str(e)))
            finally:
                self._gen_active = False

        def _poll_queue(self):
            try:
                while True:
                    msg = _GEN_QUEUE.get_nowait()
                    if msg[0] == 'status':
                        self._text.insert('end', f'【系统】{msg[1]}\n')
                    elif msg[0] == 'progress':
                        d = msg[1]
                        self._progress['value'] = d['progress']
                        self._prog_lbl.config(text=f'{d["chars"]:,}/{d["total"]:,} · {d["progress"]:.0f}%')
                        self._text.insert('end', d['text'] + '\n\n')
                        self._text.see('end')
                        self._stat_lbls['sc'].config(text=f'{d["chars"]:,}')
                        self._stat_lbls['sp'].config(text=str(d['passage']))
                        self._stat_lbls['sw'].config(text=d['world'])
                        self._stat_lbls['si'].config(text=str(d['intersections']))
                    elif msg[0] == 'complete':
                        d = msg[1]
                        self._text.insert('end', f'\n【完成】{d["chars"]:,}字·{d["intersections"]}交叉点\n{d["path"]}\n')
                        self._start_btn.config(state='normal', text='开始生成')
                        self._stop_btn.config(state='disabled')
                        self._status.config(text='完成')
                        self._progress['value'] = 100
                    elif msg[0] == 'error':
                        self._text.insert('end', f'\n【错误】{msg[1]}\n')
                        self._start_btn.config(state='normal', text='开始生成')
                        self._stop_btn.config(state='disabled')
                        self._status.config(text='错误')
            except tqueue.Empty:
                pass
            self.root.after(100, self._poll_queue)

    root = tk.Tk()
    NovelGUI(root)
    root.mainloop()


def _launch_qt():
    """代理到 PyQt5 版本。"""
    print('使用 PyQt5 启动桌面 GUI…')
    qt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gui_qt.py')
    if os.path.exists(qt_path):
        import runpy
        runpy.run_path(qt_path, run_name='__main__')
    else:
        print('错误: gui_qt.py 未找到')
        sys.exit(1)


# ── 主入口 ──
if __name__ == '__main__':
    print('万界归墟 · 桌面生成器')
    print(f'  tkinter: {"可用" if _tk_ok else "不可用（_tkinter C 扩展缺失）"}')
    print(f'  PyQt5:   {"可用" if _qt_ok else "不可用"}')

    if _tk_ok:
        print('\n启动 tkinter 桌面 GUI…')
        _launch_tk()
    elif _qt_ok:
        print('\ntkinter 不可用，自动切换到 PyQt5…')
        _launch_qt()
    else:
        print('\n错误: 无可用的 GUI 框架！')
        print('  tkinter: 请重新运行 Python 安装器，勾选「tcl/tk and IDLE」')
        print('  PyQt5:   pip install PyQt5')
        sys.exit(1)
