"""WordCountDirector —— 以字数为目标的生成主编排循环（替代现有章/卷循环）。

设计要点（呼应 REDESIGN 重构）：
- 取消「章 / 卷」概念：循环 emit Passage 直到累计字数 >= target_chars。
- 段落渲染复用 IntegratedChapterGenerator 的底层管线
  （_execute_operation / _wire_foreshadowing / _enforce_must_include /
   _voice.render_hook / _quality.process_light / 性格尾句），不重构 generate_chapter，
   保证既有 pytest 不破。
- 卷被移除：volume 不进任何生成逻辑；NarrativeContext.volume 仅留作无用兼容位。
- 伏笔闭环保持「状态驱动」：回收走 plot_state 到期 API；种植改为按段落节奏
  从 foreshadowing_pool 洗牌发牌，不再依赖固定 beat。
- 节奏（prev_tension 调制）保留：导演维护 tension 随机游走，写入 rhythm.last_tension。
"""
import logging
import os
import random
import re
import time

from .narrative_state import derive_state
from .emergent_orchestrator import EmergentOrchestrator
from .narrative_context import NarrativeContext

_logger = logging.getLogger('novel.wordcount')

# 默认配置（详见 spec/Config-Schema.md）
DEFAULT_WC_CONFIG = {
    'min_passage_chars': 200,
    'max_passage_chars': 700,
    'max_passages': None,
    'save_every': 10,
    'log_every': 5,
    'segment_mode': 'natural',
    'soft_milestones': [0.25, 0.5, 0.75],
    'recent_window': 3,
    'avg_op_chars': 110,
    'plant_every': 6,                 # 每 N 段状态化种植一个伏笔
    'rng_seed': 42,
    'volume_label': None,
    'weights': {
        'base_quota': {'scene': 6, 'action': 5, 'battle': 0, 'dialogue': 0, 'reveal': 0, 'hook': 0},
        'state': {
            'tension_high': {'action': 1.3, 'battle': 1.3},
            'pending_foreshadowing': {'reveal': 1.5, 'hook': 1.4},
            'arc_progress_high': {'dialogue': 1.3},
            'recent_repeat_penalty': 0.4,
        },
    },
}

# 目标字数预选（q-3：提供多档，后期手动选；默认用 demo 安全的 tiny）
PRESETS = {
    'tiny': 20_000,     # 演示 / 快速验证
    'small': 50_000,    # 中篇
    'book': 200_000,    # 整书级
    # 中文别名（GUI 使用）
    '短篇': 20_000,
    '中篇': 50_000,
    '长篇': 200_000,
}

# 中文 ↔ 英文映射
PRESET_CN = {
    'tiny': '短篇', 'small': '中篇', 'book': '长篇',
    '短篇': 'tiny', '中篇': 'small', '长篇': 'book',
}

AVG_CHARS_PER_CHAPTER = 1400  # chapters=N 薄封装转发时的换算系数


