"""plot_state.py 单元测试 — 状态机核心逻辑。

覆盖：初始化、CRUD、状态转换、千层饼触发矩阵、伏笔生命周期。
"""



class TestPlotStateInit:
    """初始化测试。"""

    def test_init_state_has_required_keys(self, empty_plot_state):
        """验证初始状态包含所有必需 key。"""
        required_keys = ['meta', 'characters', 'plot_flags', 'foreshadowing',
                         'worlds_unlocked', 'fragment_count', 'truth_layer',
                         'current_chapter']
        for key in required_keys:
            assert key in empty_plot_state.state, f'缺少 key: {key}'

    def test_init_state_fragment_count_zero(self, empty_plot_state):
        """初始碎片计数为 0。"""
        assert empty_plot_state.state['fragment_count'] == 0

    def test_init_state_truth_layer_one(self, empty_plot_state):
        """初始千层饼层级为 1。"""
        assert empty_plot_state.state['truth_layer'] == 1

    def test_init_state_current_chapter_zero(self, empty_plot_state):
        """初始章号为 0。"""
        assert empty_plot_state.state['current_chapter'] == 0


class TestCharacterCRUD:
    """角色状态 CRUD 测试。"""

    def test_set_and_get_char_state(self, empty_plot_state):
        """设置并读取角色状态。"""
        empty_plot_state.set_char_state('林朔', 'location', '归墟')
        assert empty_plot_state.get_char_state('林朔', 'location') == '归墟'

    def test_get_char_state_full_dict(self, empty_plot_state):
        """获取完整角色状态字典。"""
        empty_plot_state.set_char_state('林朔', 'emotional_state', '警觉')
        char = empty_plot_state.get_char_state('林朔')
        assert 'emotional_state' in char
        assert char['emotional_state'] == '警觉'

    def test_get_nonexistent_char_returns_empty(self, empty_plot_state):
        """不存在的角色返回空字典。"""
        result = empty_plot_state.get_char_state('不存在的角色')
        assert result == {}

    def test_get_nonexistent_key_returns_none(self, empty_plot_state):
        """不存在的 key 返回 None。"""
        empty_plot_state.set_char_state('林朔', 'location', '归墟')
        result = empty_plot_state.get_char_state('林朔', '不存在的key')
        assert result is None


class TestPlotFlags:
    """情节开关测试。"""

    def test_set_and_get_plot_flag(self, empty_plot_state):
        """设置并读取情节开关。"""
        empty_plot_state.set_plot_flag('first_fragment_recovered', True)
        assert empty_plot_state.get_plot_flag('first_fragment_recovered') is True

    def test_unset_flag_defaults_to_false(self, empty_plot_state):
        """未设置的开关默认为 False。"""
        assert empty_plot_state.get_plot_flag('不存在的开关') is False

    def test_toggle_flag(self, empty_plot_state):
        """开关可切换。"""
        empty_plot_state.set_plot_flag('anchor_protocol_active', True)
        assert empty_plot_state.get_plot_flag('anchor_protocol_active') is True
        empty_plot_state.set_plot_flag('anchor_protocol_active', False)
        assert empty_plot_state.get_plot_flag('anchor_protocol_active') is False


