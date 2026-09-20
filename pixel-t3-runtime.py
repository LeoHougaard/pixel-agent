#!/usr/bin/env python3
"""Termux owns startup and stop, independently of T3's network connection."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

STATE = Path.home() / '.local/state/pixel-t3'
BIN = Path.home() / '.local/bin'
INSTALL = Path.home() / '.local/share/pixel-agent'
IDLE_SECONDS = 300
START_SECONDS = 600


def idle_minutes():
    try:
        value = json.loads((STATE / 'settings.json').read_text()).get('idle_minutes', 5)
        return value if value in (2, 5, 10, 15, 30, 60) else 5
    except (OSError, ValueError, AttributeError, TypeError):
        return 5


def write_state(phase, **fields):
    temporary = STATE / 'status.tmp'
    temporary.write_text(json.dumps({'phase': phase, 'updated_at': time.time(), **fields}))
    temporary.replace(STATE / 'status.json')


def command(*args, timeout=10):
    try:
        return subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=timeout).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def notify(message, ongoing=True):
    command('termux-notification', '--id', '3773', '--title', 'Pixel Agent',
            '--content', message, '--alert-once', '--priority', 'low',
            *(('--ongoing',) if ongoing else ()),
            '--button1', 'Stop agent', '--button1-action', str(BIN / 'pixel-t3-stop'),
            '--button2', 'Open agent', '--button2-action', str(BIN / 'pixel-app-open'))


def identity(pid):
    try:
        # starttime prevents a stale PID file from targeting an unrelated process.
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def descendants(pid):
    parents = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_text().rsplit(')', 1)[1].split()
            parents[int(path.parent.name)] = int(fields[1])
        except (OSError, ValueError, IndexError):
            continue
    result = set()
    frontier = {pid}
    while frontier:
        frontier = {child for child, parent in parents.items() if parent in frontier} - result
        result.update(frontier)
    return result


def stop_processes(roots):
    # Include detached provider/terminal children, which can have their own group.
    owned = {}
    for root in roots:
        if root['start'] is not None and identity(root['pid']) == root['start']:
            for pid in descendants(root['pid']) | {root['pid']}:
                owned[pid] = identity(pid)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid, started in owned.items():
            if started is not None and identity(pid) == started:
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    pass
        if sig == signal.SIGTERM:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline and any(
                    started is not None and identity(pid) == started for pid, started in owned.items()):
                time.sleep(.2)


def saved_roots():
    try:
        value = json.loads((STATE / 'children.json').read_text())
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict) and isinstance(item.get('pid'), int)
                and isinstance(item.get('start'), str)]
    except (OSError, ValueError):
        return []


def provider_work(server_pid):
    # A provider may settle a T3 turn before its shell command has exited.
    # Keep actual children of OpenCode alive, including detached commands.
    for pid in descendants(server_pid):
        try:
            args = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
            if args and Path(os.fsdecode(args[0])).name == 'opencode' and b'serve' in args[1:]:
                if descendants(pid):
                    return True
        except OSError:
            continue
    return False


def service_ready():
    try:
        request = urllib.request.Request('http://127.0.0.1:3773/.well-known/t3/environment')
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=2) as response:
            data = json.load(response)
            return bool(data.get('environmentId') and data.get('serverVersion'))
    except (OSError, ValueError):
        return False


def latest_activity():
    try:
        with (STATE / 'activity.jsonl').open('rb') as stream:
            stream.seek(max(0, stream.seek(0, 2) - 4096))
            for line in reversed(stream.read().splitlines()):
                try:
                    data = json.loads(line)
                    if isinstance(data, dict) and 'ok' in data:
                        return data
                except ValueError:
                    continue
    except OSError:
        pass
    return {}


def desktop_activity():
    lock_path = Path.home() / '.local/state/pixel-desktop/session.lock'
    if not lock_path.exists():
        return {'running': False}
    import fcntl
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return {'running': False}
        except BlockingIOError:
            pass
    try:
        path = Path(os.environ.get('TMPDIR', '/data/data/com.termux/files/usr/tmp')) / 'pixel-desktop-activity.json'
        data = json.loads(path.read_text())
        valid = (0 <= time.time() - data['time'] < 15
                 and math.isfinite(data['idle_seconds']) and data['idle_seconds'] >= 0)
        return {**data, 'running': True, 'monitor_ok': valid, 'ready': valid and data.get('ready') is True}
    except (OSError, ValueError, TypeError, KeyError):
        return {'running': True, 'monitor_ok': False, 'ready': False}


def idle_elapsed(sample, last_use, now, wall_time, idle_seconds=IDLE_SECONDS, desktop=None):
    # Unknown/stale state cannot prove that it is safe to stop a task.
    known = sample.get('ok') is True and 0 <= wall_time - sample.get('time', 0) < 60
    # A visible chat is not user activity. Only input or actual work resets this.
    if not known or sample.get('busy') is not False:
        return now, False
    if desktop and desktop.get('running'):
        # Never close desktop work if its input clock cannot be checked.
        if not desktop.get('monitor_ok') or not desktop.get('ready'):
            return now, False
        since_input = max(0, wall_time - desktop['time'] + desktop['idle_seconds'])
        last_use = max(last_use, now - since_input)
    return last_use, now - last_use >= idle_seconds


def checkpoint():
    return command('proot-distro', 'login', 'debian', '--user', 'pixel', '--shared-tmp',
                   '--', 'python3', '/usr/local/lib/pixel-agent/pixel-checkpoint.py', timeout=45)


def close_helpers():
    # adb daemonizes outside our process tree. Do not leave its USB/Wi-Fi
    # discovery running while the agent is asleep.
    command('adb', 'kill-server', timeout=5)
    command('termux-wake-unlock')


def wireless_debugging(sleeping):
    """Release wireless ADB's multicast lock, preserving the user's setting."""
    marker = STATE / 'wireless-debugging.json'
    if not sleeping and not marker.exists():
        return
    for path in (BIN / 'rish', Path.home() / 'rish'):
        if not path.is_file():
            continue
        env = os.environ.copy(); env['RISH_APPLICATION_ID'] = 'com.termux'
        try:
            if sleeping:
                result = subprocess.run([str(path), '-c', 'settings get global adb_wifi_enabled'],
                                        env=env, capture_output=True, text=True, timeout=8)
                if result.returncode or result.stdout.strip() != '1':
                    return
                marker.write_text(json.dumps({'previous': 1}))
                value = '0'
            else:
                value = str(json.loads(marker.read_text())['previous'])
                if value not in ('0', '1'):
                    return
            result = subprocess.run([str(path), '-c', 'settings put global adb_wifi_enabled ' + value],
                                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
            if result.returncode == 0 and not sleeping:
                marker.unlink(missing_ok=True)
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
            pass
        return


def hibernate_apps():
    # Android shell can stop the whole Termux UID, including orphaned PRoot,
    # X11, audio and terminal sessions. Data directories are never cleared.
    for candidate in (BIN / 'rish', Path.home() / 'rish'):
        if candidate.is_file():
            env = os.environ.copy(); env['RISH_APPLICATION_ID'] = 'com.termux'
            try:
                subprocess.run([str(candidate), '-c',
                    'am force-stop com.termux.x11; am force-stop com.termux.api; am force-stop com.termux'],
                    env=env, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.TimeoutExpired):
                pass
            break
    # Shizuku may be unavailable after reboot. Close detached Linux services
    # from our own UID and use Termux's own Stop action as the fallback.
    roots = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            if path.stat().st_uid != os.getuid():
                continue
            executable = path.read_bytes().split(b'\0')[0].split(b'/')[-1]
            if executable in (b'proot', b'adb', b'pulseaudio', b'termux-x11', b'sshd', b'virgl_test_server_android'):
                pid = int(path.parent.name)
                roots.append({'pid': pid, 'start': identity(pid)})
        except (OSError, ValueError):
            continue
    stop_processes(roots)
    command('am', 'broadcast', '-a', 'com.termux.x11.ACTION_STOP', '-p', 'com.termux.x11')
    command('am', 'startservice', '-n', 'com.termux/.app.TermuxService', '-a', 'com.termux.service_stop')


def serve():
    import fcntl
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (STATE / 'runtime.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        (STATE / 'owner.json').write_text(json.dumps({'pid': os.getpid(), 'start': identity(os.getpid())}))
        processes = []
        roots = []
        handles = []
        stopping = False
        wake_acquired = False
        reason = 'Stopped. Open Pixel Agent to start again.'
        idle_shutdown = False
        checkpoint_ok = False
        started_at = time.time()
        stage_since = started_at
        current_stage = ''
        last_report = 0

        def report(phase, stage, **fields):
            nonlocal current_stage, stage_since, last_report
            now = time.time()
            if stage != current_stage:
                current_stage, stage_since = stage, now
            last_report = time.monotonic()
            write_state(phase, stage=stage, started_at=started_at,
                        stage_since=stage_since, **fields)

        def stop_signal(*_):
            nonlocal stopping
            stopping = True

        signal.signal(signal.SIGTERM, stop_signal)
        signal.signal(signal.SIGINT, stop_signal)

        def spawn(argv, log):
            handle = (STATE / log).open('w')
            handles.append(handle)
            process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=handle,
                                       stderr=handle, start_new_session=True)
            processes.append(process)
            roots.append({'pid': process.pid, 'start': identity(process.pid)})
            temporary = STATE / 'children.tmp'
            temporary.write_text(json.dumps(roots))
            temporary.replace(STATE / 'children.json')
            return process

        try:
            report('starting', 'Preparing session')
            wireless_debugging(False)
            # Recover only children recorded by a previous managed run.
            stop_processes(saved_roots())
            if service_ready():
                raise RuntimeError('Another T3 server is running. Use menu > Repair > Restart services.')
            wake_acquired = command('termux-wake-lock')
            notify('Starting. You can stop startup here too.')
            report('starting', 'Starting T3')
            server = spawn(['proot-distro', 'login', 'debian', '--user', 'pixel', '--shared-tmp',
                            '--', '/bin/bash', '-lc', 'exec pixel-t3-server --serve'], 'server.log')
            # Start the bridge in this process tree so Stop also cancels phone actions.
            bridge = spawn([sys.executable, str(INSTALL / 'pixel-phone-bridge.py')], 'bridge.log')
            (Path.home() / '.local/state/pixel-phone').mkdir(parents=True, exist_ok=True)
            (Path.home() / '.local/state/pixel-phone/bridge.pid').write_text(str(bridge.pid))
            deadline = time.monotonic() + START_SECONDS
            watcher = None
            sync = None
            last_use = time.monotonic()
            touch_time = 0
            ready = False
            unknown_since = None
            warned = False
            next_watch = 0
            next_work_check = 0
            provider_busy = False
            while not stopping and not (STATE / 'stop').exists():
                if server.poll() is not None:
                    raise RuntimeError('T3 exited. Open Pixel Agent to restart; see server.log if it repeats.')
                if bridge.poll() is not None:
                    raise RuntimeError('Phone tools stopped. Use menu > Repair > Restart services.')
                if watcher is None and time.monotonic() >= next_watch and service_ready():
                    # Sync the bridge token without starting another bridge or taking a wake lock.
                    if sync is None:
                        report('starting', 'Connecting phone tools')
                        sync = spawn([str(BIN / 'pixel-phone-bridge')], 'bridge-start.log')
                    watcher = spawn(['proot-distro', 'login', 'debian', '--user', 'pixel', '--shared-tmp',
                                     '--', '/bin/bash', '-lc', 'exec pixel-t3-server --watch'], 'activity.jsonl')
                if watcher is not None and watcher.poll() is not None:
                    watcher = None
                    next_watch = time.monotonic() + 30
                    notify('Retrying the idle monitor. Stop agent remains available here.')
                sample = latest_activity() if watcher else {}
                now = time.monotonic()
                if now >= next_work_check:
                    provider_busy = provider_work(server.pid)
                    next_work_check = now + 15
                if provider_busy:
                    sample = {**sample, 'busy': True}
                if not ready:
                    if sample.get('ok') is True and sync is not None and sync.poll() == 0:
                        ready = True
                        last_use = now
                        report('ready', 'Connected', busy=sample.get('busy', False))
                        notify('Running. Stops automatically when idle. Open Pixel Agent for controls.')
                    elif now >= deadline:
                        raise RuntimeError('Startup timed out after 10 minutes. Open Pixel Agent to retry.')
                else:
                    try:
                        touched = (STATE / 'use').stat().st_mtime_ns
                        if touched != touch_time:
                            touch_time, last_use = touched, now
                    except OSError:
                        pass
                    desktop = desktop_activity()
                    last_use, idle = idle_elapsed(sample, last_use, now, time.time(), idle_minutes() * 60, desktop)
                    if idle:
                        report('saving', 'Saving session')
                        checkpoint_ok = checkpoint()
                        if not checkpoint_ok:
                            raise RuntimeError('Could not back up the session. Saved work remains in its original files.')
                        # A tap or a new turn during the backup cancels sleep.
                        fresh = latest_activity()
                        try:
                            changed = (STATE / 'use').stat().st_mtime_ns != touch_time
                        except OSError:
                            changed = False
                        last_use, still_idle = idle_elapsed(fresh, last_use, time.monotonic(), time.time(),
                                                            idle_minutes() * 60, desktop_activity())
                        if changed or not still_idle or provider_work(server.pid):
                            last_use = time.monotonic()
                            report('ready', 'Connected', busy=fresh.get('busy', False))
                            continue
                        idle_shutdown = True
                        reason = f'Stopped after {idle_minutes()} idle minutes. Android can sleep.'
                        break
                    known = sample.get('ok') is True and time.time() - sample.get('time', 0) < 60
                    if known:
                        unknown_since, warned = None, False
                    else:
                        unknown_since = unknown_since or now
                        if now - unknown_since > 45 and not warned:
                            notify('Connection check failed. Use Stop agent here if chat cannot stop the task.')
                            warned = True
                if now - last_report >= 5:
                    known = sample.get('ok') is True and 0 <= time.time() - sample.get('time', 0) < 60
                    stage = ('Working' if sample.get('busy') else 'Connected') if ready else (
                        'Checking connection' if sync is not None and sync.poll() == 0 else current_stage)
                    if ready and not known:
                        stage = 'Retrying status connection'
                    desktop = desktop_activity()
                    if ready and desktop.get('running') and not desktop.get('monitor_ok'):
                        stage = 'Desktop input monitor unavailable; sleep paused'
                    report('ready' if ready else 'starting', stage,
                           busy=sample.get('busy', False), monitor_ok=known)
                time.sleep(1)
        except Exception as error:
            reason = str(error)
            report('error', 'Startup failed', message=reason)
        finally:
            # Preserve a startup error so the waiting launcher can explain it.
            try:
                failed = json.loads((STATE / 'status.json').read_text()).get('phase') == 'error'
            except (OSError, ValueError):
                failed = False
            if not failed:
                report('stopping', 'Stopping tasks')
            stop_processes(roots)
            for process in processes:
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
            for handle in handles:
                handle.close()
            close_helpers()
            (STATE / 'owner.json').unlink(missing_ok=True)
            (STATE / 'children.json').unlink(missing_ok=True)
            (STATE / 'stop').unlink(missing_ok=True)
            if not failed:
                report('stopped', 'Sleeping', message=reason, checkpoint_saved=checkpoint_ok)
            command('sync', timeout=5)
            command('termux-notification-remove', '3773')
            if idle_shutdown:
                wireless_debugging(True)
                hibernate_apps()
        return 0


def cancellation_token():
    try:
        return (STATE / 'cancel-start').stat().st_mtime_ns
    except OSError:
        return 0


def stop(cancel=True):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    if cancel:
        (STATE / 'cancel-start').touch()
    (STATE / 'stop').touch()
    try:
        owner = json.loads((STATE / 'owner.json').read_text())
        pid = owner['pid']
        if owner['start'] is not None and identity(pid) == owner['start']:
            os.kill(pid, signal.SIGTERM)
            print('Stopping Pixel Agent and its tasks.')
            return 0
    except (OSError, ValueError, KeyError):
        pass
    roots = saved_roots()
    if roots:
        stop_processes(roots)
        command('termux-wake-unlock')
        (STATE / 'children.json').unlink(missing_ok=True)
        write_state('stopped', message='Stopped. Open Pixel Agent to start again.')
        print('Stopped the remaining Pixel Agent processes.')
        return 0
    print('Pixel Agent is already stopped.')
    return 0


if __name__ == '__main__':
    os.umask(0o077)
    raise SystemExit(stop() if sys.argv[1:] == ['stop'] else serve())