class WordCountDirector:
    def __init__(self, integrated_gen, plot_state, orchestrator: EmergentOrchestrator,
                 config: dict, output_dir: str):
        self._gen = integrated_gen          # IntegratedChapterGenerator 实例（复用其私有渲染方法）
        self._ps = plot_state
        self._orch = orchestrator
        self._cfg = config
        self._output_dir = output_dir
        self._rng = random.Random(config.get('rng_seed', 42))
        # 跨段去重状态（抗罐头重复 —— 与 TextQualityPipeline.check_repetition 同口径）
        self._long_counter = {}     # 长句全局计数（封顶 2 次）
        self._recent_hooks = []     # 近期钩子，避免跨段雷同

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def generate(self, target_chars: int, *, seed: int = None, resume: bool = False) -> str:
        cfg = self._cfg
        if seed is not None:
            self._rng = random.Random(seed)
            self._orch._rng = random.Random(seed)

        total = 0
        passage_no = 0
        if resume:
            total = self._ps.state.get('current_chars', 0)
            passage_no = self._ps.state.get('current_passage', 0)

        tension = self._ps.state.get('rhythm', {}).get('last_tension', 3)
        recent = list(self._ps.state.get('recent_passage_types', []))
        buffer = []

        max_p = cfg.get('max_passages') or max(50, (target_chars // cfg['min_passage_chars']) * 3)

        _logger.info(f'[字数驱动] 启动 | 目标 {target_chars:,}字 | resume={resume} | 上限 {max_p} 段')
        t0 = time.time()

        while total < target_chars and passage_no < max_p:
            ctx = NarrativeContext()
            ctx.beat = 'generic'          # 大纲被弱化：不再有固定 beat
            ctx.volume = 1                # 兼容位（生成逻辑不读取）
            ctx.world_name = self._orch._pick_world(ctx)
            ctx.tension_level = tension
            ctx.sub_index = 1
            ctx.total_in_beat = 1

            # Layer 3: 预加载当前世界的全键术语缓存到 ctx，供后续任意算子消费
            if hasattr(self._gen, '_voice'):
                ctx.world_terms = self._gen._voice._world_term_pool(ctx.world_name)

            # 字数达标接近时，缩小末段规模，避免严重超出
            remaining = target_chars - total
            if remaining < cfg['min_passage_chars']:
                break

            # 同步角色状态 + 镜头落点
            self._gen._sync_characters(ctx)
            ctx.scene_spot = self._gen._voice._scene_spot(ctx)

            state = derive_state(total, target_chars, tension, self._ps, recent,
                                  passage_no, cfg)

            spec = self._orch.plan(ctx, state)
            text = self._render_passage(ctx, spec.ops, passage_no)
            n = len(text)

            # 过薄保护：补一组算子
            if n < cfg['min_passage_chars']:
                spec = self._orch.plan(ctx, state, extra=True)
                text = self._render_passage(ctx, spec.ops, passage_no)
                n = len(text)

            total += n
            buffer.append(text)
            recent.append(spec.passage_type)
            if len(recent) > 12:
                recent = recent[-12:]

            # 状态化伏笔种植（替代固定 beat 种植）
            if passage_no > 0 and passage_no % cfg['plant_every'] == 0:
                self._plant_foreshadowing(ctx, passage_no)

            # tension 随机游走（驱动下一轮的节奏调制）
            tension = max(0, min(10, tension + self._rng.choice([-1, 0, 0, 1])))
            passage_no += 1

            # 持久化断点
            if passage_no % cfg['save_every'] == 0:
                self._ps.state['current_chars'] = total
                self._ps.state['current_passage'] = passage_no
                self._ps.state['recent_passage_types'] = recent[-10:]
                self._ps.state.setdefault('rhythm', {})['last_tension'] = tension
                self._ps.save()

            if passage_no % cfg['log_every'] == 0:
                _logger.info(
                    f'  第{passage_no}段 | {n}字 | 累计{total:,}/{target_chars:,} '
                    f'| tension={tension} | pending={state.pending_foreshadowing}'
                )

        elapsed = time.time() - t0
        _logger.info(f'[字数驱动] 完成 | {total:,}字 | {passage_no}段 | 耗时{elapsed:.1f}s')
        return self._finalize(buffer, total, target_chars)

    # ------------------------------------------------------------------
    # 段落渲染（复用底层管线）
    # ------------------------------------------------------------------
    def _render_passage(self, ctx, ops, passage_no: int) -> str:
        L = []
        events = []
        changes = []

        for op in ops:
            try:
                lines = self._gen._execute_operation(op, ctx)
            except Exception as e:
                _logger.debug('算子执行跳过 %s: %s', op, e)
                lines = None
            if lines:
                L.extend(lines)

        # 轻量质量管线（与 generate_chapter 同款）
        L = self._gen._quality.process_light(L, ctx.beat)

        # 过薄补充
        if sum(len(x) for x in L) < 150:
            L = self._gen._enrich_thin_chapter(L, ctx.beat, ctx)

        # 伏笔闭环（回收走到期 API；种植由导演按段落节奏触发）
        self._gen._wire_foreshadowing(ctx, ops, L, events, passage_no)
        # 必含元素（generic beat 下 ctx.must_include 为空，自然 no-op）
        self._gen._enforce_must_include(ctx, L, events)

        # 章末钩子（追读率命门）：每段以钩子收束；跨段 + 全局封顶 2 次去重
        hook_text = self._pick_hook(ctx)
        if hook_text:
            if L and L[-1].strip():
                L.append('')
            L.append(hook_text)
            self._recent_hooks.append(hook_text)

        # 跨段长句去重（抗罐头）：覆盖 ops + 伏笔回收 + 钩子，与 check_repetition
        # 同口径（[。！？!?\n] 切句、去空白、>=15 字），全局封顶 2 次，
        # 超出则丢弃该行（第 3+ 次出现的长句），从根上消灭「罐头重复」。
        L = self._dedup_long_sentences(L)

        # 持久化：current_chapter 兼容千层饼/伏笔 API；current_chars 供 resume
        self._ps.state['current_chapter'] = passage_no
        self._ps.state.setdefault('rhythm', {})['last_tension'] = ctx.tension_level
        try:
            self._gen._ps.add_chapter_summary(passage_no, f'第{passage_no}段（{ctx.beat}）', events, changes)
        except Exception:
            pass

        return '\n'.join(L)

    # ------------------------------------------------------------------
    # 跨段去重（抗罐头重复）
    # ------------------------------------------------------------------
    @staticmethod
    def _norm_sent(s: str) -> str:
        return re.sub(r'\s+', '', s)

    def _long_sentences(self, text: str) -> list:
        """与 TextQualityPipeline.check_repetition 同口径抽取 >=15 字长句。"""
        out = []
        for s in re.split(r'[。！？!?\n]', text):
            sn = self._norm_sent(s)
            if len(sn) < 15:
                continue
            if not re.search(r'[\u4e00-\u9fffA-Za-z0-9]', sn):
                continue
            out.append(sn)
        return out

    def _dedup_long_sentences(self, L: list) -> list:
        text = '\n'.join(L)
        # 先更新本段长句的全局计数
        for sn in self._long_sentences(text):
            self._long_counter[sn] = self._long_counter.get(sn, 0) + 1
        # 丢弃含「已超 2 次」长句的行（封顶 2 次，第 3+ 次出现直接剔除）
        new_L = []
        for line in L:
            over = False
            for s in re.split(r'[。！？!?]', line):
                sn = self._norm_sent(s)
                if len(sn) < 15:
                    continue
                if self._long_counter.get(sn, 0) > 2:
                    over = True
                    break
            if not over:
                new_L.append(line)
        return new_L

    def _pick_hook(self, ctx) -> str:
        """章末钩子：跨段 + 全局封顶 2 次去重，避免雷同。

        优先返回「近期 10 段未用 且 全局出现 < 2 次」的钩子；
        若池耗尽或候选均已超 2 次，返回 None（本段不强加钩子，
        以保住全本 max_count<=2 这一抗罐头硬指标）。
        """
        last = [self._norm_sent(h) for h in self._recent_hooks[-10:]]
        for _ in range(12):
            cand = self._gen._voice.render_hook(ctx)
            if not cand:
                break
            sn = self._norm_sent(cand)
            if sn in last:
                continue
            if self._long_counter.get(sn, 0) >= 2:
                continue
            return cand
        return None

    # ------------------------------------------------------------------
    # 状态化伏笔种植（替代固定 beat 种植）
    # ------------------------------------------------------------------
    def _plant_foreshadowing(self, ctx, passage_no: int):
        try:
            pool = self._gen._foreshadowing_pool()
            seeds = []
            for beat_seeds in pool.get('seeds', {}).values():
                seeds.extend(beat_seeds)
            if not seeds:
                return
            seed = self._gen._voice._deal('foreshadow::emergent', seeds)
            if not seed:
                return
            fid = seed['id']
            if any(f['id'] == fid for f in self._ps.state.get('foreshadowing', [])):
                return
            lo, hi = seed.get('recovery_offset', [3, 8])
            planned = passage_no + self._rng.randint(int(lo), int(hi))
            self._ps.add_foreshadowing(
                fid, seed['content'], passage_no, planned,
                recovery_text=seed.get('recovery_text', ''),
            )
        except Exception as e:
            _logger.debug('状态化伏笔种植跳过: %s', e)

    # ------------------------------------------------------------------
    # 收尾 / 输出
    # ------------------------------------------------------------------
    def _finalize(self, buffer: list, total: int, target_chars: int) -> str:
        full = '\n\n'.join(buffer)
        ts = time.strftime('%Y%m%d_%H%M%S')
        label = self._cfg.get('volume_label')
        name_part = f'_卷{label}' if label else ''
        out_path = os.path.join(self._output_dir, f'万界归墟_字数目标{name_part}_{total}字_{ts}.txt')
        os.makedirs(self._output_dir, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('《万界归墟》· 字数目标生成（弱化大纲 / 状态驱动）\n')
            f.write(f'目标字数：{target_chars:,}　实得字数：{total:,}\n\n')
            f.write(full)
        # 收尾持久化
        self._ps.state['current_chars'] = total
        self._ps.state['current_passage'] = len(buffer)
        self._ps.save()
        return out_path
