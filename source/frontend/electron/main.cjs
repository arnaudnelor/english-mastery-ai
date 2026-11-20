// Electron shell: starts the local Python learning engine, waits for it,
// then opens the UI. The backend serves the built UI on 127.0.0.1 only.
const { app, BrowserWindow, session, shell, dialog } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");

const PORT = 8765;
const DEV = process.env.EMA_DEV === "1";
let backend = null;

function startBackend() {
  if (DEV) {
    // Dev: run from source. Requires `pip install -r backend/requirements.txt`.
    const cwd = path.join(__dirname, "..", "..", "backend");
    backend = spawn(process.platform === "win32" ? "python" : "python3", ["-m", "app.main"], { cwd, stdio: "inherit" });
  } else {
    // Production: PyInstaller-built executable shipped in resources/backend
    const exe = path.join(process.resourcesPath, "backend", process.platform === "win32" ? "ema-backend.exe" : "ema-backend");
    backend = spawn(exe, [], {
      env: { ...process.env, EMA_STATIC_DIR: path.join(process.resourcesPath, "web") },
      windowsHide: true,
    });
  }
  backend.on("exit", (code) => {
    if (code && !app.isQuitting) dialog.showErrorBox("English Mastery AI", `The learning engine stopped unexpectedly (code ${code}). See %APPDATA%\\EnglishMasteryAI\\app.log`);
  });
}

function waitForBackend(timeoutMs = 30000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      http.get(`http://127.0.0.1:${PORT}/api/system/health`, (res) => (res.statusCode === 200 ? resolve() : retry())).on("error", retry);
    };
    const retry = () => (Date.now() - start > timeoutMs ? reject(new Error("Backend did not start")) : setTimeout(tick, 300));
    tick();
  });
}

async function createWindow() {
  // Allow microphone only for our own local origin.
  session.defaultSession.setPermissionRequestHandler((wc, permission, cb) => {
    const url = wc.getURL();
    const local = url.startsWith(`http://127.0.0.1:${PORT}`) || url.startsWith("http://localhost:5173");
    cb(local && (permission === "media" || permission === "audioCapture"));
  });

  const win = new BrowserWindow({
    width: 1440, height: 920, minWidth: 1100, minHeight: 700,
    backgroundColor: "#0d1018", title: "English Mastery AI", show: false,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: "deny" }; });
  win.once("ready-to-show", () => win.show());

  try {
    await waitForBackend();
  } catch (e) {
    dialog.showErrorBox("English Mastery AI", "Could not start the learning engine. " + e.message);
    app.quit();
    return;
  }
  await win.loadURL(DEV ? "http://localhost:5173" : `http://127.0.0.1:${PORT}/`);
}

const single = app.requestSingleInstanceLock();
if (!single) app.quit();

app.whenReady().then(() => { startBackend(); createWindow(); });
app.on("before-quit", () => { app.isQuitting = true; if (backend) backend.kill(); });
app.on("window-all-closed", () => app.quit());
