#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import { createServer } from "node:net";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const FRONTEND_DIR = resolve(__dirname, "..");
const BACKEND_DIR = resolve(__dirname, "../../backend");

function getFreePort(host = "127.0.0.1") {
  return new Promise((resolvePort, reject) => {
    const server = createServer();
    server.on("error", reject);
    server.listen(0, host, () => {
      const address = server.address();
      const port = address && typeof address === "object" ? address.port : null;
      server.close(() => (port ? resolvePort(port) : reject(new Error("No port"))));
    });
  });
}

async function waitForHealth(url, { retries = 30, delayMs = 200 } = {}) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (res.ok) return true;
    } catch {}
    await new Promise((r) => setTimeout(r, delayMs));
  }
  return false;
}

function spawnProc(cmd, args, opts = {}) {
  const child = spawn(cmd, args, { stdio: "inherit", ...opts });
  child.on("error", (e) => {
    console.error(`[dev] Failed to spawn ${cmd}:`, e.message || e);
  });
  return child;
}

async function ensureBackendAndLaunchElectron() {
  // If user already provides backend URL, skip spawning backend
  const presetUrl = process.env.LYRICBRIDGE_BACKEND_URL;
  let backendUrl = presetUrl;
  let backendChild = null;

  if (!presetUrl) {
    const port = await getFreePort();
    backendUrl = `http://127.0.0.1:${port}`;

    // Try uv first; fallback to python -m uvicorn if uv not found
    const commonEnv = { ...process.env };
    const uvArgs = [
      "run",
      "python",
      "-m",
      "uvicorn",
      "app.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
      "--reload",
    ];

    let usePythonDirect = false;
    const probe = spawnSync("uv", ["--version"], { stdio: "ignore" });
    if (probe.error || probe.status !== 0) {
      usePythonDirect = true;
    }

    backendChild = usePythonDirect
      ? spawnProc("python", ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port), "--reload"], {
          cwd: BACKEND_DIR,
          env: commonEnv,
        })
      : spawnProc("uv", uvArgs, { cwd: BACKEND_DIR, env: commonEnv });

    const healthy = await waitForHealth(`${backendUrl}/health/`, { retries: 60, delayMs: 250 });
    if (!healthy) {
      console.error(`[dev] Backend did not become healthy at ${backendUrl}. Check logs above.`);
      if (backendChild) backendChild.kill("SIGKILL");
      process.exit(1);
    }
  }

  const electronEnv = { ...process.env, LYRICBRIDGE_BACKEND_URL: backendUrl };
  const electronBin = process.platform === "win32" ? "electron.cmd" : "electron";
  const electronChild = spawnProc(electronBin, ["."], {
    cwd: FRONTEND_DIR,
    env: electronEnv,
  });

  const cleanup = () => {
    if (electronChild && !electronChild.killed) electronChild.kill("SIGTERM");
    if (backendChild && !backendChild.killed) backendChild.kill("SIGTERM");
  };

  process.on("SIGINT", () => {
    cleanup();
    process.exit(130);
  });
  process.on("SIGTERM", () => {
    cleanup();
    process.exit(143);
  });

  electronChild.on("close", (code, signal) => {
    cleanup();
    process.exit(code ?? (signal ? 1 : 0));
  });
}

ensureBackendAndLaunchElectron().catch((e) => {
  console.error("[dev] Unexpected failure:", e);
  process.exit(1);
});
