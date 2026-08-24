# -*- coding: utf-8 -*-
"""双引擎统一编排器：深度融合 —— 因果结构驱动 ASP词库渲染。

核心理念（v2.1 真融合）：
  不再是"先A后B"的模式切换，而是"大脑+声音"的深度融合。
  - 因果引擎 = 大脑：决定说什么（节拍/角色/情绪/事件）
  - ASP引擎 = 声音：决定怎么说（词库/模板/描写/变化）
  - NarrativeContext = 桥梁：两者共享的状态总线
  - IntegratedChapterGenerator = 执行：一次生成，双引擎同时工作

模式：
  words     — ★默认推荐：以字数为目标的涌现式生成（弱化大纲 / 状态驱动 / 抗罐头）
  asp       — 纯ASP模板流（向后兼容）
  causal    — 纯因果链流（向后兼容，使用旧版硬编码生成器）
  integrated — words 的薄封装别名（chapters 换算为字数，向后兼容，不推荐新用）
"""

import os
import sys
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 日志配置：同时输出到控制台和文件
logger = logging.getLogger('novel_generator')
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _fh = logging.FileHandler(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'novel_generator.log'),
        encoding='utf-8'
    )
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    ))
    _ch = logging.StreamHandler(sys.stdout)
    _ch.setLevel(logging.INFO)
    _ch.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(_fh)
    logger.addHandler(_ch)

from novel_generator.engine.word_bank import WordBank
from novel_generator.engine.plot_state import PlotState
from novel_generator.engine.generators.novel import NovelGenerator
from novel_generator.engine.generators.character import CharacterGenerator
from novel_generator.engine.generators.chapter import ChapterGenerator
from novel_generator.engine.generators.battle import BattleGenerator, SceneGenerator
from novel_generator.engine.causal_chapter import CausalChapterGenerator
from novel_generator.engine.integrated_chapter_generator import IntegratedChapterGenerator
from novel_generator.engine.rubric_player import RubricEngine, PlayerArchetypeEngine, FamousSceneEngine
from novel_generator.engine.text_quality import TextQualityPipeline
from novel_generator.engine.rashomon import RashomonEngine, InfoMatrix
from novel_generator.engine.expansion import ExpansionEngine, WorldSenseInjector
from novel_generator.engine.rhythm_engine import RhythmEngine
from novel_generator.engine.fusion_generator import FusionGenerator
from novel_generator.engine.dealer import MarkovTransitions
from novel_generator.engine.wordcount_director import (
    WordCountDirector, DEFAULT_WC_CONFIG, PRESETS, AVG_CHARS_PER_CHAPTER,
)
from novel_generator.engine.emergent_orchestrator import EmergentOrchestrator


