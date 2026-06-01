const { app, BrowserWindow, dialog } = require('electron');
const { spawn, execSync } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

let mainWindow = null;
let serverProcess = null;
const BACKEND_PORT = 6969;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

function getSourceDir() {
  if (app.isPackaged) {
    return process.resourcesPath;
  }
  return path.join(__dirname, '..');
}

function getAppDataDir() {
  return path.join(app.getPath('userData'), 'app');
}

function copyRecursive(src, dest) {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true });
  }
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name === 'node_modules' || entry.name === '.venv' || entry.name === '.git' || entry.name === '__pycache__') continue;
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyRecursive(s, d);
    } else if (!fs.existsSync(d)) {
      fs.copyFileSync(s, d);
    }
  }
}

function ensureBackendInstalled(sourceDir, appDataDir) {
  if (!fs.existsSync(appDataDir)) {
    copyRecursive(sourceDir, appDataDir);
  }
  const marker = path.join(appDataDir, '.installed');
  if (fs.existsSync(marker)) return;

  const pip = spawn('python3', ['-m', 'pip', 'install', '-e', '.', '--quiet', '--prefix', appDataDir], {
    cwd: appDataDir,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  return new Promise((resolve, reject) => {
    let stderr = '';
    pip.stderr.on('data', (d) => { stderr += d.toString(); });
    pip.on('close', (code) => {
      if (code === 0) {
        fs.writeFileSync(marker, '');
        resolve();
      } else {
        reject(new Error(`pip install failed (${code}): ${stderr.slice(-500)}`));
      }
    });
    pip.on('error', reject);
  });
}

function getPythonPath(appDataDir) {
  const sitePackages = path.join(appDataDir, 'lib', `python${process.env.PYTHON_VERSION || '3.12'}`, 'site-packages');
  return `${appDataDir}/lib/python3.12/site-packages`;
}

function waitForServer(url, timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    function poll() {
      const req = http.get(url, (res) => { res.resume(); resolve(); });
      req.on('error', () => {
        if (Date.now() - start > timeoutMs) {
          reject(new Error(`Server did not start within ${timeoutMs / 1000}s`));
        } else {
          setTimeout(poll, 500);
        }
      });
      req.end();
    }
    poll();
  });
}

async function startServer() {
  const sourceDir = getSourceDir();
  const appDataDir = getAppDataDir();
  const taosDataDir = path.join(app.getPath('userData'), 'data');

  fs.mkdirSync(taosDataDir, { recursive: true });

  if (app.isPackaged) {
    try {
      await ensureBackendInstalled(sourceDir, appDataDir);
    } catch (err) {
      dialog.showErrorBox('Setup Error', `Failed to install backend:\n${err.message}`);
      throw err;
    }
  }

  const pythonEnv = {
    ...process.env,
    TAOS_HOST: '127.0.0.1',
    TAOS_PORT: String(BACKEND_PORT),
    TAOS_DATA_DIR: taosDataDir,
    PYTHONPATH: app.isPackaged ? getPythonPath(appDataDir) : (process.env.PYTHONPATH || ''),
  };

  serverProcess = spawn('python3', [
    '-m', 'uvicorn', 'tinyagentos.app:create_app', '--factory',
    '--host', '127.0.0.1',
    '--port', String(BACKEND_PORT),
    '--log-level', 'info',
  ], {
    cwd: app.isPackaged ? appDataDir : sourceDir,
    env: pythonEnv,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  serverProcess.stdout.on('data', (d) => console.log(`[backend] ${d.toString().trim()}`));
  serverProcess.stderr.on('data', (d) => console.error(`[backend] ${d.toString().trim()}`));
  serverProcess.on('exit', (code) => { serverProcess = null; });

  await waitForServer(`${BACKEND_URL}/api/health`);
}

function stopServer() {
  if (serverProcess) {
    serverProcess.kill('SIGTERM');
    setTimeout(() => {
      if (serverProcess) serverProcess.kill('SIGKILL');
    }, 5000);
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    title: 'TinyAgentOS',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  mainWindow.loadURL(BACKEND_URL);
  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(async () => {
  try {
    await startServer();
    createWindow();
  } catch (err) {
    console.error('Startup failed:', err);
    if (!app.isPackaged) process.exit(1);
  }
});

app.on('window-all-closed', () => { stopServer(); app.quit(); });
app.on('before-quit', () => { stopServer(); });
app.on('activate', () => { if (mainWindow === null && serverProcess) createWindow(); });
