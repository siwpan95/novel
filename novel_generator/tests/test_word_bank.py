"""word_bank.py 单元测试 — 词库加载/缓存/随机选取/名字生成。

覆盖：pick/pick_n/pick_without/generate_name/all_keys/缓存/确定性。
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

from novel_generator.engine.word_bank import WordBank


@pytest.fixture
def seeded_wb():
    """固定 seed=42 的 WordBank（确定性输出）。"""
    return WordBank(seed=42)


@pytest.fixture
def wb_with_temp_bank():
    """带临时测试词库的 WordBank。"""
    import novel_generator.engine.word_bank as wb_mod
    original_dir = wb_mod.WORD_BANK_DIR

    with tempfile.TemporaryDirectory() as tmpdir:
        bank_dir = Path(tmpdir) / 'word_banks'
        os.makedirs(str(bank_dir), exist_ok=True)
        test_data = {
            'key1': ['alpha', 'beta', 'gamma', 'delta', 'epsilon'],
            'key2': ['一', '二', '三'],
            'empty_key': [],
        }
        with open(str(bank_dir / 'test_bank.json'), 'w', encoding='utf-8') as f:
            json.dump(test_data, f, ensure_ascii=False)

        wb_mod.WORD_BANK_DIR = bank_dir
        wb = WordBank(seed=42)
        yield wb
        wb_mod.WORD_BANK_DIR = original_dir


class TestPick:
    """pick() 随机选取。"""

    def test_pick_deterministic(self, seeded_wb):
        """相同 seed 产生相同结果。"""
        key = 'weapon_type'
        result1 = seeded_wb.pick('equipment', key)
        # 重新创建相同 seed 的 WordBank
        wb2 = WordBank(seed=42)
        result2 = wb2.pick('equipment', key)
        assert result1 == result2

    def test_pick_returns_string(self, seeded_wb):
        """pick 返回字符串。"""
        result = seeded_wb.pick('equipment', 'weapon_type')
        assert isinstance(result, str)
        assert len(result) > 0

    def test_pick_nonexistent_key_raises(self, wb_with_temp_bank):
        """不存在的 key 抛出 KeyError。"""
        with pytest.raises(KeyError):
            wb_with_temp_bank.pick('test_bank', '不存在的key')

    def test_pick_nonexistent_bank_raises(self, seeded_wb):
        """不存在的词库抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            seeded_wb.pick('不存在的词库', '任意key')


class TestPickN:
    """pick_n() 多选。"""

    def test_pick_n_count(self, wb_with_temp_bank):
        """返回指定数量。"""
        results = wb_with_temp_bank.pick_n('test_bank', 'key1', 3)
        assert len(results) == 3
        for r in results:
            assert r in ['alpha', 'beta', 'gamma', 'delta', 'epsilon']

    def test_pick_n_unique(self, wb_with_temp_bank):
        """unique=True 时不重复。"""
        results = wb_with_temp_bank.pick_n('test_bank', 'key1', 3, unique=True)
        assert len(set(results)) == 3  # 无重复

    def test_pick_n_unique_capped(self, wb_with_temp_bank):
        """unique=True 且 n > pool 时，自动截断为 pool 大小。"""
        results = wb_with_temp_bank.pick_n('test_bank', 'key2', 10, unique=True)
        assert len(results) == 3  # pool 只有 3 项


class TestPickWithout:
    """pick_without() 排除选取。"""

    def test_pick_without_excludes(self, wb_with_temp_bank):
        """排除项不会出现在结果中。"""
        exclude = {'alpha', 'beta'}
        for _ in range(20):  # 多次测试确保确实被排除
            result = wb_with_temp_bank.pick_without('test_bank', 'key1', exclude)
            assert result not in exclude

    def test_pick_without_all_excluded(self, wb_with_temp_bank):
        """全部被排除时 fallback 到完整池。"""
        result = wb_with_temp_bank.pick_without(
            'test_bank', 'key2', {'一', '二', '三'}
        )
        # fallback 返回池中任一项
        assert result in ['一', '二', '三']


class TestGenerateName:
    """generate_name() 半随机名字生成。"""

    def test_generate_name_deterministic(self):
        """相同 seed 产生相同名字。"""
        wb1 = WordBank(seed=42)
        wb2 = WordBank(seed=42)
        assert wb1.generate_name() == wb2.generate_name()

    def test_generate_name_format(self, seeded_wb):
        """名字格式：姓氏+名字字符。"""
        name = seeded_wb.generate_name()
        assert len(name) >= 2
        assert isinstance(name, str)

    def test_generate_name_with_surname(self, seeded_wb):
        """指定姓氏生成名字。"""
        name = seeded_wb.generate_name(surname='墨')
        assert name.startswith('墨')
        assert len(name) >= 3  # 姓氏 + 至少 1 个名字字符

    def test_generate_name_length(self, seeded_wb):
        """指定名字字符长度。"""
        name = seeded_wb.generate_name(length=3, surname='林')
        assert name.startswith('林')
        assert len(name) == 4  # 1 姓氏 + 3 名字字符

    def test_generate_name_pair(self, seeded_wb):
        """生成一对名字。"""
        n1, n2 = seeded_wb.generate_name_pair()
        assert n1 != n2  # 大概率不同（seed=42 时确实不同）
        assert len(n1) >= 2
        assert len(n2) >= 2


class TestCache:
    """词库缓存。"""

    def test_load_caches(self, wb_with_temp_bank):
        """首次加载后缓存。"""
        wb_with_temp_bank.load('test_bank')
        assert 'test_bank' in wb_with_temp_bank._cache

    def test_second_load_uses_cache(self, wb_with_temp_bank):
        """第二次加载直接读缓存。"""
        data1 = wb_with_temp_bank.load('test_bank')
        data2 = wb_with_temp_bank.load('test_bank')
        assert data1 is data2  # 同一对象引用


class TestAllKeys:
    """all_keys() 获取所有 key。"""

    def test_all_keys(self, wb_with_temp_bank):
        """返回词库中所有 key。"""
        keys = wb_with_temp_bank.all_keys('test_bank')
        assert 'key1' in keys
        assert 'key2' in keys
        assert 'empty_key' in keys


class TestGetRNG:
    """get_rng() 获取内部 RNG。"""

    def test_get_rng_deterministic(self, seeded_wb):
        """相同 seed 的 RNG 产生相同序列。"""
        rng1 = seeded_wb.get_rng()
        rng2 = WordBank(seed=42).get_rng()
        assert rng1.randint(1, 1000000) == rng2.randint(1, 1000000)
