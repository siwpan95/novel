"""《宇宙巨校闪级生》风格小说生成器。

基于 ASP 多层嵌套循环 + 词库随机替换的注水风格写作程序。

用法：
    # 快速生成（3部，每部7章，每章4对手）
    python -m novel_generator.main

    # 自定义生成
    python -m novel_generator.main --volumes 5 --chapters 7 --opponents 4 --seed 42

    # 查看帮助
    python -m novel_generator.main --help
"""

__version__ = "2.1.0"
