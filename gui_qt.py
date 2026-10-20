#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《万界归墟》桌面生成器 — PyQt5 本地直连。

启动: python gui_qt.py
依赖: pip install PyQt5
"""
from __future__ import annotations
import os
import sys
import time
import random
import threading
import queue

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QTextEdit,
    QRadioButton, QButtonGroup, QSplitter, QFrame, QGridLayout,
    QSizePolicy, QScrollArea,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QFont, QColor, QPalette, QTextCursor, QFontDatabase

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

STYLE = """
QMainWindow, QWidget { background: #fafaf8; }
QFrame#panel { background: #ffffff; border: 1px solid #e2e0d8; border-radius: 8px; }
QLabel#title { font-size: 15px; font-weight: bold; color: #2c2c28; }
QLabel#label { font-size: 12px; color: #888780; }
QLabel#stat_val { font-size: 18px; font-weight: bold; color: #2c2c28; }
QLineEdit {
    background: #fafaf8; border: 1px solid #e2e0d8; border-radius: 4px;
    padding: 6px 8px; font-size: 13px;
}
QRadioButton {
    font-size: 11px; padding: 6px 12px;
    background: #fafaf8; border: 1px solid #e2e0d8; border-radius: 4px;
}
QRadioButton:checked {
    background: #EEEDFE; border-color: #534AB7; color: #534AB7;
}
QPushButton { border-radius: 4px; padding: 8px 16px; font-size: 13px; border: none; }
QPushButton#start { background: #534AB7; color: white; }
QPushButton#start:disabled { background: #a9a4d8; }
QPushButton#stop { background: #993C1D; color: white; }
QPushButton#stop:disabled { background: #c99; }
QPushButton#clear { background: #fafaf8; border: 1px solid #e2e0d8; color: #2c2c28; }
QProgressBar {
    border: none; background: #e2e0d8; border-radius: 3px; height: 6px;
    text-align: center; font-size: 10px;
}
QProgressBar::chunk { background: #534AB7; border-radius: 3px; }
QTextEdit {
    background: #fafaf8; border: 1px solid #e2e0d8; border-radius: 6px;
    padding: 12px; font-size: 14px; line-height: 1.8;
}
QScrollBar:vertical { width: 8px; background: #fafaf8; }
QScrollBar::handle:vertical { background: #d3d1c7; border-radius: 4px; min-height: 20px; }
QSplitter::handle { background: #e2e0d8; width: 1px; }
"""


class GenerateWorker(QThread):
    """后台生成线程。"""
    progress_signal = pyqtSignal(dict)
    status_signal = pyqtSignal(str)
    complete_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, target_chars, seed):
        super().__init__()
        self.target = target_chars
        self.seed = seed
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            self.status_signal.emit('正在初始化引擎…')
            wb = WordBank(seed=self.seed)
            ps = PlotState()
            voice = VoiceEngine(wb, ps, seed=self.seed)
            wm = WorldStateManager(wb, seed=self.seed)
            for world in ['归墟', '武侠·苍云之殇', '末日废土']:
                wm.load_world(world)
            timeline = Timeline.default_timeline(seed=self.seed)
            storyboard = StoryBoard.default_board(seed=self.seed)
            integrated_gen = IntegratedChapterGenerator(wb, ps, seed=self.seed)

            config = dict(DEFAULT_WC_CONFIG)
            config['save_every'] = 10
            config['log_every'] = 100
            config['min_passage_chars'] = 200
            config['max_passage_chars'] = 1200

            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
            director = SceneDirector(
                integrated_gen, ps, wm, timeline, storyboard,
                config, output_dir, seed=self.seed,
            )

            self.status_signal.emit('开始生成…')
            total = 0
            passage_no = 0
            max_p = max(50, (self.target // config['min_passage_chars']) * 3)
            buffer = []

            while total < self.target and passage_no < max_p and not self._stop:
                wm.tick()
                fired = timeline.tick(wm.global_time, director._build_world_state_snapshot())
                for ev in fired:
                    if str(ev.scope) == 'EventScope.WORLD' and 'world' in ev.payload:
                        wm.unlock_world(ev.payload['world'])

                beats = storyboard.tick(passage_no)
                if not beats:
                    beats = [StoryBeat(line_id='a_lin_shuo', time_step=passage_no,
                                       beat_type='primary', pov_char='林朔')]

                remaining = self.target - total
                if remaining < config['min_passage_chars']:
                    break

                text = director._render_section(beats, fired, remaining)
                n = len(text)
                total += n
                passage_no += 1
                buffer.append(text)

                self.progress_signal.emit({
                    'chars': total, 'total': self.target,
                    'passage': passage_no,
                    'progress': min(100, total / self.target * 100),
                    'text': text, 'world': wm._active_world,
                    'dist': dict(storyboard.line_distribution()),
                    'intersections': len(storyboard._intersection_points),
                })

                director._chars.tick()

            full = '\n\n'.join(buffer)
            ts = time.strftime('%Y%m%d_%H%M%S')
            out_path = os.path.join(output_dir, f'万界归墟_qt_{total}字_{ts}.txt')
            os.makedirs(output_dir, exist_ok=True)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(full)

            self.complete_signal.emit({
                'chars': total,
                'intersections': len(storyboard._intersection_points),
                'path': out_path,
            })
        except Exception as e:
            self.error_signal.emit(str(e))


class NovelWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('万界归墟 · 棋盘生成器')
        self.resize(1100, 750)
        self.setMinimumSize(800, 500)
        self.setStyleSheet(STYLE)

        self._worker = None
        self._lines = []
        self._beat_counts = {}

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 8)

        # 标题
        title = QLabel('万界归墟 · 棋盘生成器')
        title.setObjectName('title')
        self._status_lbl = QLabel('就绪')
        self._status_lbl.setObjectName('label')
        header = QHBoxLayout()
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._status_lbl)
        root.addLayout(header)

        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # 左面板
        left = self._build_panel()
        splitter.addWidget(left)

        # 右面板
        right = self._build_output()
        splitter.addWidget(right)

        splitter.setSizes([310, 770])

    def _build_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName('panel')
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # 字数
        layout.addWidget(QLabel('目标字数', objectName='label'))
        self._target_edit = QLineEdit('2000')
        layout.addWidget(self._target_edit)

        # 预设
        layout.addWidget(QLabel('预设规模', objectName='label'))
        preset_group = QButtonGroup(self)
        preset_box = QHBoxLayout()
        self._presets = {}
        for cn, val in [('短篇', '2万'), ('中篇', '5万'), ('长篇', '20万')]:
            rb = QRadioButton(f'{cn}\n{val}')
            preset_group.addButton(rb)
            preset_box.addWidget(rb)
            self._presets[cn] = rb
            rb.toggled.connect(self._on_preset)
        self._presets['短篇'].setChecked(True)
        layout.addLayout(preset_box)

        # 种子
        layout.addWidget(QLabel('随机种子（零则随机）', objectName='label'))
        self._seed_edit = QLineEdit('42')
        layout.addWidget(self._seed_edit)

        # 按钮
        btn_box = QHBoxLayout()
        self._start_btn = QPushButton('开始生成')
        self._start_btn.setObjectName('start')
        self._start_btn.setCursor(Qt.PointingHandCursor)
        self._start_btn.clicked.connect(self._start)
        btn_box.addWidget(self._start_btn, 1)

        self._stop_btn = QPushButton('停止')
        self._stop_btn.setObjectName('stop')
        self._stop_btn.setCursor(Qt.PointingHandCursor)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)
        btn_box.addWidget(self._stop_btn)
        layout.addLayout(btn_box)

        # 进度
        self._progress = QProgressBar()
        layout.addWidget(self._progress)
        self._progress_lbl = QLabel('')
        self._progress_lbl.setObjectName('label')
        layout.addWidget(self._progress_lbl)

        # 统计
        stat_grid = QGridLayout()
        stat_grid.setSpacing(8)
        stats = [
            ('已生成字', 'stat_chars', '〇'),
            ('段落数', 'stat_passage', '〇'),
            ('活跃世界', 'stat_world', '归墟'),
            ('交叉点', 'stat_intersect', '〇'),
        ]
        self._stat_lbls = {}
        for i, (label, key, default) in enumerate(stats):
            card = QFrame()
            card.setStyleSheet('background:#fafaf8; border:1px solid #e2e0d8; border-radius:6px;')
            cl = QVBoxLayout(card)
            cl.setContentsMargins(8, 6, 8, 6)
            cl.setSpacing(0)
            val = QLabel(default)
            val.setObjectName('stat_val')
            val.setAlignment(Qt.AlignCenter)
            cl.addWidget(val)
            lbl = QLabel(label)
            lbl.setObjectName('label')
            lbl.setAlignment(Qt.AlignCenter)
            cl.addWidget(lbl)
            stat_grid.addWidget(card, i // 2, i % 2)
            self._stat_lbls[key] = val
        layout.addLayout(stat_grid)

        # 棋盘标题
        layout.addWidget(QLabel('棋盘布局', objectName='label'))
        self._board_panel = QFrame()
        self._board_panel.setStyleSheet('background:#fafaf8; border-radius:4px;')
        self._board_panel.setMinimumHeight(120)
        self._board_layout = QVBoxLayout(self._board_panel)
        self._board_layout.setContentsMargins(8, 8, 8, 8)
        self._board_layout.setSpacing(4)
        self._board_bars = {}
        self._board_lbls = {}
        colors = [('#534AB7', '主线：归墟锚定'), ('#1D9E75', '辅线：玩家觉醒'),
                   ('#993C1D', '暗线：暗流涌动'), ('#854F0B', '支线：苍云遗志')]
        for color, label in colors:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setObjectName('label')
            lbl.setFixedWidth(95)
            row.addWidget(lbl)
            bar = QFrame()
            bar.setStyleSheet(f'background:{color}; border-radius:3px;')
            bar.setFixedHeight(18)
            bar.setMinimumWidth(1)
            row.addWidget(bar, 1)
            self._board_layout.addLayout(row)
            self._board_bars[color] = bar
        layout.addWidget(self._board_panel)

        layout.addStretch()
        return panel

    def _build_output(self) -> QWidget:
        out_frame = QFrame()
        out_frame.setObjectName('panel')
        layout = QVBoxLayout(out_frame)
        layout.setContentsMargins(8, 8, 8, 8)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel('实时输出', objectName='label'))
        toolbar.addStretch()
        clear_btn = QPushButton('清空')
        clear_btn.setObjectName('clear')
        clear_btn.clicked.connect(lambda: self._output.clear())
        toolbar.addWidget(clear_btn)
        layout.addLayout(toolbar)

        # 文本框
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        layout.addWidget(self._output, 1)

        return out_frame

    # ── 事件 ──
    def _on_preset(self):
        for cn, rb in self._presets.items():
            if rb.isChecked():
                self._target_edit.setText(str(PRESET_CN.get(cn, 2000)))

    def _start(self):
        if self._worker and self._worker.isRunning():
            return

        target = int(self._target_edit.text() or 2000)
        seed = int(self._seed_edit.text() or 0)
        if seed == 0:
            seed = int(time.time() * 1000) % (2 ** 31)

        self._start_btn.setEnabled(False)
        self._start_btn.setText('生成中…')
        self._stop_btn.setEnabled(True)
        self._status_lbl.setText('正在生成…')
        self._output.clear()
        self._progress.setValue(0)

        self._worker = GenerateWorker(target, seed)
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.status_signal.connect(self._on_status)
        self._worker.complete_signal.connect(self._on_complete)
        self._worker.error_signal.connect(self._on_error)
        self._worker.start()

    def _stop(self):
        if self._worker:
            self._worker.stop()
            self._worker = None
        self._start_btn.setEnabled(True)
        self._start_btn.setText('开始生成')
        self._stop_btn.setEnabled(False)
        self._status_lbl.setText('已停止')

    def _on_status(self, msg: str):
        self._output.append(f'【系统】{msg}\n')

    def _on_progress(self, d: dict):
        self._progress.setValue(int(d['progress']))
        self._progress_lbl.setText(
            f'{d["chars"]:,} / {d["total"]:,} 字 · {d["progress"]:.0f}%')
        self._output.append(d['text'] + '\n\n')
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._output.setTextCursor(cursor)

        self._stat_lbls['stat_chars'].setText(f'{d["chars"]:,}')
        self._stat_lbls['stat_passage'].setText(str(d['passage']))
        self._stat_lbls['stat_world'].setText(d['world'])
        self._stat_lbls['stat_intersect'].setText(str(d['intersections']))

        # 棋盘
        dist = d.get('dist', {})
        total_b = max(1, sum(dist.values()))
        for color, bar in self._board_bars.items():
            key_map = {'#534AB7': 'a_lin_shuo', '#1D9E75': 'b_tang_chuan',
                       '#993C1D': 'c_agents', '#854F0B': 'd_wuxia_yl'}
            cnt = dist.get(key_map.get(color, ''), 0)
            pct = int(cnt / total_b * 200)
            bar.setFixedWidth(max(2, pct))
            bar.setToolTip(f'{cnt} 拍')

    def _on_complete(self, d: dict):
        self._output.append(
            f'\n【完成】{d["chars"]:,} 字 · {d["intersections"]} 个交叉点\n'
            f'文件: {d["path"]}\n')
        self._start_btn.setEnabled(True)
        self._start_btn.setText('开始生成')
        self._stop_btn.setEnabled(False)
        self._status_lbl.setText('完成')
        self._progress.setValue(100)

    def _on_error(self, msg: str):
        self._output.append(f'\n【错误】{msg}\n')
        self._start_btn.setEnabled(True)
        self._start_btn.setText('开始生成')
        self._stop_btn.setEnabled(False)
        self._status_lbl.setText('错误')


def main():
    app = QApplication(sys.argv)
    # 加载本地字体
    font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'KeShiLuGangBiHeTi', 'I-PenCrane-B-2.ttf')
    if os.path.exists(font_path):
        QFontDatabase.addApplicationFont(font_path)
        QApplication.setFont(QFont('I-PenCrane-B', 11))
    else:
        QApplication.setFont(QFont('Microsoft YaHei', 10))

    window = NovelWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
