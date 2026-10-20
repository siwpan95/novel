"""《万界归墟》小说生成器。

双引擎（因果结构 + ASP词库渲染）程序化中文长篇小说生成系统。
通用内核（WordBank / TemplateEngine 基类）来自 `novel-generator`。

用法：
    # 快速生成（3部，每部7章，每章4对手）
    python -m wanjie.main

    # 自定义生成
    python -m wanjie.main --volumes 5 --chapters 7 --opponents 4 --seed 42

    # 查看帮助
    python -m wanjie.main --help
"""

__version__ = "3.0.0"