class UnifiedNovelEngine:
    """双引擎统一编排器。

    路径体系（v2.1 → v3.0）：
      ★ words   — 唯一推荐：以字数为目标的涌现式生成（EmergentOrchestrator，状态驱动）
      ⚠ causal  — DEPRECATED：旧版硬编码因果链（计划 v3.0 移除）
      ⚠ asp     — DEPRECATED：纯ASP模板流（计划 v3.0 移除）
      ⚠ integrated — DEPRECATED：words 的薄封装别名（不推荐新用）

    Usage:
        engine = UnifiedNovelEngine(seed=42)
        engine.generate_by_words(preset='small')          # ★推荐
        engine.generate(mode='causal', chapters=80)       # ⚠ 废弃
    """

    def __init__(self, seed=42, output_dir=None, dealer_cfg=None):
        self._seed = seed
        self._dealer_cfg = dealer_cfg
        self._output_dir = output_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'output'
        )
        os.makedirs(self._output_dir, exist_ok=True)

        # 共享核心
        self.wb = WordBank(seed=seed)
        self.plot_state = PlotState()
        self.rng = self.wb.get_rng()

        # ASP 引擎组件
        self.asp_novel = NovelGenerator(seed=seed)
        self.asp_chapter = ChapterGenerator(self.wb)
        self.asp_character = CharacterGenerator(self.wb)

        # ================================================================
        # 共享组件（先创建，再注入到子生成器中，消除双重实例化）
        # ================================================================
        self.rubric = RubricEngine(seed)
        self.player_engine = PlayerArchetypeEngine(seed)
        self.quality = TextQualityPipeline(seed)
        self.rashomon = RashomonEngine(seed)
        self.info = InfoMatrix()
        self.expansion = ExpansionEngine(seed)
        self.world_sense = WorldSenseInjector(seed)
        self.rhythm = RhythmEngine(seed)
        # 懒加载组件（仅首次访问时创建）
        self._famous_scenes = None
        self._fusion = None

        self.battle_gen = BattleGenerator(self.wb)
        self.scene_gen = SceneGenerator(self.wb)

        # ================================================================
        # 子生成器（注入共享组件，避免内部重复创建）
        # ================================================================
        # 因果链引擎（旧版，硬编码文本）—— 懒加载：
        # 默认 integrated 路径不再构建这套废弃引擎，仅在 --mode causal 或预览大纲时按需创建
        self._causal_gen = None

        # ★ 融合引擎（新版，因果结构+ASP词库渲染）
        self.integrated_gen = IntegratedChapterGenerator(
            self.wb, self.plot_state, seed,
            rubric=self.rubric, player_engine=self.player_engine,
            quality=self.quality, rashomon=self.rashomon,
            info=self.info, expansion=self.expansion,
            world_sense=self.world_sense, rhythm=self.rhythm,
            dealer_cfg=dealer_cfg,
        )

        # ================================================================
        # 统一入口
        # ================================================================

    # ================================================================
    # 懒加载组件（仅首次访问时创建，节省 non-integrated 模式下的内存）
    # ================================================================
    @property
    def famous_scenes(self):
        if self._famous_scenes is None:
            self._famous_scenes = FamousSceneEngine(self._seed)
        return self._famous_scenes

    @property
    def fusion(self):
        if self._fusion is None:
            self._fusion = FusionGenerator(self._seed)
        return self._fusion

    @property
    def causal_gen(self):
        """旧版因果链生成器——懒加载（默认 integrated 路径不构建废弃引擎）。"""
        if self._causal_gen is None:
            self._causal_gen = CausalChapterGenerator(
                self.wb, self.plot_state,
                rubric=self.rubric, player_engine=self.player_engine,
                quality=self.quality, rashomon=self.rashomon,
                info=self.info, expansion=self.expansion,
                world_sense=self.world_sense, rhythm=self.rhythm,
            )
        return self._causal_gen

    def generate(self, mode='words', **kwargs):
        """统一生成入口。

        Args:
            mode: 'words'(★唯一推荐) | 'asp'(⚠废弃) | 'causal'(⚠废弃) | 'integrated'(⚠废弃)
            **kwargs: chapters / target_chars / preset / resume / volume_label / skip_rubric 等
        """
        if mode == 'asp':
            logger.warning('[generate] mode=asp 已废弃，请使用 mode=words。asp 路径计划 v3.0 移除。')
            return self._gen_asp(**kwargs)
        elif mode == 'causal':
            logger.warning('[generate] mode=causal 已废弃，请使用 mode=words。causal 路径计划 v3.0 移除。')
            return self._gen_causal(**kwargs)
        elif mode == 'words':
            return self.generate_by_words(**kwargs)
        elif mode in ('hybrid', 'integrated'):
            logger.warning(
                '[generate] mode=integrated/hybrid 已废弃。'
                '请使用 mode=words 或直接调用 generate_by_words()。'
            )
            chapters = kwargs.pop('chapters', kwargs.pop('chapters_per_volume', None))
            if 'volume' in kwargs:
                logger.warning('[generate] volume 参数已废弃（卷从生成逻辑移除），忽略。')
                kwargs.pop('volume')
            kwargs.pop('start_chapter', None)
            target = (int(chapters) * AVG_CHARS_PER_CHAPTER) if chapters else \
                kwargs.pop('target_chars', PRESETS['tiny'])
            return self.generate_by_words(target_chars=target, **kwargs)
        else:
            raise ValueError(f"未知模式: {mode}，可选: asp / causal / integrated / words")

    # ================================================================
    # 字数目标生成（弱化大纲 / 状态驱动 / 卷已移除）
    # ================================================================
    def generate_by_words(self, target_chars=None, preset=None, resume=False,
                          volume_label=None, **kwargs):
        """以字数为目标的生成入口。

        Args:
            target_chars: 目标字数；为 None 时用 preset（默认 tiny）。
            preset: 'tiny'(2万) / 'small'(5万) / 'book'(20万)。
            resume: 从 plot_state.current_chars 断点续写。
            volume_label: 可选元数据标签（仅用于输出文件名），不参与生成逻辑。
        """
        if target_chars is None:
            target_chars = PRESETS.get(preset, PRESETS['tiny'])
        return self._gen_by_words(target_chars=target_chars, resume=resume,
                                  volume_label=volume_label)

    def _gen_by_words(self, target_chars, resume=False, volume_label=None):
        """构建字数驱动导演并执行。复用 integrated_gen 的底层渲染管线。"""
        config = dict(DEFAULT_WC_CONFIG)
        if volume_label is not None:
            config['volume_label'] = volume_label
        orch = EmergentOrchestrator(
            self.integrated_gen._voice, config,
            rng=self.integrated_gen._wb.get_rng(),
        )
        director = WordCountDirector(
            self.integrated_gen, self.plot_state, orch, config, self._output_dir,
        )
        return director.generate(target_chars, resume=resume)

    # ================================================================
    # 发牌员增强：bootstrap 转移矩阵（供 Layer2 加载）
    # ================================================================
    def bootstrap_dealer(self, target_chars=None, matrix_path=None):
        """收集真实发牌序列 → 构建马尔可夫转移矩阵 → 落盘 JSON。

        生成的转移矩阵供 Layer2（发牌员马尔可夫增强）在正式生成时加载：
        VoiceEngine 据此在 7-bag 内部按「上一张 → 下一张」的转移计数加权重排发牌，
        使相邻发牌更符合语感。矩阵与 seed 无关（转移是结构性的），默认用 tiny 规模
        即可覆盖主要 queue_key；结果落盘到 matrix_path（默认 data/deal_transitions.json）。
        """
        from novel_generator.engine.wordcount_director import PRESETS
        voice = self.integrated_gen._voice
        voice.begin_deal_recording()
        target = target_chars or PRESETS.get('tiny', 20000)
        self.generate_by_words(target_chars=target)
        log = voice.end_deal_recording()

        mk = MarkovTransitions(self._dealer_cfg.get('markov') if self._dealer_cfg else None)
        mk.build_from_log(log)

        if matrix_path is None:
            matrix_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'deal_transitions.json')
        matrix_path = os.path.abspath(matrix_path)
        os.makedirs(os.path.dirname(matrix_path), exist_ok=True)
        mk.save(matrix_path)
        logger.info('[bootstrap_dealer] 转移矩阵已构建: %s（%d 个队列，%d 条发牌记录）',
                    matrix_path, len(mk.matrix), len(log))
        return matrix_path

        # ================================================================
        # ASP 模式：模板循环流
        # ================================================================
    def _gen_asp(self, volumes=3, chapters_per_volume=7,
                 opponents_per_chapter=4, **kwargs):
        """ASP模板引擎模式——海量文本批量生成。"""
        logger.info(f'[ASP引擎] 启动 | {volumes}部×{chapters_per_volume}章×{opponents_per_chapter}对手')
        t0 = time.time()

        text = self.asp_novel.generate(
            volumes=volumes,
            chapters_per_volume=chapters_per_volume,
            opponents_per_chapter=opponents_per_chapter,
        )

        elapsed = time.time() - t0
        logger.info(f'[ASP引擎] 完成 | 耗时 {elapsed:.1f}s')

        return text

        # ================================================================
        # Causal 模式：因果链流
        # ================================================================
    def _gen_causal(self, chapters=80, skip_rubric=False, **kwargs):
        """因果链引擎模式——有情节状态追踪的节拍驱动生成。"""
        logger.info(f'[因果引擎] 启动 | {chapters}章 Save the Cat! 15节拍')
        t0 = time.time()

        outline = self.causal_gen.generate_outline(chapters)

        all_chapters = []
        total_chars = 0
        all_scores = []

        for entry in outline:
            ch = entry['chapter']
            try:
                text = self.causal_gen.generate_chapter(ch, entry)
            except Exception as e:
                logger.error(
                    f'第{ch}章 [{entry["beat"]}] 生成失败: {e}', exc_info=True
                )
                continue
            all_chapters.append('\n' + '=' * 40 + '\n' + text)
            chars = len(text)
            total_chars += chars

            # 安全网：章节内逐字重复检测（P0 防御）
            rep = self.quality.check_repetition(text)
            if rep['max_count'] >= 3 and rep['repeated']:
                logger.warning(
                    f'  第{ch:2d}章 [{entry["beat"]:10s}] 检测到逐字重复句（最多{rep["max_count"]}次）'
                    f' 示例：「{rep["repeated"][0][0][:20]}…」'
                )

            if not skip_rubric:
                result = self.rubric.evaluate(text, entry['beat'])
                all_scores.append((ch, result['total'], result['verdict']))
                if result['total'] < 2.5:
                    logger.warning(
                        f'  第{ch:2d}章 [{entry["beat"]:10s}] Rubric:{result["total"]:.1f} '
                        f'低于阈值 2.5'
                    )
                if ch % 5 == 0 or ch <= 5:
                    logger.info(
                        f'  第{ch:2d}章 [{entry["beat"]:10s}] {chars:4d}字 '
                        f'Rubric:{result["total"]:.1f}'
                    )

        full_text = '\n'.join(all_chapters)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(
            self._output_dir,
            f'万界归墟_第一卷_全{chapters}章_{timestamp}.txt'
        )

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f'《万界归墟》第一卷 全{chapters}章\n')
            f.write(f'总字数：{total_chars:,}\n\n')
            f.write(full_text)

        elapsed = time.time() - t0
        avg_score = (sum(s[1] for s in all_scores) / len(all_scores)
                     if all_scores else 0)
        logger.info(f'[因果引擎] 完成 | {total_chars:,}字 | '
              f'Rubric均分:{avg_score:.1f} | 耗时{elapsed:.1f}s')

        return output_path

        # ================================================================
        # [已取消] 旧 Integrated 章/卷循环逻辑已移除，转发到字数目标生成
        # ================================================================
    def _gen_integrated(self, chapters=80, volume=1, start_chapter=1, skip_rubric=False,
                        resume=False, **kwargs):
        """[已取消] 旧「章/卷循环」生成逻辑已移除，转发到字数目标生成。

        原逻辑：generate_outline（Save the Cat 15 拍硬编码到章号）+ 按卷 dispatch +
        固定 _QUOTA[beat] 算子数 —— 即「罐头式脚本驱动」结构，已取消。
        现统一走 WordCountDirector（以字数为目标、状态驱动、卷已移除）。

        - volume / start_chapter 参数已废弃，不再影响生成（仅告警一次）。
        - chapters 仅作为字数换算系数（chapters × AVG_CHARS_PER_CHAPTER）。
        """
        if volume != 1 or start_chapter != 1:
            logger.warning('[generate] volume/start_chapter 已废弃（章/卷逻辑已取消），忽略。')
        target = int(chapters) * AVG_CHARS_PER_CHAPTER
        return self._gen_by_words(target_chars=target, resume=resume)

        # ================================================================
        # ASP词库注入器：为因果章节注入更丰富的模板化描写
        # ================================================================
    def _asp_boost_inject(self, text, beat, chapter_num):
        """在因果链生成的章节中注入ASP词库的丰富描写。"""
        injections = []

        # 注入1个随机角色的外貌扩展（24部位中的8个关键部位）
        if self.rng.random() < 0.6:
            char = self.asp_character.generate()
            # 只取8个关键部位的精简外貌
            key_parts = self.rng.sample(
                ['头', '脸', '眼', '身', '手', '声', '形', '气'], 4
            )
            lines = [f'\n【{char["name"]}的外貌】']
            for part in key_parts:
                desc = self.wb.get_random(part, 'body_parts')
                if desc:
                    lines.append(f'{part}：{desc}')
            lines.append('')
            injections.append('\n'.join(lines))

        # 注入环境描写增强
        if self.rng.random() < 0.4:
            scene_desc = self.scene_gen.generate_scene_description()
            if scene_desc:
                injections.append(f'\n{scene_desc}\n')

        # 注入到文本中间偏后的位置
        if injections:
            lines = text.split('\n')
            insert_pos = len(lines) * 2 // 3
            for inj in injections:
                lines.insert(insert_pos, inj)
                insert_pos += len(inj.split('\n'))
            text = '\n'.join(lines)

        return text

        # ================================================================
        # 增强战斗注入
        # ================================================================
    def _inject_enhanced_battle(self, text, beat):
        """使用ASP引擎的战斗生成器注入更详细的战斗描写。"""
        hero = self.asp_character.generate(surname='墨')
        enemy = self.asp_character.generate()
        terrain = '苍云山后山' if beat == 'all_lost' else '闪排骨平川'

        battle_text = self.battle_gen.generate_battle(
            char_a=hero, char_b=enemy,
            rounds=self.rng.randint(2, 4), terrain=terrain
        )

        lines = text.split('\n')
        insert_pos = len(lines) * 3 // 4
        lines.insert(insert_pos, '\n【战斗场景】')
        lines.insert(insert_pos + 1, battle_text)
        return '\n'.join(lines)

        # ================================================================
        # 大纲预览
        # ================================================================
    def preview_outline(self, chapters=80):
        """预览因果链引擎的章节大纲。"""
        outline = self.causal_gen.generate_outline(chapters)
        lines = [f'第1卷大纲预览（{chapters}章）：', '=' * 50]
        for entry in outline:
            lines.append(
                f"  第{entry['chapter']:2d}章 "
                f"[{entry['beat']:10s}] "
                f"变体{entry['sub_index']}/{entry['total_in_beat']}"
            )
        return '\n'.join(lines)

        # ================================================================
        # 诊断报告
        # ================================================================
    def diagnostic_report(self):
        """输出当前引擎状态诊断报告。"""
        lines = [
            '=' * 50,
            '  双引擎统一编排器 v2.1 — 诊断报告',
            '  ★ 深度融合模式：IntegratedChapterGenerator',
            '=' * 50,
            f'  随机种子：{self._seed}',
            f'  输出目录：{self._output_dir}',
            f'  情节状态：第{self.plot_state.state.get("current_chapter", 0)}章',
            f'  已回收碎片：{self.plot_state.state.get("fragment_count", 0)}',
            f'  千层饼层数：{self.plot_state.state.get("truth_layer", 1)}/6（自动触发）',
            '',
            '  【融合架构 v2.1】',
            '  ├─ 大脑层：BeatOrchestrator — 节拍→操作序列',
            '  ├─ 声音层：VoiceEngine — 上下文感知词库渲染',
            '  └─ 总线：  NarrativeContext — 共享状态',
            '',
            '  【生成器对比】',
            '  ├─ integrated (★推荐)：每次运行文本不同，因果逻辑一致',
            '  ├─ causal (旧版)：每次输出完全相同的硬编码文本',
            '  └─ asp (旧版)：海量模板文本，无情节结构',
            '',
            '  已解锁世界：',
        ]
        for layer_key in ['layer_1', 'layer_2', 'layer_3']:
            worlds = self.plot_state.state['worlds_unlocked'][layer_key]
            for name, data in worlds.items():
                status = '✓已回收' if data['fragment_recovered'] else ('○已解锁' if data['unlocked'] else '✗未解锁')
                lines.append(f'    {layer_key} | {name}: {status}')
        lines.append('=' * 50)
        return '\n'.join(lines)
