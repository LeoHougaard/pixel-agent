# Device verification

## Previously verified on a Pixel 10, Android 17

- Native Stop works when chat networking is disconnected.
- Startup reports stages and elapsed time; a paused supervisor produces a
  stale-status indication instead of a false Connected status.
- Android screen inspection, screenshots, app launch and navigation work.
- The Debian desktop launches OrcaSlicer. Mouse, keyboard and clipboard typing
  were checked in its file dialog without slicing or printing.
- The GitHub picker clones a repository, registers its checkout and opens a
  draft without sending a model prompt or changing the remote repository.
- Menus and selection dialogs use matching dark colors and rounded corners.

## Battery changes

The original idle logic treated any visible client as activity and refreshed
its use marker on every status poll. A detached ADB daemon could also survive
shutdown. The revised logic counts actual input, lets active work finish,
then waits the full idle interval. SQLite backups precede idle shutdown.

The app unloads its background WebView. Managed shutdown closes its services,
releases the wake lock and stops ADB. With Shizuku, it also stops the Termux,
Termux:API and Termux:X11 Android packages without clearing their data.
Wireless debugging is disabled during sleep and restored on startup to release
the Android ADB multicast lock. A fallback uses Termux's own Stop action if
Shizuku is unavailable.

## Verified for 1.1

- A two-minute idle check completed while chat remained visible and untouched.
  The app returned to Android's home screen. Termux, its API service, and its
  Linux processes stopped; the Termux wake lock was released.
- Wireless debugging changed from enabled to disabled during shutdown and
  returned to enabled when the app was reopened. Battery Saver was unchanged.
- T3 and OpenCode backups completed. The original and backup T3 databases
  passed SQLite integrity checks with the same message count. A saved test file
  was preserved. No model messages were sent during testing.
- An unsent draft survived shutdown and reappeared in the same chat route after
  reopening. The verification text was removed afterward.
- The idle interval was restored to five minutes after the shorter test.
- All 37 Python tests and three Node policy tests passed. These include a full
  idle interval after task completion, visible-but-untouched chat, SQLite WAL
  backup, preservation of project files, and wireless-setting restoration.
- All 27 shell scripts passed Bash syntax checks. The APK built and was signed.

Unplugged battery endurance still requires measurement. Other Android devices
and a complete installation on a second, empty phone are not yet tested.

## 1.1.1 follow-up

Closing Termux could reveal the launcher behind it and restart services during
idle cleanup. The launcher now leaves the task stack when backgrounded, while
preserving its chat route and draft storage. File pickers retain their activity.
The exact failure case was tested with Termux in front: idle shutdown returned
to the home screen, left no agent/Linux services, and kept wireless debugging
off. Neither Termux's Wi-Fi lock nor the ADB multicast lock remained.

The installers now bind their source folder explicitly into Debian, so cloning
in Termux's private home works as well as using shared Android storage.
