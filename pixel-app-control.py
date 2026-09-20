#!/usr/bin/env python3
"""Small command API for the Android app, transported by Termux intents."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import urllib.error

spec = importlib.util.spec_from_file_location('runtime', Path(__file__).with_name('pixel-t3-runtime.py'))
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
STATE = runtime.STATE


def read_json(name, default=None):
    try:
        value = json.loads((STATE / name).read_text())
        return value if isinstance(value, dict) else default
    except (OSError, ValueError):
        return default


def running():
    owner = read_json('owner.json', {})
    return owner.get('start') is not None and runtime.identity(owner.get('pid')) == owner['start']


def status():
    result = read_json('status.json', {'phase': 'stopped'})
    if not running() and result.get('phase') in ('starting', 'ready', 'stopping'):
        result = {'phase': 'stopped', 'message': 'The service stopped. Tap Start to recover.'}
    sample = runtime.latest_activity()
    age = max(0, time.time() - result.get('updated_at', 0))
    result.update(idle_minutes=runtime.idle_minutes(), busy=result.get('busy', sample.get('busy')),
                  monitor_ok=result.get('monitor_ok', sample.get('ok', False)),
                  heartbeat_age=round(age), version=2)
    job=read_json('project-job.json')
    if job:result['project_job']=job
    result['desktop'] = runtime.desktop_activity()
    return result


def start(expected_cancel=None):
    import fcntl
    if expected_cancel is None:
        expected_cancel = runtime.cancellation_token()
    with (STATE / 'launch.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if runtime.cancellation_token() != expected_cancel:
            return status()
        (STATE / 'use').touch()
        # Recover a missing owner file without interrupting the live runtime.
        if not running():
            target = str(runtime.INSTALL / 'pixel-t3-runtime.py')
            for path in Path('/proc').glob('[0-9]*/cmdline'):
                try:
                    args = path.read_bytes().decode(errors='replace').strip('\0').split('\0')
                    if len(args) > 1 and args[1] == target:
                        pid = int(path.parent.name)
                        (STATE / 'owner.json').write_text(json.dumps({'pid': pid, 'start': runtime.identity(pid)}))
                        break
                except (OSError, ValueError):
                    continue
        # A tap during idle cleanup queues a new start instead of opening a dying server.
        deadline = time.monotonic() + 30
        while read_json('status.json', {}).get('phase') in ('stopping', 'stopped', 'error'):
            with (STATE / 'runtime.lock').open('w') as runtime_lock:
                try:
                    fcntl.flock(runtime_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Service is stuck. Use menu > Repair > Restart services.')
            time.sleep(.25)
        if not running():
            if runtime.cancellation_token() != expected_cancel:
                return status()
            (STATE / 'stop').unlink(missing_ok=True)
            runtime.write_state('starting')
            with (STATE / 'runtime.log').open('w') as log:
                subprocess.Popen([sys.executable, str(Path(__file__).with_name('pixel-t3-runtime.py'))],
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            # Let the owner file appear before another foreground status request.
            for _ in range(20):
                if running():
                    break
                time.sleep(.1)
            if runtime.cancellation_token() != expected_cancel:
                runtime.stop()
    return status()


def stop(wait=False, cancel=True):
    with contextlib.redirect_stdout(io.StringIO()):
        runtime.stop(cancel=cancel)
    if wait:
        deadline = time.monotonic() + 25
        while running() and time.monotonic() < deadline:
            time.sleep(.25)
        if running():
            roots = runtime.saved_roots()
            owner = read_json('owner.json', {})
            runtime.stop_processes(roots + [owner])
            runtime.command('termux-wake-unlock')
    return status()


def recover_processes():
    # Explicit Restart can recover missing PID files. Match executable arguments,
    # not arbitrary substrings in shell commands, and only the local Pixel stack.
    roots = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args = path.read_bytes().decode(errors='replace').strip('\0').split('\0')
            if len(args) < 2:
                continue
            pixel_python = args[1] in (str(runtime.INSTALL / 'pixel-t3-runtime.py'),
                                       str(runtime.INSTALL / 'pixel-phone-bridge.py'))
            t3_server = args[1].endswith('/node_modules/t3/dist/bin.mjs') and 'serve' in args[2:] and '3773' in args[2:]
            monitor = args[1] == '/usr/local/lib/pixel-agent/pixel-t3-watch.mjs'
            if pixel_python or t3_server or monitor:
                pid = int(path.parent.name)
                roots.append({'pid': pid, 'start': runtime.identity(pid)})
        except (OSError, ValueError):
            continue
    if roots:
        runtime.stop_processes(roots)
        runtime.command('termux-wake-unlock')


def diagnostics():
    result = status()
    checks = []
    for label, path in [
        ('Runtime', Path(__file__).with_name('pixel-t3-runtime.py')),
        ('Start command', runtime.BIN / 'pixel-t3-mobile'),
        ('Phone bridge', runtime.INSTALL / 'pixel-phone-bridge.py'),
    ]:
        checks.append({'name': label, 'ok': path.is_file()})
    checks.append({'name': 'Local chat server', 'ok': runtime.service_ready()})
    backend = 'not running'
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                'http://127.0.0.1:18080/health', timeout=10) as response:
            backend = json.load(response).get('backend', 'unavailable')
    except (OSError, ValueError):
        pass
    result.update(checks=checks, phone_control=backend,
                  help='Phone control needs Shizuku after a phone restart. Coding and chat work without it.')
    return result


def main(args):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    command = args[0] if args else 'status'
    if command == 'start':
        return start()
    if command == 'status':
        if args[1:] == ['active']:
            (STATE / 'use').touch()
        return status()
    if command == 'stop':
        return stop()
    if command == 'restart':
        token = runtime.cancellation_token()
        stop(wait=True, cancel=False)
        if runtime.cancellation_token() != token:
            return status()
        recover_processes()
        return start(expected_cancel=token)
    if command == 'settings':
        minutes = int(args[1])
        if minutes not in (2, 5, 10, 15, 30, 60):
            raise ValueError('Choose an idle time between 2 and 60 minutes.')
        temporary = STATE / 'settings.tmp'
        temporary.write_text(json.dumps({'idle_minutes': minutes}))
        temporary.replace(STATE / 'settings.json')
        return status()
    if command == 'diagnostics':
        return diagnostics()
    if command == 'desktop-view':
        return {'ok': runtime.command('termux-x11-preference', 'fullscreen:false')}
    if command == 'desktop':
        if not running() or not runtime.service_ready():
            raise RuntimeError('Wait for the agent to connect before opening the desktop.')
        (STATE / 'use').touch()
        token = (Path.home() / '.config/pixel-agent/bridge-token').read_text().strip()
        request = urllib.request.Request('http://127.0.0.1:18080/desktop/start', data=b'{}',
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=45) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            result = json.load(error)
        if result.get('error'):
            raise RuntimeError(result['error'])
        return {'desktop_starting': True}
    if command in ('projects','project'):
        action=['list'] if command=='projects' else ['open',args[1]]
        result=subprocess.run(['proot-distro','login','debian','--user','pixel','--shared-tmp',
            '--bind',str(STATE)+':/run/pixel-agent-state','--','python3','/usr/local/lib/pixel-agent/pixel-projects.py',*action],
            capture_output=True,text=True,timeout=600)
        try:return json.loads(result.stdout)
        except ValueError:raise RuntimeError('GitHub did not respond. Check its sign-in in Termux.')
    if command == 'pair':
        if not running() or not runtime.service_ready():
            raise RuntimeError('The server is not ready. Tap Start first.')
        result = subprocess.run(['proot-distro', 'login', 'debian', '--user', 'pixel', '--shared-tmp',
                                 '--', '/bin/bash', '-lc', 'pixel-t3-server --pair-only'],
                                capture_output=True, text=True, timeout=90)
        url = result.stdout.strip()
        if result.returncode or not url.startswith('http://127.0.0.1:3773/pair#token='):
            raise RuntimeError('Pairing failed. Use menu > Repair > Restart services.')
        return {'url': url}
    raise ValueError('Unknown control action')


if __name__ == '__main__':
    os.umask(0o077)
    try:
        print(json.dumps(main(sys.argv[1:])))
    except Exception as error:
        print(json.dumps({'phase': 'error', 'message': str(error)}))
        raise SystemExit(1)
