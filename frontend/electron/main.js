import { app, BrowserWindow, ipcMain, shell, dialog, nativeImage } from "electron";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { promises as fs, existsSync, writeFileSync } from "node:fs";

// __dirname is not available in ESM; reconstruct it from import.meta.url
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

let mainWindow;

const getStatePath = () => {
  try {
    return join(app.getPath("userData"), "lyricbridge-state.json");
  } catch {
    // Fallback if userData is not available for some reason
    return join(app.getPath("home"), ".lyricbridge-state.json");
  }
};

const loadState = async () => {
  try {
    const content = await fs.readFile(getStatePath(), "utf-8");
    return JSON.parse(content);
  } catch {
    return {};
  }
};

const updateState = async (patch) => {
  try {
    const current = await loadState();
    const next = { ...current, ...patch };
    await fs.writeFile(getStatePath(), JSON.stringify(next), "utf-8");
  } catch {
    // Best-effort only; ignore persistence errors
  }
};

// Set application name for OS integration
try { app.setName("LyricBridge"); } catch {}

const createWindow = () => {
  const iconPath = (() => {
    const candidates = [
      join(__dirname, "..", "renderer", "favicon.png"),
      join(__dirname, "..", "renderer", "favicon.ico"),
      join(__dirname, "..", "renderer", "favicon.svg"),
    ];
    for (const p of candidates) {
      try { if (existsSync(p)) return p; } catch {}
    }
    return undefined;
  })();

  const winOpts = {
    width: 1280,
    height: 920,
    minWidth: 960,
    minHeight: 720,
    webPreferences: {
      preload: join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    autoHideMenuBar: true,
    title: "LyricBridge",
  };
  if (iconPath) {
    // On Linux/Windows, Electron uses this as the window/taskbar icon.
    // Prefer nativeImage for SVG to improve compatibility across WMs.
    try {
      if (iconPath.endsWith('.svg')) {
        const img = nativeImage.createFromPath(iconPath);
        if (!img.isEmpty()) {
          // Create a PNG on disk to help WMs that ignore in-memory icons.
          try {
            const pngBuf = img.resize({ width: 256, height: 256 }).toPNG();
            const tmpPng = join(app.getPath('temp'), 'lyricbridge-icon.png');
            writeFileSync(tmpPng, pngBuf);
            winOpts.icon = tmpPng;
          } catch {
            winOpts.icon = img;
          }
        } else {
          winOpts.icon = iconPath;
        }
      } else {
        winOpts.icon = iconPath;
      }
    } catch {
      winOpts.icon = iconPath;
    }
  }

  mainWindow = new BrowserWindow(winOpts);

  mainWindow.loadFile(join(__dirname, "..", "renderer", "index.html"));

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
};

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

ipcMain.handle("app:get-version", () => app.getVersion());
ipcMain.handle("app:save-lyrics", async (_evt, payload) => {
  try {
    const defaultFileName = (payload && payload.defaultFileName) || "lyrics.srt";
    const content = (payload && payload.content) || "";
    const state = await loadState();
    const lastSaveDir = state && typeof state.lastSaveDir === "string" ? state.lastSaveDir : null;
    const baseDir =
      typeof lastSaveDir === "string" && lastSaveDir && existsSync(lastSaveDir)
        ? lastSaveDir
        : app.getPath("home");
    const { filePath, canceled } = await dialog.showSaveDialog(mainWindow, {
      title: "保存歌词",
      defaultPath: join(baseDir, defaultFileName),
      filters: [{ name: "SubRip Subtitle", extensions: ["srt"] }],
    });
    if (canceled || !filePath) return { canceled: true };
    await fs.writeFile(filePath, content, "utf-8");
    try {
      const dir = dirname(filePath);
      if (dir) await updateState({ lastSaveDir: dir });
    } catch {}
    return { canceled: false, filePath };
  } catch (e) {
    return { canceled: true, error: e && e.message ? e.message : String(e) };
  }
});
