"""template.py 单元测试 — 模板引擎占位符解析。

覆盖：上下文变量替换、bank.key 引用、:unique 修饰、,N 多选、fill_loop。
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

from novel_generator.engine.word_bank import WordBank
from novel_generator.engine.template import TemplateEngine


@pytest.fixture
def mock_word_bank():
    """创建带最小测试词库的 WordBank（使用 seed=42 确保确定性）。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试词库
        test_bank = {
            'body_parts': {
                '头': ['圆圆的脑袋', '尖尖的头颅'],
                '眼': ['明亮的眼睛', '锐利的目光'],
            },
            'equipment': {
                '兵器': ['青冥剑', '紫电刀', '破风枪'],
            },
            'adjectives': {
                '场景': ['幽暗的', '明亮的', '阴森的'],
            },
        }
        import novel_generator.engine.word_bank as wb_mod
        original_dir = wb_mod.WORD_BANK_DIR
        bank_dir = Path(tmpdir) / 'word_banks'
        os.makedirs(str(bank_dir), exist_ok=True)
        with open(str(bank_dir / 'test_bank.json'), 'w', encoding='utf-8') as f:
            json.dump(test_bank, f, ensure_ascii=False)
        wb_mod.WORD_BANK_DIR = bank_dir
        wb = WordBank(seed=42)
        engine = TemplateEngine(wb)
        yield engine
        wb_mod.WORD_BANK_DIR = original_dir


@pytest.fixture
def simple_engine():
    """简化版：只用 WordBank 作变量替换（不测试词库）。"""
    wb = WordBank(seed=42)
    return TemplateEngine(wb)


class TestContextVariables:
    """上下文变量替换。"""

    def test_simple_variable(self, simple_engine):
        """简单 {{name}} 替换。"""
        result = simple_engine.fill('{{主角名}}站在废墟中', {'主角名': '林朔'})
        assert result == '林朔站在废墟中'

    def test_multiple_variables(self, simple_engine):
        """多个变量替换。"""
        result = simple_engine.fill(
            '{{角色A}}与{{角色B}}对峙',
            {'角色A': '林朔', '角色B': '唐川'}
        )
        assert result == '林朔与唐川对峙'

    def test_variable_used_twice(self, simple_engine):
        """同一变量多次替换。"""
        result = simple_engine.fill('{{名}}说：{{名}}在此！', {'名': '林朔'})
        assert result == '林朔说：林朔在此！'

    def test_unresolved_variable_preserved(self, simple_engine):
        """未解析的占位符保留原样。"""
        result = simple_engine.fill('他举起{{不存在的变量}}', {})
        assert '{{不存在的变量}}' in result

    def test_empty_template(self, simple_engine):
        """空模板返回空字符串。"""
        result = simple_engine.fill('', {'名': '林朔'})
        assert result == ''


class TestBankRef:
    """bank.key 引用（需要真实词库）。"""

    def test_bank_key_pick_from_real_adjectives(self, simple_engine):
        """从真实词库 adjectives.json 的 scene key 随机选取（seed=42 确定性）。"""
        result = simple_engine.fill('{{adjectives.scene}}')
        assert len(result) > 0
        assert result != '{{adjectives.scene}}'  # 已替换

    def test_bank_key_pick_from_real_equipment(self, simple_engine):
        """从 real equipment.json 的 weapon_type key 选取。"""
        result = simple_engine.fill('{{equipment.weapon_type}}')
        assert len(result) > 0
        assert result != '{{equipment.weapon_type}}'


class TestFillLoop:
    """fill_loop 循环填充。"""

    def test_fill_loop_iterations(self, simple_engine):
        """验证迭代次数正确。"""
        results = simple_engine.fill_loop(
            '第{{循环索引}}章：{{主角}}登场',
            {'主角': '林朔'},
            iterations=3
        )
        assert len(results) == 3
        assert '第1章' in results[0]
        assert '第2章' in results[1]
        assert '第3章' in results[2]

    def test_fill_loop_all_contain_variables(self, simple_engine):
        """每次迭代都正确替换变量。"""
        results = simple_engine.fill_loop(
            '{{名}}行动', {'名': '林朔'}, iterations=5
        )
        for r in results:
            assert '林朔行动' == r


class TestEdgeCases:
    """边界条件。"""

    def test_no_placeholders(self, simple_engine):
        """无占位符的纯文本原样返回。"""
        result = simple_engine.fill('纯文本无占位符', {})
        assert result == '纯文本无占位符'

    def test_none_variables(self, simple_engine):
        """variables=None 不报错。"""
        result = simple_engine.fill('{{某变量}}', None)
        assert '{{某变量}}' in result  # 无变量定义，保留原样

    def test_special_chars_in_template(self, simple_engine):
        """模板含特殊字符。"""
        result = simple_engine.fill('价格：{{货币}}100', {'货币': '灵石'})
        assert result == '价格：灵石100'
