# -*- coding: utf-8 -*-
"""万界归墟 GUI 配置。"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 服务器
HOST = "127.0.0.1"
HTTP_PORT = 5000

# 生成器默认值
DEFAULT_TARGET_CHARS = 2000
DEFAULT_SEED = 42

# 输出目录
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# 日志
LOG_FILE = os.path.join(BASE_DIR, "gui_server.log")
