"""共享测试 fixtures。"""
import json
import os
import sys
import tempfile

import pytest

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from novel_generator.engine.plot_state import PlotState
from novel_generator.engine.word_bank import WordBank


@pytest.fixture
def empty_plot_state():
    """创建纯内存模式的 PlotState（不写文件）。"""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
        json.dump({}, f)
        tmp_path = f.name
    ps = PlotState(save_path=tmp_path)
    # 覆盖为全新初始状态
    ps.state = ps._init_state()
    yield ps
    # 清理临时文件
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


@pytest.fixture
def seeded_word_bank():
    """固定 seed 的 WordBank（确定性输出）。"""
    return WordBank(seed=42)


@pytest.fixture
def temp_word_bank_dir():
    """创建临时词库目录，包含最小测试用词库。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_bank = {
            "test_key": ["alpha", "beta", "gamma"],
            "emotions": ["愤怒", "悲伤", "喜悦"],
            "senses": ["视觉", "听觉", "触觉"],
        }
        bank_path = os.path.join(tmpdir, 'test_bank.json')
        with open(bank_path, 'w', encoding='utf-8') as f:
            json.dump(test_bank, f, ensure_ascii=False)
        yield tmpdir
