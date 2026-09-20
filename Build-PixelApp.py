"""Build on Windows or Debian ARM64 using Android SDK jars and native tools."""
from pathlib import Path
import os
import subprocess
import zipfile
import sys
import shutil
import re

ROOT = Path(__file__).resolve().parent
WINDOWS = os.name == 'nt'
default_sdk = Path(os.environ['LOCALAPPDATA']) / 'Android/Sdk' if WINDOWS else Path.home() / '.cache/pixel-agent/android-sdk'
SDK = Path(os.environ.get('ANDROID_HOME', str(default_sdk)))
JDK = Path(os.environ.get('JAVA_HOME', 'C:/Program Files/Android/Android Studio/jbr' if WINDOWS else '/usr/lib/jvm/default-java'))
TOOLS = SDK / 'build-tools/36.0.0'
platform = 'android-37.0' if WINDOWS else 'android-34'
ANDROID = Path(os.environ.get('PIXEL_ANDROID_JAR', str(SDK / 'platforms' / platform / 'android.jar')))
D8 = Path(os.environ.get('PIXEL_D8_JAR', str(TOOLS / 'lib/d8.jar')))
EXE = '.exe' if WINDOWS else ''
AAPT = TOOLS / 'aapt2.exe' if WINDOWS else shutil.which('aapt2')
ZIPALIGN = TOOLS / 'zipalign.exe' if WINDOWS else shutil.which('zipalign')
if not AAPT or not ZIPALIGN or not ANDROID.is_file() or not D8.is_file():
    raise RuntimeError('Android build tools are missing. See docs/MAINTENANCE.md.')
BUILD = ROOT / '.downloads/pixel-app-build'
APP = ROOT / 'pixel-app'
APPLICATION_ID = os.environ.get('PIXEL_APPLICATION_ID', 'dev.pixelagent.app')
if not re.fullmatch(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+', APPLICATION_ID):
    raise ValueError('Invalid Android application ID')
for directory in ('classes', 'dex', 'assets'):
    target=(BUILD/directory).resolve()
    if not target.is_relative_to(BUILD.resolve()):raise RuntimeError('Build path left the build directory')
    if target.exists():shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


files = ['apply-pixel-power.sh', 'pixel-app-control.py', 'pixel-t3-runtime.py',
         'pixel-t3-mobile.sh', 'pixel-t3-server.sh', 'pixel-t3-watch.mjs',
         'pixel-phone-bridge.py', 'pixel-phone-bridge-start.sh', 'pixel-desktop-start.sh',
         'pixel-desktop-control.py', 'pixel-desktop-activity.py', 'pixel-desktop-navigation.py', 'pixel-desktop-session.sh',
         'pixel-checkpoint.py', 'pixel-projects.py', 'pixel-project-register.mjs', 'pixel-opencode/AGENTS.md',
         *[str(p.relative_to(ROOT)).replace('\\', '/') for p in (ROOT/'pixel-opencode/tools').glob('*.ts')]]
with zipfile.ZipFile(BUILD / 'assets/runtime.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
    for name in files:
        bundle.writestr(name, (ROOT / name).read_text(encoding='utf-8').replace('\r\n', '\n'))
run(AAPT, 'compile', '--dir', APP / 'res', '-o', BUILD / 'resources.zip')
manifest = BUILD / 'AndroidManifest.xml'
manifest.write_text((APP / 'AndroidManifest.xml').read_text().replace('dev.pixelagent.app', APPLICATION_ID))
source = BUILD / 'MainActivity.java'
source.write_text((APP / 'src/dev/pixelagent/app/MainActivity.java').read_text(encoding='utf-8')
                  .replace('package dev.pixelagent.app;', 'package ' + APPLICATION_ID + ';'), encoding='utf-8')
run(AAPT, 'link', '-o', BUILD / 'unsigned.apk', '-I', ANDROID,
    '--manifest', manifest, '-A', BUILD / 'assets',
    *(['--debug-mode'] if '--debug' in sys.argv else []), BUILD / 'resources.zip')
run(JDK / ('bin/javac' + EXE), '--release', '8', '-encoding', 'UTF-8', '-classpath', ANDROID,
    '-d', BUILD / 'classes', source)
run(JDK / ('bin/java' + EXE), '-cp', D8, 'com.android.tools.r8.D8',
    '--lib', ANDROID, '--min-api', '28', '--output', BUILD / 'dex', *BUILD.glob('classes/**/*.class'))
with zipfile.ZipFile(BUILD / 'unsigned.apk', 'a') as apk:
    apk.write(BUILD / 'dex/classes.dex', 'classes.dex')
run(ZIPALIGN, '-f', '4', BUILD / 'unsigned.apk', BUILD / 'aligned.apk')
# Keep this local key for future updates; it is deliberately outside tracked files.
key = Path(os.environ.get('PIXEL_SIGNING_KEY', str(APP / '.signing/pixel-agent.jks')))
key.parent.mkdir(parents=True, exist_ok=True)
legacy_key = ROOT / '.downloads/pixel-app-signing.jks'
if not key.exists() and legacy_key.exists():
    shutil.copy2(legacy_key, key)
if not key.exists():
    run(JDK / ('bin/keytool' + EXE), '-genkeypair', '-keystore', key, '-storepass', 'android',
        '-keypass', 'android', '-alias', 'pixel-agent', '-keyalg', 'RSA', '-keysize', '2048',
        '-validity', '10000', '-dname', 'CN=Pixel Agent Local')
output = ROOT / '.downloads/Pixel-Agent.apk'
signer = [JDK / 'bin/java.exe', '-jar', TOOLS / 'lib/apksigner.jar'] if WINDOWS else ['apksigner']
run(*signer, 'sign', '--ks', key,
    '--ks-pass', 'pass:android', '--out', output, BUILD / 'aligned.apk')
run(*signer, 'verify', output)
print(output)
