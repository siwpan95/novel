"""共享节拍常量 + RNG 种子工具 — 避免在多处重复定义。

Save the Cat! 15 节拍的中文简称映射 + 节拍→世界映射 + 确定性种子派生。
"""
import hashlib
import random

BEAT_NAMES_CN = {
    'opening': '归墟',
    'theme': '锚定者',
    'inciting': '万界',
    'debate': 'GM',
    'break_1': '碎片',
    'b_story': '苍云山',
    'fun_games': '玩家公会',
    'midpoint': '星图',
    'bad_guys': '祂们',
    'all_lost': '代价',
    'dark_night': '第四十七次',
    'break_2': '白夜',
}

# 节拍→世界映射（按卷号）。volume=1 为默认（向后兼容）
BEAT_TO_WORLD = {
    1: {
        'opening': '归墟', 'theme': '归墟', 'inciting': '归墟',
        'debate': '归墟', 'break_1': '武侠·苍云之殇',
        'b_story': '武侠·苍云之殇', 'fun_games': '武侠·苍云之殇',
        'midpoint': '归墟', 'bad_guys': '末日废土',
        'all_lost': '武侠·苍云之殇', 'dark_night': '归墟',
        'break_2': '归墟',
    },
    2: {
        'opening': '东方修仙', 'theme': '东方修仙',
        'inciting': '东方修仙', 'debate': '归墟',
        'break_1': '星际殖民', 'b_story': '星际殖民',
        'fun_games': '东方修仙', 'midpoint': '归墟',
        'bad_guys': '赛博都市', 'all_lost': '归墟',
        'dark_night': '归墟', 'break_2': '归墟',
    },
    3: {
        'opening': '诸神黄昏', 'inciting': '诸神黄昏',
        'debate': '归墟', 'break_1': '克苏鲁深渊',
        'b_story': '归墟', 'fun_games': '归墟',
        'midpoint': '造物主遗迹', 'bad_guys': '归墟',
        'all_lost': '造物主遗迹', 'dark_night': '归墟',
        'break_2': '归墟', 'epilogue': '归墟',
    },
}


def resolve_world(beat: str, volume: int = 1) -> str:
    """根据节拍和卷号返回对应世界名。"""
    mapping = BEAT_TO_WORLD.get(volume, BEAT_TO_WORLD[1])
    return mapping.get(beat, '归墟')


def derive_seed(master_seed: int, component_id: str) -> int:
    """从主 seed 确定性派生子 seed（基于 MD5 哈希，不消耗主 RNG 状态）。

    与 `wb.get_rng().randint()` 不同，本函数：
    - 不受调用顺序影响（相同的 master_seed + component_id 始终产生相同结果）
    - 不消耗主 RNG 的熵
    - 使全局可复现性成为可能
    """
    h = hashlib.md5(f"{master_seed}:{component_id}".encode()).hexdigest()
    return int(h[:8], 16)


def sub_rng(master_seed: int, component_id: str) -> random.Random:
    """从主 seed 确定性派生独立子 RNG。"""
    return random.Random(derive_seed(master_seed, component_id))
