#!/usr/bin/env python3
"""GitHub checkout and T3 registration. Never reset or merge an existing checkout."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

STATE=Path('/run/pixel-agent-state')


def cancellation():
    try:return (STATE/'cancel-start').stat().st_mtime_ns
    except OSError:return 0


CANCEL=cancellation()


def progress(stage):
    if STATE.is_dir():
        p=STATE/'project-job.tmp';p.write_text(json.dumps({'stage':stage,'updated_at':time.time()}));p.replace(STATE/'project-job.json')


def command(args,stage,timeout=60):
    if cancellation()!=CANCEL:raise RuntimeError('Stopped')
    progress(stage)
    p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True,env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GH_PROMPT_DISABLED':'1'})
    deadline=time.monotonic()+timeout
    while True:
        try:
            out,err=p.communicate(timeout=2)
            if p.returncode: raise RuntimeError((err or out).strip()[:500])
            return out.strip()
        except subprocess.TimeoutExpired:
            if time.monotonic()>=deadline or cancellation()!=CANCEL:
                os.killpg(p.pid,signal.SIGKILL);p.communicate();raise RuntimeError('Stopped' if cancellation()!=CANCEL else 'GitHub did not finish in time. Try again from the menu.')
            progress(stage)


def repository_name(value):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',value) or any(s in ('.','..') for s in value.split('/')):
        raise ValueError('Use a GitHub repository name such as owner/repository.')
    return value


def main(args):
    if args[0]=='list':
        out=command(['gh','repo','list','--limit','100','--json','nameWithOwner'],'Reading GitHub repositories')
        return {'repositories':[r['nameWithOwner'] for r in json.loads(out)]}
    repo=repository_name(args[1]); owner,name=repo.split('/')
    base=(Path.home()/'projects').resolve();base.mkdir(exist_ok=True)
    old=base/name
    destination=base/owner/name
    if (old/'.git').exists():
        remote=command(['git','-C',str(old),'remote','get-url','origin'],'Checking local repository')
        if remote.removesuffix('.git').endswith('/'+repo) or remote.removesuffix('.git').endswith(':'+repo):destination=old
    destination=destination.resolve()
    if not destination.is_relative_to(base):raise ValueError('Checkout path must be inside projects.')
    if destination.exists():
        remote=command(['git','-C',str(destination),'remote','get-url','origin'],'Checking local repository')
        if not (remote.removesuffix('.git').endswith('/'+repo) or remote.removesuffix('.git').endswith(':'+repo)):
            raise ValueError('The local folder belongs to a different repository.')
        command(['git','-C',str(destination),'fetch','origin'],'Fetching '+repo,timeout=480)
    else:
        destination.parent.mkdir(parents=True,exist_ok=True)
        command(['gh','repo','clone',repo,str(destination),'--','--progress'],'Cloning '+repo,timeout=480)
    entry=Path.home()/'.local/share/t3-code/node_modules/t3/dist/bin.mjs'
    if not entry.exists():entry=Path((Path.home()/'.local/state/t3-code-entry').read_text().strip())
    output=command(['node',str(Path(__file__).with_name('pixel-project-register.mjs')),str(entry),str(destination),name],'Opening '+repo,timeout=90)
    return {**json.loads(output),'path':str(destination)}


if __name__=='__main__':
    try:print(json.dumps(main(sys.argv[1:])))
    except Exception as e:print(json.dumps({'error':str(e)}));raise SystemExit(1)
    finally:
        if STATE.is_dir():(STATE/'project-job.json').unlink(missing_ok=True)
