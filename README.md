# Pixel Agent

Run T3 Code and OpenCode locally on an Android phone, with Android automation,
an optional Debian desktop, and GitHub project access. Opening the app starts
services and restores chat. It does not send a model prompt.

## Requirements

- An ARM64 Android phone. Android 11 or later is recommended for wireless
  debugging. Tested on a Pixel 10 running Android 17; other phones need testing.
- Termux and Termux:API from the same distribution, such as F-Droid.
- At least 3 GB free for the coding setup, or 10 GB for the optional desktop.
- Internet access for initial installation and the selected model provider.
- Shizuku and its exported `rish` files for Android app control and complete
  idle shutdown. Coding works without Shizuku, but cleanup is more limited.

The APK is a launcher and recovery UI. Install the Termux environment below
before opening it. No accounts, credentials, conversations, or projects are
included in the repository or APK. Sign in with your own accounts.

## Install

1. Install Termux and Termux:API, then open Termux and run:

   ```sh
   termux-setup-storage
   pkg update
   pkg install git
   ```

2. Clone this repository using its GitHub **Code** URL, then run in Termux:

   ```sh
   cd pixel-agent
   bash install-pixel-phone.sh
   ```

   Installation can take several minutes. Keep Termux open until it finishes.
   The installer creates a Debian user named `pixel`.

3. Sign in inside Debian:

   ```sh
   proot-distro login debian --user pixel --shared-tmp
   opencode auth login
   gh auth login
   exit
   ```

   The included model default is Muse Spark 1.3 Free. Availability and provider
   terms can change; select a model available to your account in T3 if needed.

4. For phone control, install and start Shizuku. Export its terminal files,
   place `rish` and `rish_shizuku.dex` in Termux's `~/.local/bin`, make `rish`
   executable, and set `RISH_APPLICATION_ID=com.termux` in its script. Run
   `rish -c id` once and approve Termux in Shizuku.
   On Android 14 or later, also run `chmod 400 ~/.local/bin/rish_shizuku.dex`.

5. Download `Pixel-Agent.apk` from this repository's Releases page and install
   it. Open Pixel Agent and grant permission to run commands in Termux.
   In your first chat, choose OpenCode and a model available to your account.

After a reboot, unlock Android once and start Shizuku again through
**menu > Settings > Phone control**. Android may require wireless re-pairing.

To update an existing installation, install the new APK, then use
**menu > Repair > Repair files** to install its bundled runtime changes.
Projects, accounts and existing AGENTS.md are preserved.

## Use

The normal screen is T3 chat, a connection status, and one menu. Startup shows
its stage, elapsed time, and the age of the last service update. Menus use
matching dark colors, rounded corners, and system sans-serif text.

**GitHub projects** lists repositories for the account signed in through `gh`.
Selecting one clones it or fetches origin, registers it in T3, and opens a draft.
It preserves existing branches and uncommitted work. Send your task in chat.

**Linux desktop** starts the desktop and opens it when ready. Use the return
arrow at the top of its left panel to return to chat.
Linux apps stay open. Android navigation remains visible as another way out.

**Stop agent** works independently of the chat connection. **Reconnect chat**
re-pairs the view. **Repair** can restart services, restore bundled control
files, reset the chat view, or help restore Termux access.

Git, editor and terminal controls are available through **Workspace tools**.
The model receives environment instructions from
[pixel-opencode/AGENTS.md](pixel-opencode/AGENTS.md), installed as
`~/.config/opencode/AGENTS.md` in Debian. Existing repository instructions apply.

## Battery and saved work

Choose the idle interval in **menu > Settings**. Five minutes is the default.
Actual input resets the countdown; an untouched visible chat does not.
Desktop mouse and keyboard input also resets it, even while chat is closed.
An active task is allowed to finish, then the full idle interval begins.
If the desktop input monitor fails, automatic sleep pauses to protect work.
**Status** reports this condition; **Stop agent** remains available.

Before idle shutdown, the runtime backs up T3 and OpenCode SQLite databases
using SQLite's backup API. Backups stay in Debian at
`~/.local/state/pixel-agent/checkpoint`. Original chats and project files stay
in place, including uncommitted and untracked files. The app preserves the chat
route and T3 stores drafts locally. Reopening starts services and reconnects.

Shutdown stops managed services, kills the Termux ADB daemon, releases its
wake lock, and, when Shizuku is available, force-stops Termux, Termux:API and
Termux:X11. This closes other Termux sessions too. It never clears app data.
The background chat page is unloaded so it cannot keep polling.
The launcher also leaves Android's recent-task stack when backgrounded, so
closing Termux cannot uncover it and accidentally start services again.
Without Shizuku, it closes Linux services and invokes Termux's own Stop action.
With Shizuku, wireless debugging is disabled during sleep to release its Wi-Fi
multicast lock, then restored to its previous setting on startup. Normal Wi-Fi
connectivity and Android's Battery Saver setting are unchanged.

Save GUI documents before leaving a desktop task. Arbitrary unsaved application
memory and running terminal sessions cannot be restored after shutdown.
Do not treat a chat backup as a backup of project files or unsaved GUI documents.

## Optional Linux desktop

Install Termux:X11, then run in the same Termux checkout:

```sh
bash install-linux-desktop.sh
```

This installs XFCE, a browser and OrcaSlicer. The `pixel_desktop` tool can start
it, launch apps, capture screenshots and control mouse/keyboard input. Desktop
coordinates are pixels; Android tool coordinates are normalized from 0 to 1000.
Use `orca-slicer-pixel` to launch OrcaSlicer. The desktop starts only when needed.

Debian uses PRoot and software rendering. Linux applications that need kernel
features, hardware acceleration or x86 binaries may not work.

## Build and verification

`python Build-PixelApp.py` builds and signs the APK on Windows or Debian ARM64,
including on the phone. See [maintenance instructions](docs/MAINTENANCE.md)
for Linux build tools, runtime updates and agent access.
Output: `.downloads/Pixel-Agent.apk`. Keep the
ignored `pixel-app/.signing` directory for future updates. `--debug` enables
WebView inspection; release builds disable it. `PIXEL_APPLICATION_ID` can be
set when maintaining a private installation with a different package ID.

Run the focused checks with:

```sh
python -m unittest discover -s tests
node --test tests/test_pixel_t3_watch.mjs
```

See [DESKTOP-VERIFICATION.md](DESKTOP-VERIFICATION.md) for device verification
and its limits. No multi-day battery-life claim is made.