class TestTruthProgress:
    """千层饼揭秘进度测试 — 核心逻辑。"""

    def test_check_truth_progress_layer2(self, empty_plot_state):
        """第 1→2 层触发：1 碎片 + 已回收标志 + 到第 49 章。"""
        empty_plot_state.state['fragment_count'] = 1
        empty_plot_state.set_plot_flag('first_fragment_recovered', True)
        empty_plot_state.state['current_chapter'] = 49
        result = empty_plot_state.check_truth_progress()
        assert result == 2

    def test_check_truth_progress_not_enough_fragments(self, empty_plot_state):
        """碎片不足时不触发。"""
        empty_plot_state.state['fragment_count'] = 0
        empty_plot_state.set_plot_flag('first_fragment_recovered', True)
        empty_plot_state.state['current_chapter'] = 49
        result = empty_plot_state.check_truth_progress()
        assert result is None  # 条件不满足，不触发

    def test_check_truth_progress_not_enough_chapters(self, empty_plot_state):
        """章数不够时不触发。"""
        empty_plot_state.state['fragment_count'] = 1
        empty_plot_state.set_plot_flag('first_fragment_recovered', True)
        empty_plot_state.state['current_chapter'] = 20
        result = empty_plot_state.check_truth_progress()
        assert result is None  # 条件不满足，不触发

    def test_auto_advance_truth_returns_narrative(self, empty_plot_state):
        """自动推进千层饼返回叙事文本。"""
        empty_plot_state.state['fragment_count'] = 1
        empty_plot_state.set_plot_flag('first_fragment_recovered', True)
        empty_plot_state.state['current_chapter'] = 49
        result = empty_plot_state.auto_advance_truth()
        assert result is not None
        assert isinstance(result, dict)
        assert 'layer' in result
        assert 'narrative' in result

    def test_auto_advance_saves_state(self, empty_plot_state):
        """自动推进后保存状态。"""
        empty_plot_state.state['fragment_count'] = 1
        empty_plot_state.set_plot_flag('first_fragment_recovered', True)
        empty_plot_state.state['current_chapter'] = 49
        old_layer = empty_plot_state.state['truth_layer']
        empty_plot_state.auto_advance_truth()
        assert empty_plot_state.state['truth_layer'] > old_layer


class TestForeshadowing:
    """伏笔生命周期测试。"""

    def test_add_foreshadowing(self, empty_plot_state):
        """添加伏笔。"""
        empty_plot_state.add_foreshadowing(
            foreshadow_id='guixu_rumble',
            content='归墟深处有异动',
            planted_chapter=5,
            planned_recovery=10
        )
        assert len(empty_plot_state.state['foreshadowing']) >= 1
        fs = empty_plot_state.state['foreshadowing'][-1]
        assert fs['content'] == '归墟深处有异动'
        assert fs['planned_recovery_chapter'] == 10
        assert fs['status'] == 'active'

    def test_recover_foreshadowing(self, empty_plot_state):
        """回收伏笔。"""
        empty_plot_state.add_foreshadowing(
            foreshadow_id='first_fragment_glow',
            content='第一块碎片的光芒',
            planted_chapter=3,
            planned_recovery=5
        )
        empty_plot_state.recover_foreshadowing(
            foreshadow_id='first_fragment_glow',
            recovery_chapter=5
        )
        # 验证伏笔状态已更新
        fs = empty_plot_state.state['foreshadowing'][0]
        assert fs['status'] == 'recovered'
        assert fs['recovered_chapter'] == 5

    def test_recover_nonexistent_foreshadowing(self, empty_plot_state):
        """回收不存在的伏笔无副作用。"""
        count_before = len(empty_plot_state.state['foreshadowing'])
        empty_plot_state.recover_foreshadowing('不存在的伏笔', 10)
        # 不应新增或修改任何伏笔
        assert len(empty_plot_state.state['foreshadowing']) == count_before


class TestWorldProgression:
    """世界解锁与探索测试。"""

    def test_get_next_world_returns_valid(self, empty_plot_state):
        """获取下一个待探索世界，返回 (layer, world_name) 元组或 None。"""
        world = empty_plot_state.get_next_world_to_explore()
        # layer_1 中有已解锁但未回收碎片的世界
        if world is not None:
            assert isinstance(world, tuple), f'期望 tuple，得到 {type(world)}'
            assert len(world) == 2
            assert isinstance(world[1], str)

    def test_unlock_world(self, empty_plot_state):
        """解锁世界（'东方修仙' 在 layer_2）。"""
        empty_plot_state.unlock_world(layer=2, world_name='东方修仙')
        worlds = empty_plot_state.state['worlds_unlocked']['layer_2']
        assert '东方修仙' in worlds
        assert worlds['东方修仙']['unlocked'] is True
