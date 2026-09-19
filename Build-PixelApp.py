"""Build the small Android wrapper using the installed Android SDK and JDK."""
from pathlib import Path
import os
import subprocess
import zipfile
import sys
import shutil
import re

ROOT = Path(__file__).resolve().parent
SDK = Path(os.environ['LOCALAPPDATA']) / 'Android/Sdk'
JDK = Path(os.environ.get('JAVA_HOME', 'C:/Program Files/Android/Android Studio/jbr'))
TOOLS = SDK / 'build-tools/36.0.0'
ANDROID = SDK / 'platforms/android-37.0/android.jar'
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
         'pixel-desktop-control.py', 'pixel-checkpoint.py', 'pixel-projects.py', 'pixel-project-register.mjs', 'pixel-opencode/AGENTS.md',
         *[str(p.relative_to(ROOT)).replace('\\', '/') for p in (ROOT/'pixel-opencode/tools').glob('*.ts')]]
with zipfile.ZipFile(BUILD / 'assets/runtime.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
    for name in files:
        bundle.writestr(name, (ROOT / name).read_text(encoding='utf-8').replace('\r\n', '\n'))
run(TOOLS / 'aapt2.exe', 'compile', '--dir', APP / 'res', '-o', BUILD / 'resources.zip')
manifest = BUILD / 'AndroidManifest.xml'
manifest.write_text((APP / 'AndroidManifest.xml').read_text().replace('dev.pixelagent.app', APPLICATION_ID))
source = BUILD / 'MainActivity.java'
source.write_text((APP / 'src/dev/pixelagent/app/MainActivity.java').read_text(encoding='utf-8')
                  .replace('package dev.pixelagent.app;', 'package ' + APPLICATION_ID + ';'), encoding='utf-8')
run(TOOLS / 'aapt2.exe', 'link', '-o', BUILD / 'unsigned.apk', '-I', ANDROID,
    '--manifest', manifest, '-A', BUILD / 'assets',
    *(['--debug-mode'] if '--debug' in sys.argv else []), BUILD / 'resources.zip')
run(JDK / 'bin/javac.exe', '--release', '8', '-encoding', 'UTF-8', '-classpath', ANDROID,
    '-d', BUILD / 'classes', source)
run(JDK / 'bin/java.exe', '-cp', TOOLS / 'lib/d8.jar', 'com.android.tools.r8.D8',
    '--lib', ANDROID, '--min-api', '28', '--output', BUILD / 'dex', *BUILD.glob('classes/**/*.class'))
with zipfile.ZipFile(BUILD / 'unsigned.apk', 'a') as apk:
    apk.write(BUILD / 'dex/classes.dex', 'classes.dex')
run(TOOLS / 'zipalign.exe', '-f', '4', BUILD / 'unsigned.apk', BUILD / 'aligned.apk')
# Keep this local key for future updates; it is deliberately outside tracked files.
key = APP / '.signing/pixel-agent.jks'
key.parent.mkdir(parents=True, exist_ok=True)
legacy_key = ROOT / '.downloads/pixel-app-signing.jks'
if not key.exists() and legacy_key.exists():
    shutil.copy2(legacy_key, key)
if not key.exists():
    run(JDK / 'bin/keytool.exe', '-genkeypair', '-keystore', key, '-storepass', 'android',
        '-keypass', 'android', '-alias', 'pixel-agent', '-keyalg', 'RSA', '-keysize', '2048',
        '-validity', '10000', '-dname', 'CN=Pixel Agent Local')
output = ROOT / '.downloads/Pixel-Agent.apk'
run(JDK / 'bin/java.exe', '-jar', TOOLS / 'lib/apksigner.jar', 'sign', '--ks', key,
    '--ks-pass', 'pass:android', '--out', output, BUILD / 'aligned.apk')
run(JDK / 'bin/java.exe', '-jar', TOOLS / 'lib/apksigner.jar', 'verify', output)
print(output)
