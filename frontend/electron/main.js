import { app, BrowserWindow, ipcMain, shell, dialog } from "electron";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { promises as fs } from "node:fs";

// __dirname is not available in ESM; reconstruct it from import.meta.url
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

let mainWindow;

// Set application name for OS integration
try { app.setName("LyricBridge"); } catch {}

const createWindow = () => {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 920,
    minWidth: 960,
    minHeight: 720,
    webPreferences: {
      preload: join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    },
    autoHideMenuBar: true,
    title: "LyricBridge"
  });

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
    const { filePath, canceled } = await dialog.showSaveDialog(mainWindow, {
      title: "保存歌词",
      defaultPath: join(process.cwd(), defaultFileName),
      filters: [{ name: "SubRip Subtitle", extensions: ["srt"] }],
    });
    if (canceled || !filePath) return { canceled: true };
    await fs.writeFile(filePath, content, "utf-8");
    return { canceled: false, filePath };
  } catch (e) {
    return { canceled: true, error: e && e.message ? e.message : String(e) };
  }
});
