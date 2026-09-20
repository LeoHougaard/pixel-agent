#!/usr/bin/env python3
"""Add a return launcher without replacing the user's XFCE panel layout."""
from pathlib import Path
import subprocess


def query(*args):
    return subprocess.check_output(['xfconf-query', *args], text=True)


def main():
    launcher = Path.home() / '.local/share/applications/pixel-agent-return.desktop'
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text('''[Desktop Entry]
Type=Application
Name=Return to Pixel Agent
Comment=Return to chat and keep the desktop running
Exec=python3 /usr/local/lib/pixel-agent/pixel-desktop-control.py '{"action":"hide"}'
Icon=go-previous-symbolic
Terminal=false
Categories=Utility;
''')
    panel = '/panels/panel-1/plugin-ids'
    ids = [line.strip() for line in query('-c', 'xfce4-panel', '-p', panel).splitlines()
           if line.strip().isdigit()]
    plugin = '3773'
    query('-c', 'xfce4-panel', '-p', '/plugins/plugin-' + plugin, '-n', '-t', 'string', '-s', 'launcher')
    query('-c', 'xfce4-panel', '-p', '/plugins/plugin-' + plugin + '/items', '-n', '-a',
          '-t', 'string', '-s', str(launcher))
    if plugin not in ids:
        values = [arg for value in [plugin, *ids] for arg in ('-t', 'int', '-s', value)]
        query('-c', 'xfce4-panel', '-p', panel, '-a', *values)


if __name__ == '__main__':
    main()
