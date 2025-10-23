# LyricBridge backend

This directory contains the FastAPI backend that powers the reimplementation of **163MusicLyrics**, branded as **LyricBridge**.

## Getting started

推荐使用 uv 的工作流（可重复安装、无需手动激活 venv）：

```bash
# 同步项目依赖（根据 pyproject.toml / uv.lock）
uv sync

# 运行开发服务（自动在项目环境中执行）
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 可选：安装开发依赖并同步
uv sync --extra dev
```

如需传统方式：

```bash
uv venv && source .venv/bin/activate
uv pip install -e .
uv run uvicorn app.main:app --reload
```

## Project structure

- `app/config.py` – base configuration, path handling, provider credentials.
- `app/main.py` – FastAPI application factory.
- `app/api` – routers that expose search/export/settings endpoints.
- `app/services` – core domain logic (music providers, translation, lyric formatting).
- `app/models` – Pydantic schemas mirroring the original VO objects.
- `app/utils` – shared helpers (caching, conversions, formatting).

Unit tests live under `backend/tests`.
