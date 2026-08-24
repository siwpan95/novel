FROM python:3.11-slim

WORKDIR /app

# 纯标准库项目，无需 pip install（可选安装 dev 依赖则取消注释）
# COPY pyproject.toml .
# RUN pip install -e ".[dev]"

COPY . .

# 默认运行深度融合模式（可通过 docker run 覆盖 CMD）
CMD ["python", "-m", "novel_generator", "--mode", "integrated", "--chapters", "80"]
