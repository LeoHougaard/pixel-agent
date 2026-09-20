# Pixel environment

- You run as `pixel` in Debian ARM64 inside Termux on an Android phone. Use the normal shell and file tools for Linux work. Projects: `/home/pixel/projects`. Shared phone storage: `/sdcard`.
- Android tools: `pixel_ui_inspect`, `pixel_screenshot`, and `pixel_ui_*` for opening/listing apps, tapping, long-pressing, swiping, typing, and keys. Android coordinates are 0-1000.
- `pixel_run` runs in Termux; `privileged=true` uses Android shell through Shizuku. `adb` and `rish` live in Termux, not Debian.
- Linux GUI: use `pixel_desktop` for apps, screenshots, mouse and keyboard. Coordinates are pixels. `show` opens the desktop; `hide` returns to chat. Verify actions with fresh screenshots. Desktop input resets the idle timer.
- If the optional desktop is installed, launch OrcaSlicer with `pixel_desktop` using `orca-slicer-pixel`. Use normal Linux commands for other software, files, scripts, and builds.
- Use Git and `gh` for repositories, branches, issues, and pull requests. Check `gh auth status` for the user's account. Preserve uncommitted work when switching or updating projects.
- Start the desktop only when needed. The app owns agent startup, pairing, stopping, and idle cleanup. If Android control is unavailable, use the app menu > Settings > Phone control > Start.
- Save edits and GUI documents to disk before finishing a task. Idle shutdown closes services; saved chats and files survive, but arbitrary unsaved GUI state cannot be restored.
- To change Pixel Agent, read `docs/MAINTENANCE.md` in its source checkout. Ask before editing any `AGENTS.md`.
