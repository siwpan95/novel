"""模板挖掘流水线产物（templates/ 词库）+ ASP 接入测试。

验证：
1. templates/ 词库存在且模板带 {slot} 槽位（模板骨架，非成品句）。
2. BattleGenerator 从词库加载额外模板 + 槽位值池（接入生效，池变长）。
3. 槽位值可从 battle_slots 词库读取（拆硬编码 → 词库）。
"""
from novel_generator.engine.word_bank import WordBank
from novel_generator.engine.generators.battle import BattleGenerator


def test_template_banks_exist_and_slotted():
    wb = WordBank(seed=1)
    for name in ("battle_action", "battle_reaction", "battle_effect",
                 "battle_opening", "battle_ending", "scene_frame",
                 "character_intro", "emotion_beat"):
        data = wb.load(name)
        templates = data.get("templates", [])
        assert templates, f'{name} 词库为空'
        # 至少一半模板带槽位（模板骨架特征）
        slotted = sum(1 for t in templates if '{' in t)
        assert slotted >= len(templates) // 2, f'{name} 槽位模板过少: {slotted}/{len(templates)}'


def test_battle_slots_bank_loads():
    wb = WordBank(seed=1)
    data = wb.load("battle_slots")
    # 关键槽位键齐全（原 battle.py 硬编码列表已迁入词库）
    for key in ("color", "action", "verb", "expression", "thing", "lunge", "shake"):
        assert data.get(key), f'battle_slots 缺键 {key}'


def test_battle_generator_loads_bank_templates_and_slots():
    wb = WordBank(seed=42)
    bg = BattleGenerator(wb)
    # 接入生效：模板池应大于硬编码基线（17 / 11 / 10），说明词库模板被追加
    assert len(bg.ACTION_PATTERNS) > 17, f'action 模板未从词库追加: {len(bg.ACTION_PATTERNS)}'
    assert len(bg.REACTION_PATTERNS) > 11
    assert len(bg.EFFECT_PATTERNS) > 10
    # 槽位值池来自词库
    assert bg._slot_pools.get("color")
    # 生成一轮打斗不报错、非空
    text = bg.generate_round("林朔", "张铁柱", "铁剑", "裂空斩", "无", "铁布衫", "护心镜", "断魂崖")
    assert text and len(text) > 20


def test_dialogue_generator_loads_bank_templates_and_slots():
    from novel_generator.engine.generators.dialogue import DialogueGenerator
    wb = WordBank(seed=7)
    dg = DialogueGenerator(wb)
    # 词库追加：应大于硬编码基线 7
    assert len(dg.EXCHANGE_PATTERNS) > 7
    assert dg._slot_pools.get("expression")
    text = dg.generate_exchange("林朔", "张铁柱", "裂空斩", "铁布衫", "铁剑", "长枪", "护心镜", "玉佩", "断魂崖")
    assert text and "道：" in text


def test_scene_generator_loads_directions():
    from novel_generator.engine.generators.battle import SceneGenerator
    wb = WordBank(seed=7)
    sg = SceneGenerator(wb)
    assert sg._directions and "南方" in sg._directions
    assert "就在前面" in sg.generate_scene()


def test_character_generator_loads_intro_templates_and_slots():
    from novel_generator.engine.generators.character import CharacterGenerator
    wb = WordBank(seed=7)
    cg = CharacterGenerator(wb)
    assert cg._intro_templates
    assert cg._char_slots.get("aura")
    text = cg.render_entrance({"name": "林朔"})
    assert text and "林朔" in text
