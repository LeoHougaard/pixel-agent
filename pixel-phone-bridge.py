#!/usr/bin/env python3
"""Pixel Phone bridge: localhost HTTP API so OpenCode (inside Debian/T3)
can do real phone actions from the T3 mobile UI.

Runs in Termux (where rish/adb/termux-api live). Debian guest reaches it
at http://127.0.0.1:18080 because PRoot shares the network namespace.

Endpoints (all localhost only, Bearer token required except /health):
  GET  /health              -> {"ok": true, "backend": "rish|adb|unavailable"}
  POST /run                 {"command": str, "privileged": bool, "timeout": int}
  GET  /screenshot          -> raw image/png
  GET  /apps                -> {"apps": "..."}
  POST /open_app            {"app": str}
  POST /tap                 {"x": int, "y": int, "normalized": bool}
  POST /swipe               {"sx":..,"sy":..,"ex":..,"ey":..,"duration_ms":..,"normalized": bool}
  POST /key                 {"key": str}
  POST /type                {"text": str, "press_enter": bool}

Token file: ~/.config/pixel-agent/bridge-token (mode 600).
Port file:  ~/.local/state/pixel-phone/bridge-port
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import shutil
import struct
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = int(os.environ.get("PIXEL_PHONE_PORT", "18080"))
CONFIG_DIR = Path.home() / ".config" / "pixel-agent"
TOKEN_FILE = CONFIG_DIR / "bridge-token"
STATE_DIR = Path.home() / ".local" / "state" / "pixel-phone"
MAX_BODY = 256 * 1024

COMMON_APPS = {
    "calculator": "com.google.android.calculator",
    "calendar": "com.google.android.calendar",
    "camera": "com.google.android.GoogleCamera",
    "chrome": "com.android.chrome",
    "files": "com.google.android.apps.nbu.files",
    "gmail": "com.google.android.gm",
    "google": "com.google.android.googlequicksearchbox",
    "maps": "com.google.android.apps.maps",
    "messages": "com.google.android.apps.messaging",
    "phone": "com.google.android.dialer",
    "photos": "com.google.android.apps.photos",
    "play store": "com.android.vending",
    "settings": "com.android.settings",
    "youtube": "com.google.android.youtube",
}

KEYCODES = {
    "BACK": "KEYCODE_BACK", "DEL": "KEYCODE_DEL", "DELETE": "KEYCODE_DEL",
    "DOWN": "KEYCODE_DPAD_DOWN", "END": "KEYCODE_MOVE_END",
    "ENTER": "KEYCODE_ENTER", "ESC": "KEYCODE_ESCAPE", "ESCAPE": "KEYCODE_ESCAPE",
    "HOME": "KEYCODE_HOME", "LEFT": "KEYCODE_DPAD_LEFT", "MENU": "KEYCODE_MENU",
    "PAGEDOWN": "KEYCODE_PAGE_DOWN", "PAGEUP": "KEYCODE_PAGE_UP",
    "RECENTS": "KEYCODE_APP_SWITCH", "RIGHT": "KEYCODE_DPAD_RIGHT",
    "SPACE": "KEYCODE_SPACE", "TAB": "KEYCODE_TAB", "UP": "KEYCODE_DPAD_UP",
    "VOLUME_DOWN": "KEYCODE_VOLUME_DOWN", "VOLUME_UP": "KEYCODE_VOLUME_UP",
}


def ensure_token() -> str:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if len(token) >= 32:
            return token
    token = secrets.token_hex(32)
    TOKEN_FILE.write_text(token + "\n", encoding="utf-8")
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass
    return token


def child_env() -> dict[str, str]:
    blocked = re.compile(r"(API.?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTH)", re.I)
    env = {k: v for k, v in os.environ.items() if not blocked.search(k)}
    # Never leak the bridge token to model-run commands.
    env.pop("PIXEL_PHONE_TOKEN", None)
    env.setdefault("RISH_APPLICATION_ID", "com.termux")
    return env


def clip(text: str, limit: int = 16_000) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n... <{len(text) - half * 2} chars omitted> ...\n{text[-half:]}"


class Bridge:
    def __init__(self) -> None:
        cands = [
            os.environ.get("PIXEL_AGENT_RISH"),
            str(Path.home() / ".local" / "bin" / "rish"),
            str(Path.home() / "rish"),
            shutil.which("rish"),
        ]
        self.rish = next((str(Path(p)) for p in cands if p and Path(p).is_file()), None)
        self.adb = shutil.which("adb")
        self._detect_lock = threading.Lock()
        self.backend = self._detect()
        self._checked_at = time.monotonic()
        self.desktop_process = None
        self.desktop_apps = []
        self._desktop_lock = threading.Lock()

    def refresh(self) -> str:
        # Shizuku can stop/restart after this HTTP process starts. Refresh before
        # commands, but never repeat a tap or command after an ambiguous failure.
        with self._detect_lock:
            if time.monotonic() - self._checked_at >= 5:
                self.backend = self._detect()
                self._checked_at = time.monotonic()
        return self.backend

    def _detect(self) -> str:
        if self.rish:
            try:
                r = subprocess.run([self.rish, "-c", "id"], capture_output=True,
                                   text=True, timeout=8, env=child_env())
                if r.returncode == 0:
                    return "rish"
            except (OSError, subprocess.SubprocessError):
                pass
        if self.adb:
            try:
                r = subprocess.run([self.adb, "devices"], capture_output=True,
                                   text=True, timeout=5, env=child_env())
                if [l for l in r.stdout.splitlines()[1:] if l.strip().endswith("\tdevice")]:
                    return "adb"
            except (OSError, subprocess.SubprocessError):
                pass
        return "unavailable"

    def run(self, command: str, privileged: bool = False, timeout: int = 60) -> dict:
        timeout = max(1, min(int(timeout), 300))
        if privileged:
            self.refresh()
            if self.backend == "rish" and self.rish:
                argv = [self.rish, "-c", command]
            elif self.backend == "adb" and self.adb:
                argv = [self.adb, "shell", command]
            else:
                return {"exit_code": 127, "stdout": "", "stderr": "No Android bridge. Start Shizuku/rish or connect adb.", "backend": "unavailable"}
            backend = self.backend
        else:
            argv = ["sh", "-c", command]
            backend = "termux"
        try:
            c = subprocess.run(argv, capture_output=True, text=True,
                               timeout=timeout, env=child_env(), errors="replace")
            return {"exit_code": c.returncode, "stdout": clip(c.stdout),
                    "stderr": clip(c.stderr), "backend": backend}
        except subprocess.TimeoutExpired:
            return {"exit_code": 124, "stdout": "", "stderr": f"Timed out after {timeout}s", "backend": backend}

    def screenshot(self) -> bytes:
        self.refresh()
        if self.backend == "rish" and self.rish:
            path = Path(f"/sdcard/Download/.pixel-agent-screen-{os.getpid()}.png")
            try:
                c = subprocess.run([self.rish, "-c", f"screencap -p {path}"],
                                   capture_output=True, timeout=20, env=child_env())
                if c.returncode != 0:
                    raise RuntimeError(c.stderr.decode("utf-8", "replace").strip())
                data = path.read_bytes()
                png_dimensions(data)
                return data
            finally:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
        if self.backend == "adb" and self.adb:
            c = subprocess.run([self.adb, "exec-out", "screencap", "-p"],
                               capture_output=True, timeout=20, env=child_env())
            if c.returncode != 0:
                raise RuntimeError(c.stderr.decode("utf-8", "replace").strip())
            data = c.stdout.replace(b"\r\r\n", b"\r\n")
            png_dimensions(data)
            return data
        raise RuntimeError("No Android bridge for screenshots.")

    def screen_size(self) -> tuple[int, int]:
        w, h = png_dimensions(self.screenshot())
        return w, h

    def inspect_ui(self):
        path = Path(f'/sdcard/Download/.pixel-agent-ui-{secrets.token_hex(6)}.xml')
        try:
            result = self.run(f'uiautomator dump --compressed {path}', privileged=True, timeout=25)
            if result['exit_code'] != 0:
                raise RuntimeError(result['stderr'] or result['stdout'])
            width, height = self.screen_size()
            return ui_elements(path.read_text(), width, height)
        finally:
            path.unlink(missing_ok=True)

    def desktop(self, action, body=None):
        import fcntl
        if action in ('show', 'hide'):
            if action == 'show':
                component = 'com.termux.x11/com.termux.x11.MainActivity'
            else:
                app_id = (CONFIG_DIR / 'app-id').read_text().strip()
                if not re.fullmatch(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+', app_id):
                    raise ValueError('Invalid Pixel Agent app ID')
                component = app_id + '/.MainActivity'
            result = self.run('am start -n ' + component, privileged=self.refresh() in ('rish', 'adb'))
            if result['exit_code']:
                raise RuntimeError(result['stderr'] or 'Android could not open the app')
            if action == 'show':
                self.run("termux-x11-preference 'fullscreen:false' </dev/null", privileged=False)
            (Path.home() / '.local/state/pixel-t3/use').touch()
            return {'ok': True}
        folder = Path.home()/'.local/state/pixel-desktop'
        folder.mkdir(parents=True, exist_ok=True)
        with self._desktop_lock:
            with (folder/'session.lock').open('a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    running = False
                except BlockingIOError:
                    running = True
                if action == 'status':
                    return {'running': running, 'managed': self.desktop_process is not None and self.desktop_process.poll() is None}
                if action == 'launch':
                    if not running: raise RuntimeError('Start the desktop first.')
                    command = str((body or {}).get('command', '')).strip()
                    if not command: raise ValueError('command is required')
                    cwd = str((body or {}).get('cwd', '/home/pixel'))
                    shell = 'cd -- '+shlex.quote(cwd)+' && exec /bin/bash -lc '+shlex.quote(command)
                    with (folder/'apps.log').open('ab') as log:
                        app = subprocess.Popen(['proot-distro','login','debian','--user','pixel','--shared-tmp','--',
                            'env','DISPLAY=:1','LIBGL_ALWAYS_SOFTWARE=1','NO_AT_BRIDGE=1','/bin/bash','-c',shell],
                            stdin=subprocess.DEVNULL,stdout=log,stderr=log,env=child_env(),start_new_session=True)
                    self.desktop_apps = [p for p in self.desktop_apps if p.poll() is None]+[app]
                    return {'pid':app.pid,'hint':'Check desktop status and a screenshot to verify the window opened.'}
                if action == 'start' and not running:
                    check = subprocess.run(['proot-distro', 'login', 'debian', '--user', 'pixel', '--',
                        'sh', '-c', 'command -v xfce4-session >/dev/null'],
                        capture_output=True, timeout=30, env=child_env())
                    if check.returncode or not shutil.which('termux-x11'):
                        raise RuntimeError('Linux desktop is not installed. Run bash install-linux-desktop.sh in the Termux source checkout.')
                    (Path(os.environ.get('TMPDIR', '/data/data/com.termux/files/usr/tmp')) / 'pixel-desktop-activity.json').unlink(missing_ok=True)
                    fcntl.flock(lock, fcntl.LOCK_UN)
                    env = child_env(); env['PIXEL_DESKTOP_MANAGED'] = '1'
                    with (folder/'session.log').open('a') as log:
                        self.desktop_process = subprocess.Popen(['flock','--nonblock','--close',str(folder/'session.lock'),
                            str(Path.home()/'.local/bin/pixel-desktop'),'--session'], env=env,
                            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
                    return {'running': True, 'state': 'starting', 'managed': True,
                            'hint': 'Wait for pixel_desktop status to report ready before GUI actions.'}
                if action == 'stop':
                    if self.desktop_process is None or self.desktop_process.poll() is not None:
                        return {'running': running, 'stopped': False, 'reason': 'This desktop was not started by the agent.'}
                    # The runtime also owns this process tree, including detached GUI clients.
                    import importlib.util
                    spec = importlib.util.spec_from_file_location('runtime', Path(__file__).with_name('pixel-t3-runtime.py'))
                    runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
                    runtime.stop_processes([{'pid': self.desktop_process.pid, 'start': runtime.identity(self.desktop_process.pid)}])
                    runtime.stop_processes([{'pid':p.pid,'start':runtime.identity(p.pid)} for p in self.desktop_apps if p.poll() is None])
                    self.desktop_apps = []
                    self.desktop_process = None
                    return {'running': False, 'stopped': True}
                return {'running': running, 'state': 'running'}


def ui_elements(xml, width, height):
    root = ET.fromstring(xml)
    items = []
    for node in root.iter('node'):
        a = node.attrib
        bounds = list(map(int, re.findall(r'-?\d+', a.get('bounds', ''))))
        if len(bounds) != 4 or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            continue
        if not (a.get('text') or a.get('content-desc') or a.get('clickable') == 'true'
                or a.get('scrollable') == 'true' or a.get('focusable') == 'true'):
            continue
        x1,y1,x2,y2 = bounds
        if x2 <= 0 or y2 <= 0 or x1 >= width or y1 >= height:
            continue
        password = a.get('password') == 'true'
        items.append({'text': '' if password else a.get('text', ''),
                      'label': a.get('content-desc', ''), 'resource_id': a.get('resource-id', ''),
                      'package': a.get('package', ''), 'class': a.get('class', ''),
                      'bounds': bounds, 'center': [round(max(0,min(width,(x1+x2)/2))/width*1000), round(max(0,min(height,(y1+y2)/2))/height*1000)],
                      'clickable': a.get('clickable') == 'true', 'scrollable': a.get('scrollable') == 'true',
                      'enabled': a.get('enabled') == 'true', 'focused': a.get('focused') == 'true', 'password': password})
    return {'width': width, 'height': height, 'elements': items[:300], 'truncated': len(items)>300,
            'hint': 'Centers use 0-1000 coordinates. Inspect again after navigation. Use a screenshot for unlabeled controls.'}


def png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("screencap did not return PNG")
    return struct.unpack(">II", data[16:24])


def denorm(v: int | float, extent: int) -> int:
    return max(0, min(extent - 1, int(float(v) / 1000 * extent)))


BRIDGE = Bridge()
TOKEN = ensure_token()


class Handler(BaseHTTPRequestHandler):
    server_version = "PixelPhone/1.0"

    def log_message(self, *a):  # quiet; log to file below
        pass

    def _send_json(self, obj: dict, code: int = 200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self) -> bool:
        if self.path == "/health" and self.command == "GET":
            return True
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {TOKEN}"

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_GET(self):
        if not self._auth_ok():
            return self._send_json({"error": "unauthorized"}, 401)
        if self.path == "/health":
            return self._send_json({"ok": True, "backend": BRIDGE.refresh()})
        if self.path == "/screenshot":
            try:
                data = BRIDGE.screenshot()
            except Exception as exc:
                return self._send_json({"error": str(exc)}, 500)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/apps":
            r = BRIDGE.run("cmd package query-activities --brief -a android.intent.action.MAIN -c android.intent.category.LAUNCHER",
                           privileged=True, timeout=30)
            if r["exit_code"] != 0:
                return self._send_json({"error": r["stderr"] or r["stdout"]}, 500)
            comps = sorted({l.strip() for l in r["stdout"].splitlines() if "/" in l})
            return self._send_json({"apps": "\n".join(comps)[:16000]})
        if self.path in ('/ui', '/desktop/status'):
            try:
                return self._send_json(BRIDGE.inspect_ui() if self.path == '/ui' else BRIDGE.desktop('status'))
            except Exception as exc:
                return self._send_json({'error': str(exc)}, 500)
        return self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._auth_ok():
            return self._send_json({"error": "unauthorized"}, 401)
        body = self._body()
        try:
            if self.path in ('/desktop/start', '/desktop/stop', '/desktop/launch', '/desktop/show', '/desktop/hide'):
                return self._send_json(BRIDGE.desktop(self.path.rsplit('/', 1)[1], body))
            if self.path == "/run":
                cmd = str(body.get("command", ""))
                if not cmd:
                    return self._send_json({"error": "command required"}, 400)
                return self._send_json(BRIDGE.run(cmd, bool(body.get("privileged")), int(body.get("timeout", 60) or 60)))
            if self.path == "/open_app":
                want = str(body.get("app", "")).strip()
                pkg = COMMON_APPS.get(want.lower(), want.split("/", 1)[0])
                if "." not in pkg:
                    out = BRIDGE.run("pm list packages -3; pm list packages -s", privileged=True)["stdout"]
                    m = [l[8:] for l in out.splitlines() if want.lower() in l.lower()]
                    if not m:
                        return self._send_json({"error": f"No package matched {want!r}; GET /apps first."}, 404)
                    pkg = m[0]
                r = BRIDGE.run(f"monkey -p {shlex.quote(pkg)} -c android.intent.category.LAUNCHER 1", privileged=True, timeout=30)
                r["package"] = pkg
                return self._send_json(r)
            if self.path in ("/tap", "/swipe", "/key", "/type"):
                return self._send_json(self._ui(self.path, body))
        except Exception as exc:
            return self._send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        return self._send_json({"error": "not found"}, 404)

    def _ui(self, path: str, body: dict) -> dict:
        w, h = BRIDGE.screen_size()

        def px(v, extent):
            v = float(v)
            # Accept 0-1000 normalized OR absolute pixels (>1000 or normalized=false).
            if body.get("normalized", True) and 0 <= v <= 1000:
                return denorm(v, extent)
            return max(0, min(extent - 1, int(v)))

        if path == "/tap":
            x, y = px(body.get("x", 0), w), px(body.get("y", 0), h)
            return BRIDGE.run(f"input tap {x} {y}", privileged=True)
        if path == "/swipe":
            sx, sy = px(body.get("sx", 0), w), px(body.get("sy", 0), h)
            ex, ey = px(body.get("ex", 0), w), px(body.get("ey", 0), h)
            dur = max(50, min(int(body.get("duration_ms", 500)), 10000))
            return BRIDGE.run(f"input swipe {sx} {sy} {ex} {ey} {dur}", privileged=True)
        if path == "/key":
            key = str(body.get("key", "")).strip().upper().replace(" ", "_")
            code = KEYCODES.get(key, key if key.startswith("KEYCODE_") else f"KEYCODE_{key}")
            if not re.fullmatch(r"KEYCODE_[A-Z0-9_]+", code):
                return {"error": f"Unsupported key: {body.get('key')!r}"}
            return BRIDGE.run(f"input keyevent {code}", privileged=True)
        if path == "/type":
            text = str(body.get("text", ""))
            helper = shutil.which("termux-clipboard-set")
            if helper:
                try:
                    c = subprocess.run([helper], input=text, text=True,
                                       capture_output=True, timeout=10, env=child_env())
                    if c.returncode == 0:
                        r = BRIDGE.run("input keyevent KEYCODE_PASTE", privileged=True)
                        r["input_method"] = "clipboard-paste"
                        if body.get("press_enter"):
                            BRIDGE.run("input keyevent KEYCODE_ENTER", privileged=True)
                        return r
                except (OSError, subprocess.SubprocessError):
                    pass
            enc = text.replace("%", "%25").replace(" ", "%s")
            r = BRIDGE.run("input text " + shlex.quote(enc), privileged=True)
            r["input_method"] = "adb-input-text-fallback"
            if body.get("press_enter"):
                BRIDGE.run("input keyevent KEYCODE_ENTER", privileged=True)
            return r
        return {"error": "unknown ui action"}


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "bridge-port").write_text(str(PORT), encoding="utf-8")
    print(f"Pixel Phone bridge on {HOST}:{PORT} backend={BRIDGE.backend}", flush=True)
    print(f"Token: {TOKEN_FILE} (mode 600, localhost only)", flush=True)
    if BRIDGE.backend == "unavailable":
        print("No rish/adb yet. Start Shizuku or pair Termux adb; the bridge will detect it automatically.", flush=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
