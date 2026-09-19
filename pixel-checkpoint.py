#!/usr/bin/env python3
"""Keep a consistent local chat backup before hibernating. Never upload it."""
import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import time


def checkpoint(home):
    folder = home / '.local/state/pixel-agent/checkpoint'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    saved = []
    # Both databases use SQLite WAL; copying live files alone is not safe.
    for name, source in [('t3', home / '.t3/userdata/state.sqlite'),
                         ('opencode', home / '.local/share/opencode/opencode.db')]:
        if not source.exists():
            continue
        temporary = folder / (name + '.tmp')
        deadline = time.monotonic() + 15
        def progress(*_):
            if time.monotonic() > deadline:
                raise TimeoutError('Session backup timed out')
        try:
            with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src:
                with closing(sqlite3.connect(temporary)) as dest:
                    src.backup(dest, pages=256, progress=progress)
                    if dest.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                        raise RuntimeError('Session backup did not pass verification')
            temporary.replace(folder / (name + '.sqlite'))
            saved.append(name)
        finally:
            temporary.unlink(missing_ok=True)
    # Projects stay in place, including uncommitted and untracked files.
    temporary = folder / 'session.tmp'
    temporary.write_text(json.dumps({'saved_at': time.time(), 'databases': saved,
                                    'projects': str(home / 'projects')}))
    temporary.replace(folder / 'session.json')


if __name__ == '__main__':
    os.umask(0o077)
    checkpoint(Path.home())
