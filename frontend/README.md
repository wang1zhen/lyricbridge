# LyricBridge frontend

Electron-based desktop shell for the LyricBridge project. The renderer currently uses plain HTML/CSS/JS and communicates with the FastAPI backend through the preload bridge.

## Development

```bash
cd lyricbridge/frontend
# 首次或 CI 环境建议使用 npm ci 以保证与 lockfile 一致
npm ci || npm install

# 一键启动：自动选择空闲端口唤起后端，并把地址注入到 Electron
npm start

# 如已手动启动后端，设置环境变量可跳过自动唤起：
# Linux/macOS
#   export LYRICBRIDGE_BACKEND_URL=http://127.0.0.1:8000 && npm start
# Windows PowerShell
#   $env:LYRICBRIDGE_BACKEND_URL="http://127.0.0.1:8000"; npm start
```

### Available scripts

- `npm start` – launch Electron pointing at the local renderer bundle.
- `npm run lint` – placeholder for future linting configuration.

## Structure

```
frontend/
├── electron/  # main process + preload bridge
├── renderer/  # lightweight UI (can be replaced with React/Vue later)
└── package.json
```

The preload layer exposes APIs such as `preciseSearch` and `readSettings` that proxy to the backend service. Update `LYRICBRIDGE_BACKEND_URL` (fallback to `NEO_MUSICLYRIC_BACKEND_URL` for compatibility) or use the in-app settings to connect to a different backend instance. When running `npm start`, the dev script auto-starts the backend on a free port unless `LYRICBRIDGE_BACKEND_URL` is provided.
