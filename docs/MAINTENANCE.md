# Maintaining Pixel Agent from the phone

The agent has normal Debian shell/file tools, `git`, `gh`, Android controls,
and `pixel_desktop`. Use them to inspect, edit, test and update this project
when the user asks. Opening the app never sends a maintenance task or model prompt.

## Source and installed files

Work in a clone of the public repository. Check `git remote -v` and
`git status --short` first. An older private installation may also have an
archived checkout; do not publish its history. Keep keys, accounts, chats,
device identifiers and private project paths out of source and release assets.

- Termux controls: `~/.local/share/pixel-agent`, commands: `~/.local/bin`.
- Termux runtime state and logs: `~/.local/state/pixel-t3`.
- Debian helpers: `/usr/local/lib/pixel-agent`.
- Debian tools/instructions: `~/.config/opencode`.
- Desktop session: `/usr/local/bin/pixel-desktop-session`.
- Installed Android package ID: Termux's `~/.config/pixel-agent/app-id`.

Use `pixel_run` with `privileged=false` for Termux. Its `$HOME` is Termux's
home, not Debian's. For root access inside Debian, use Termux's
`proot-distro login debian --shared-tmp -- <command>`.

## Runtime changes

1. Edit source and run the focused checks in the README.
2. Copy the source to a temporary Termux directory, or `/sdcard/Download`,
   then run `bash apply-pixel-power.sh` from there using `pixel_run`.
   This installs controls without upgrading packages or replacing accounts.
3. Save all work and finish the reply before restarting. Restarting services
   kills the agent performing the update. The user can reopen the app, or use
   **menu > Repair > Restart services** after the task finishes.

Keep APK-bundled controls current when publishing. **Repair files** restores
the bundled version and can overwrite a runtime-only patch. The installer
preserves existing AGENTS.md; edit its relevant lines deliberately when needed.

## Android app changes

`python3 Build-PixelApp.py` runs on Windows and Debian ARM64. On Debian, install
`aapt`, `zipalign`, `apksigner`, and `default-jdk-headless` as root. Debian supplies
native ARM64 executables; the Google SDK's Linux native executables are x86.

The build also needs Android SDK Java archives:

- `android.jar` from Android SDK Platform 34 on Debian. Its packaged AAPT2
  cannot read newer platform resource tables. This app still targets API 35.
- `lib/d8.jar` from Android SDK Build Tools 36.0.0.

Install the platform and build tools using the
[Android SDK tools](https://developer.android.com/tools), or copy these two
archives from an existing SDK. They run on ARM64. By default the builder reads
`~/.cache/pixel-agent/android-sdk/platforms/android-34/android.jar` and
`~/.cache/pixel-agent/android-sdk/build-tools/36.0.0/lib/d8.jar` on Debian.
`PIXEL_ANDROID_JAR`, `PIXEL_D8_JAR`, `ANDROID_HOME`, and `JAVA_HOME` can override
the paths. No model call is needed to build.

Use the installed app's package ID and its original signing key for updates:

```sh
# If this installation has a saved build environment:
test ! -f ~/.config/pixel-agent/build.env || . ~/.config/pixel-agent/build.env
python3 Build-PixelApp.py
```

`PIXEL_APPLICATION_ID` overrides the public package ID. `PIXEL_SIGNING_KEY`
selects a private keystore; otherwise the ignored `pixel-app/.signing` key is
used or created. Keep the existing key backed up privately. A different key
cannot update an installed APK. Do not uninstall the app to work around this,
because uninstalling loses its saved drafts and view state.
For a public release, unset private package-ID overrides and keep the device's
build environment and keystore out of the published files.

The output is `.downloads/Pixel-Agent.apk`. Copy it to shared Downloads and open
it with Android's installer. Android may require the user to approve installation.
With working Shizuku, `pixel_run` with Android shell privileges can copy the APK
to `/data/local/tmp/pixel-agent-update.apk`, run `pm install -r` on that copy,
then remove the temporary copy. Installing directly from shared storage may
fail. Verify the installed version and update time,
then reopen the app and test the actual workflow. Increment `versionCode` and
`versionName` before a new release. A debug build is only for local inspection.

## Desktop behavior to preserve

The app menu starts the managed desktop and waits for its window manager.
`pixel_desktop show` opens the viewer; `hide` or the return arrow returns to
Pixel Agent without closing Linux apps. Android's
navigation remains available if Linux hangs.

The X11 screensaver extension reports time since mouse or keyboard input.
`pixel-desktop-activity.py` reports it every three seconds through the shared
temporary directory. The runtime waits for both agent completion and a full
idle interval without input. A missing desktop input monitor pauses automatic
sleep to protect work. It does not disable the explicit Stop control.

Verify cold launch, return to chat, repeated desktop entry, keyboard/mouse use
beyond the idle interval, and sleep after use stops. Save GUI documents before
testing shutdown. Chat/database backup cannot restore unsaved GUI memory.
