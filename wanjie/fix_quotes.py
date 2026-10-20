"""Fix Chinese quotes in Python source files that were written with ASCII " instead of \u201c/\u201d."""
import py_compile
import sys
import os

# 安全防护：仅允许修改项目目录内的 .py 文件
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_ALLOWED_EXTENSIONS = ('.py',)

TARGET = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    _PROJECT_ROOT, 'engine', 'causal_dialogue.py'
)

# 路径白名单校验
TARGET = os.path.abspath(TARGET)
if not TARGET.startswith(os.path.abspath(_PROJECT_ROOT)):
    sys.exit(f'[拒绝] 目标文件不在项目目录内: {TARGET}')
if not TARGET.endswith(_ALLOWED_EXTENSIONS):
    sys.exit(f'[拒绝] 仅允许修改 .py 文件: {TARGET}')

with open(TARGET, 'r', encoding='utf-8') as f:
    content = f.read()

def _is_cjk(c):
    o = ord(c)
    return (0x4E00 <= o <= 0x9FFF or 0x3000 <= o <= 0x303F or
            0xFF00 <= o <= 0xFFEF or 0x2000 <= o <= 0x206F)

def fix_line(line):
    result = []
    i = 0
    in_str = False
    str_char = None

    while i < len(line):
        ch = line[i]

        if not in_str:
            result.append(ch)
            if ch in '"\'':
                in_str = True
                str_char = ch
            i += 1
        else:
            if ch == str_char:
                # Check if this is string terminator
                next_pos = i + 1
                while next_pos < len(line) and line[next_pos] == ' ':
                    next_pos += 1
                if next_pos >= len(line) or line[next_pos] in ',)]}\n':
                    result.append(ch)
                    in_str = False
                    i += 1
                    continue

            if ch == '"' and str_char == '"':
                prev_cjk = i > 0 and _is_cjk(line[i-1])
                next_cjk = i + 1 < len(line) and _is_cjk(line[i+1])
                if prev_cjk or next_cjk:
                    result.append('\u201c')
                    i += 1
                    while i < len(line) and line[i] != '"':
                        result.append(line[i])
                        i += 1
                    if i < len(line):
                        result.append('\u201d')
                    i += 1
                    continue

            result.append(ch)
            i += 1

    return ''.join(result)

lines = content.split('\n')
fixed_lines = [fix_line(line) for line in lines]

with open(TARGET, 'w', encoding='utf-8') as f:
    f.write('\n'.join(fixed_lines))

try:
    py_compile.compile(TARGET, doraise=True)
    print(f'{TARGET}: Syntax OK!')
except py_compile.PyCompileError as e:
    print(f'Error: {e}')
