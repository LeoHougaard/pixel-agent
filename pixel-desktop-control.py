#!/usr/bin/env python3
"""Desktop computer-use tools, run inside the existing Debian guest."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ENV = {**os.environ, 'DISPLAY': ':1', 'LIBGL_ALWAYS_SOFTWARE': '1', 'NO_AT_BRIDGE': '1'}


def run(*args, input=None, timeout=15):
    p = subprocess.run(args, input=input, capture_output=True, text=True, env=ENV, timeout=timeout)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout).strip()[:1500])
    return p.stdout.strip()


def bridge(path, body=None):
    token = (Path.home()/'.config/pixel-phone/bridge-token').read_text().strip()
    request = urllib.request.Request('http://127.0.0.1:18080'+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization':'Bearer '+token, 'Content-Type':'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=40) as response:
        return json.load(response)


def point(data, width, height, x='x', y='y'):
    return str(max(0,min(width-1,int(data[x])))), str(max(0,min(height-1,int(data[y]))))


def main(data):
    action = data['action']
    if action in ('start','stop'):
        return bridge('/desktop/'+action, {})
    if action == 'show':
        return bridge('/run', {'command':'am start -n com.termux.x11/com.termux.x11.MainActivity', 'privileged':False})
    try:
        width,height = map(int,run('xdotool','getdisplaygeometry',timeout=4).split())
    except (RuntimeError,subprocess.TimeoutExpired):
        if action == 'status':
            return {**bridge('/desktop/status'), 'ready':False}
        raise RuntimeError('Desktop is not ready. Use pixel_desktop start, then status.')
    if action == 'status':
        try: windows=run('wmctrl','-l')
        except RuntimeError:
            return {'ready':False,'width':width,'height':height,'stage':'Starting window manager'}
        return {'ready':True,'width':width,'height':height,'windows':windows}
    if action == 'screenshot':
        folder=Path('/tmp/pixel-desktop');folder.mkdir(exist_ok=True,mode=0o700)
        path=folder/f'screen-{time.time_ns()}.png'
        run('scrot','--silent',str(path))
        return {'path':str(path),'width':width,'height':height,
                'hint':'Read this file as an image. Desktop coordinates are pixels, not Android normalized coordinates.'}
    if action == 'launch':
        command=data['command'].strip()
        if not command: raise ValueError('command is required')
        return bridge('/desktop/launch', {'command':command,'cwd':os.getcwd()})
    if action in ('click','move','drag','scroll'):
        x,y=point(data,width,height)
        run('xdotool','mousemove','--sync',x,y)
        if action == 'click':
            run('xdotool','click','--repeat',str(max(1,min(2,int(data.get('clicks',1))))),str(max(1,min(3,int(data.get('button',1))))))
        if action == 'scroll':
            direction=data.get('direction','down')
            if direction not in ('up','down'): raise ValueError('Scroll direction must be up or down')
            run('xdotool','click','--repeat',str(max(1,min(20,int(data.get('amount',3))))),'--delay','80','4' if direction=='up' else '5')
        if action == 'drag':
            x2,y2=point(data,width,height,'end_x','end_y')
            run('xdotool','mousedown','1')
            try: run('xdotool','mousemove','--sync',x2,y2)
            finally: run('xdotool','mouseup','1')
    elif action == 'key':
        run('xdotool','key','--clearmodifiers',data['key'])
    elif action == 'type':
        # The foreground clipboard owner exits when replaced. No daemon escapes the runtime.
        p=subprocess.Popen(['xclip','-selection','clipboard','-quiet'],stdin=subprocess.PIPE,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=ENV)
        p.stdin.write(data['text'].encode());p.stdin.close()
        time.sleep(.15)
        if p.poll() is not None: raise RuntimeError('Could not set the desktop clipboard')
        run('xdotool','key','--clearmodifiers','ctrl+v')
    else:
        raise ValueError('Unknown desktop action')
    return {'ok':True,'hint':'Inspect a new screenshot to verify the result.'}


if __name__ == '__main__':
    try: print(json.dumps(main(json.loads(sys.argv[1]))))
    except Exception as error:
        print(json.dumps({'error':str(error)}));raise SystemExit(1)
