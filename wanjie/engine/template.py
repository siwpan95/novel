"""模板引擎：将带占位符的模板填充随机词库内容。

这是"ASP多层嵌套循环替换关键字"写法的核心实现。

通用内核来自已发布到 PyPI 的 ``novel-generator``（导入名 ``novel_generator``）：

    from novel_generator.engine.template import TemplateEngine   # 内核
    class TemplateEngine(_KernelTemplateEngine): ...             # 本文件

**继承来的通用能力**（内核实现）：修饰符系统（``:w`` / ``:c=`` / ``:u`` /
``:f=`` / ``:e=`` / ``:n=``）、状态变量（``set_var`` / ``get_var`` /
``clear_vars``）、条件分支、上下文缓存，以及 ``resolve`` /
``resolve_with_context`` / ``batch_resolve`` / ``template``。

**本文件保留《万界归墟》自身的模板方言**（内核 ``fill`` 不支持，故覆写）：

模板语法：
- {{bank.key}}          → 从词库随机取一项（每次调用可能不同）
- {{bank.key[N]}}       → 从词库取第N项（确定性）
- {{bank.key:unique}}   → 本次模板展开中不重复
- {{bank.key,3}}        → 取3项，用顿号连接
- {{name}}              → 特殊占位符，由上下文变量替换
- {{name|surname}}      → 半随机名字（指定姓氏）
"""

import re
from typing import Optional

from novel_generator.engine.template import TemplateEngine as _KernelTemplateEngine
from .word_bank import WordBank


class TemplateEngine(_KernelTemplateEngine):
    """《万界归墟》模板填充引擎：内核 TemplateEngine + 本仓模板方言。"""

    def __init__(self, word_bank: WordBank):
        super().__init__(word_bank)
        self._wb = word_bank
        self._used: dict[str, set] = {}  # 跟踪已使用项（用于unique模式）

    def reset_used(self):
        """重置唯一性追踪。"""
        self._used.clear()

    def fill(self, template: str, variables: Optional[dict[str, str]] = None) -> str:
        """将模板中的所有占位符替换为随机内容。

        Args:
            template: 模板字符串，含 {{...}} 占位符
            variables: 上下文变量字典（如 {"主角名": "林朔", "对手名": "张铁柱"}）
        """
        if variables is None:
            variables = {}

        def replacer(match: re.Match) -> str:
            placeholder = match.group(1).strip()

            # 1. 上下文变量替换
            if placeholder in variables:
                return variables[placeholder]

            # 2. 解析 bank.key 或 bank.key[N] 或 bank.key:unique 或 bank.key,N
            parts = placeholder.split(".", 1)
            if len(parts) == 2:
                return self._resolve_bank_ref(parts[0], parts[1])

            # 3. 直接是上下文变量名
            if placeholder in variables:
                return variables[placeholder]

            # 4. 无法解析的占位符保留原样
            return match.group(0)

        result = re.sub(r"\{\{(.+?)\}\}", replacer, template)
        return result

    def _resolve_bank_ref(self, bank_name: str, ref: str) -> str:
        """解析 bank.key 引用。"""
        key = ref
        unique = False
        count = 1

        # 检查 :unique 修饰
        if ":unique" in key:
            unique = True
            key = key.replace(":unique", "")

        # 检查 ,N 修饰
        if "," in key:
            key, count_str = key.rsplit(",", 1)
            try:
                count = int(count_str.strip())
            except ValueError:
                count = 1

        # 检查 [N] 索引
        idx_match = re.match(r"(.+)\[(\d+)\]", key)
        if idx_match:
            key = idx_match.group(1)
            idx = int(idx_match.group(2))
            # 返回指定索引项（用于固定搭配）
            data = self._wb.load(bank_name)
            pool = data.get(key, [])
            if 0 <= idx < len(pool):
                return pool[idx]
            return f"[{bank_name}.{key}[{idx}]不存在]"

        # 随机选取
        if unique:
            used_key = f"{bank_name}.{key}"
            if used_key not in self._used:
                self._used[used_key] = set()
            # 尝试选取未使用的
            data = self._wb.load(bank_name)
            pool = data.get(key, [])
            available = [item for item in pool if item not in self._used[used_key]]
            if not available:
                self._used[used_key].clear()
                available = pool
            result = self._wb.get_rng().choice(available)
            self._used[used_key].add(result)
            return result

        # 普通随机选取
        if count > 1:
            items = self._wb.pick_n(bank_name, key, count, unique=True)
            return "、".join(items)

        return self._wb.pick(bank_name, key)

    def fill_loop(self, template: str, variables: dict[str, str], iterations: int) -> list[str]:
        """对同一模板进行多次填充（用于循环生成多个对手/场景）。

        每次迭代重置unique追踪，但保留上下文变量。
        """
        results = []
        for i in range(iterations):
            self.reset_used()
            # 在变量中加入循环索引
            loop_vars = {**variables, "循环索引": str(i + 1)}
            results.append(self.fill(template, loop_vars))
        return results
