// CommonJS preload to avoid ESM pitfalls and ensure contextBridge availability
const { contextBridge, ipcRenderer } = require("electron");

let backendUrl =
  process.env.LYRICBRIDGE_BACKEND_URL ||
  process.env.NEO_MUSICLYRIC_BACKEND_URL ||
  "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const url = `${backendUrl}${path}`;
  let res;
  try {
    res = await fetch(url, {
      method: "GET",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch (e) {
    const reason = e && e.message ? e.message : String(e);
    throw new Error(`Failed to fetch ${url}. Is the backend running and reachable? ${reason}`);
  }
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  const text = await res.text();
  if (!text) return null;
  return JSON.parse(text);
}

contextBridge.exposeInMainWorld("api", {
  getVersion: () => ipcRenderer.invoke("app:get-version"),
  getBackendUrl: () => backendUrl,
  setBackendUrl: (url) => { backendUrl = url; },
  saveSrt: (defaultFileName, content) => ipcRenderer.invoke("app:save-lyrics", { defaultFileName, content }),
  health: () => request("/health/"),
  // Use trailing slash to avoid 307 redirects that break CORS preflight
  readSettings: () => request("/settings/"),
  updateSettings: (payload) => request("/settings/", { method: "PUT", body: payload }),
  preciseSearch: (payload) => request("/search/precise", { method: "POST", body: payload }),
  blurSearch: (payload) => request("/search/blur", { method: "POST", body: payload }),
  exportLyrics: (payload) => request("/export/lyrics", { method: "POST", body: payload }),
  getSongLinks: (payload) => request("/export/song-link", { method: "POST", body: payload }),
  getSongPics: (payload) => request("/export/song-pic", { method: "POST", body: payload }),
  downloadArtifact: async (artifactId) => {
    const res = await fetch(`${backendUrl}/export/download/${artifactId}`);
    if (!res.ok) throw new Error(`Failed to download artifact ${artifactId}`);
    const blob = await res.blob();
    return blob;
  },
});
