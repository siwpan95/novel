# -*- coding: utf-8 -*-
"""WorldState —— 世界空间模型，替代 scene_locations 洗牌发牌。

设计原则：
  1. 空间连续性：地点之间有路径、距离，角色移动需要时间，不能瞬移。
  2. 区域差异化：不同区域有不同的事件密度、势力分布、危险等级。
  3. 状态随时间演化：势力扩张/收缩、资源消耗/再生、气候周期。

数据结构：
  WorldMap  = 世界的全部已知地点 + 邻接关系（无向带权图）
  Region    = 地图上的一个区域（含天气/危险/势力/事件密度）
  Path      = 两区域间的连接（含距离/难度/传送门标志）
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# 区域定义
# ---------------------------------------------------------------------------
@dataclass
class Region:
    """世界中的一个区域——城镇、废墟、战场、荒野等。"""
    name: str
    category: str = 'wilderness'  # town / ruin / battlefield / wilderness / dungeon / port
    danger: int = 1               # 1-10，影响遭遇频率和战斗强度
    description: str = ''
    factions_present: list[str] = field(default_factory=list)
    npc_count: int = 0
    resources: dict = field(default_factory=dict)  # resource_name → amount
    weather_bias: str = 'temperate'  # 气候倾向

    # 动态状态（在 tick 中更新）
    current_danger: int = 0         # 当前危险等级（含势力冲突叠加）
    event_density: float = 0.3      # 事件密度 0-1，越高越活跃
    last_visited: int = 0           # 时间步——上次被角色访问

    def __post_init__(self):
        if self.current_danger == 0:
            self.current_danger = self.danger


# ---------------------------------------------------------------------------
# 连接定义
# ---------------------------------------------------------------------------
@dataclass
class Path:
    """两个区域之间的通路。"""
    region_a: str
    region_b: str
    distance: int = 1          # 旅行时间步数
    difficulty: int = 1        # 1-5，越高越需要准备/检查
    is_portal: bool = False    # 传送门——瞬间到达
    is_hidden: bool = False    # 隐藏路径——需要特定条件发现
    discover_condition: str = ''


# ---------------------------------------------------------------------------
# 世界地图
# ---------------------------------------------------------------------------
class WorldMap:
    """一个世界的地图：区域集合 + 邻接图。"""

    def __init__(self, world_name: str):
        self.world_name = world_name
        self._regions: dict[str, Region] = {}
        self._paths: list[Path] = []
        self._neighbors: dict[str, list[str]] = {}  # region → 相邻区域列表

    # -- 构造 API -----------------------------------------------------------
    def add_region(self, region: Region):
        self._regions[region.name] = region
        if region.name not in self._neighbors:
            self._neighbors[region.name] = []

    def add_path(self, path: Path):
        self._paths.append(path)
        self._neighbors.setdefault(path.region_a, []).append(path.region_b)
        self._neighbors.setdefault(path.region_b, []).append(path.region_a)

    def region(self, name: str) -> Optional[Region]:
        return self._regions.get(name)

    def neighbors(self, region_name: str) -> list[str]:
        return self._neighbors.get(region_name, [])

    def path_to(self, a: str, b: str) -> Optional[Path]:
        for p in self._paths:
            if (p.region_a == a and p.region_b == b) or (p.region_a == b and p.region_b == a):
                return p
        return None

    def all_regions(self) -> list[str]:
        return list(self._regions.keys())

    def all_paths(self) -> list[Path]:
        return list(self._paths)

    # -- 查询 API -----------------------------------------------------------
    def reachable(self, from_region: str, max_dist: int = 3) -> list[str]:
        """从指定区域出发，在 max_dist 距离内可达的所有区域。"""
        visited = {from_region}
        frontier = {from_region}
        for _ in range(max_dist):
            nxt = set()
            for r in frontier:
                for nb in self.neighbors(r):
                    if nb not in visited:
                        p = self.path_to(r, nb)
                        if p and not p.is_hidden:
                            nxt.add(nb)
            visited |= nxt
            frontier = nxt
        return sorted(visited)

    def travel_distance(self, a: str, b: str) -> int:
        """BFS 最短路径距离（跳数），不考虑权重时为-1。"""
        if a == b:
            return 0
        visited = {a}
        q = [(a, 0)]
        while q:
            cur, dist = q.pop(0)
            for nb in self.neighbors(cur):
                if nb == b:
                    return dist + 1
                if nb not in visited:
                    visited.add(nb)
                    q.append((nb, dist + 1))
        return -1

    # -- 演化 API -----------------------------------------------------------
    def tick(self, time_step: int, rng: random.Random):
        """世界状态随时间演化：势力变动、资源消长、事件密度变化。"""
        for region in self._regions.values():
            # 危险度自然衰减 + 随机波动
            region.current_danger = max(
                1, min(10,
                       int(region.danger + rng.randint(-1, 2) + (time_step % 10 == 0) * 2)
                       ))
            # 事件密度随危险度上升
            region.event_density = min(1.0, 0.2 + region.current_danger * 0.08)
            # 资源自然再生
            for k in region.resources:
                region.resources[k] = min(100, region.resources.get(k, 0) + rng.randint(0, 3))


# ---------------------------------------------------------------------------
# 世界工厂——从词库数据自动生成地图
# ---------------------------------------------------------------------------
def build_world_from_banks(world_name: str, wb, rng: random.Random) -> WorldMap:
    """从词库数据自动构建世界地图。

    读取 scene_locations 获取地点列表 → 按区域类型分类 →
    自动建立邻接关系 → 返回 WorldMap。
    """
    wm = WorldMap(world_name)
    try:
        data = wb.load('scene_locations')
        locations = data.get(world_name, [])
    except Exception:
        locations = []

    if not locations:
        # fallback：最少一个中心区域
        wm.add_region(Region(name=f'{world_name}·中心', category='town', danger=1))
        return wm

    # 地点分类
    categories = {
        'ruin': [], 'town': [], 'wilderness': [], 'battlefield': [], 'dungeon': [],
    }
    for loc in locations:
        if isinstance(loc, str):
            # heuristic: 关键词分类
            cat = 'wilderness'
            for kw, c in [('废墟', 'ruin'), ('遗迹', 'ruin'), ('城', 'town'),
                          ('镇', 'town'), ('村', 'town'), ('战场', 'battlefield'),
                          ('洞', 'dungeon'), ('墓', 'dungeon'), ('殿', 'dungeon')]:
                if kw in loc:
                    cat = c
                    break
            categories.setdefault(cat, []).append(loc)

    # 创建区域节点
    all_regions = []
    for cat, locs in categories.items():
        for loc_name in locs:
            danger = {'town': 2, 'wilderness': 4, 'ruin': 6, 'battlefield': 8, 'dungeon': 7}.get(cat, 3)
            region = Region(
                name=loc_name, category=cat, danger=danger + rng.randint(-1, 1),
                event_density={'town': 0.4, 'wilderness': 0.3, 'ruin': 0.5,
                               'battlefield': 0.8, 'dungeon': 0.6}.get(cat, 0.3),
                weather_bias=rng.choice(['temperate', 'harsh', 'mystical']),
            )
            wm.add_region(region)
            all_regions.append(loc_name)

    # 自动建立邻接关系：相邻分类之间随机连边
    for i, a in enumerate(all_regions):
        for j in range(i + 1, min(i + 4, len(all_regions))):
            b = all_regions[j]
            if a != b and not wm.path_to(a, b):
                dist = rng.randint(1, 3)
                diff = rng.randint(1, 3)
                wm.add_path(Path(region_a=a, region_b=b, distance=dist, difficulty=diff))

    return wm


# ---------------------------------------------------------------------------
# 世界状态管理器——跨世界
# ---------------------------------------------------------------------------
class WorldStateManager:
    """管理当前激活的世界及其地图、时间、角色位置。"""

    def __init__(self, wb, seed: int = None):
        self._wb = wb
        self._rng = random.Random(seed)
        self._worlds: dict[str, WorldMap] = {}     # world_name → WorldMap
        self._active_world: str = '归墟'
        self._global_time: int = 0                 # 全局时间步
        self._world_unlock_order: list[str] = []    # 世界解锁顺序
        self._unlocked_worlds: set[str] = {'归墟'}

    def load_world(self, world_name: str) -> WorldMap:
        if world_name not in self._worlds:
            self._worlds[world_name] = build_world_from_banks(world_name, self._wb, self._rng)
        return self._worlds[world_name]

    def active_map(self) -> WorldMap:
        return self.load_world(self._active_world)

    def switch_to(self, world_name: str):
        """切换到指定世界（传送/跨世界移动）。"""
        if world_name not in self._unlocked_worlds:
            self._unlocked_worlds.add(world_name)
        self._active_world = world_name
        self.load_world(world_name)  # 确保加载

    def unlock_world(self, world_name: str):
        self._unlocked_worlds.add(world_name)
        if world_name not in self._world_unlock_order:
            self._world_unlock_order.append(world_name)

    def tick(self):
        """世界时钟前进一格。"""
        self._global_time += 1
        for wm in self._worlds.values():
            wm.tick(self._global_time, self._rng)

    @property
    def global_time(self) -> int:
        return self._global_time
