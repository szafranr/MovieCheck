"""Runner zadań MovieCheck: setup, test, icons, build, release, verify, version, bump."""

import argparse
import ast
import hashlib
import json
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "moviecheck" / "__init__.py"
ENVIRONMENT = ROOT / ".venv-build"


def read_version(path: Path = VERSION_FILE) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets):
            version = ast.literal_eval(node.value)
            if isinstance(version, str) and re.fullmatch(r"0\.1\.(?:0|[1-9]\d*)", version):
                return version
    raise ValueError("Wersja musi mieć format 0.1.x w moviecheck/__init__.py.")


def bump_version(path: Path = VERSION_FILE) -> str:
    current = read_version(path)
    next_version = f"0.1.{int(current.split('.')[2]) + 1}"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'(?m)^__version__\s*=\s*[\'"]0\.1\.\d+[\'"]\s*$', f'__version__ = "{next_version}"', text)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return next_version


def native_target(system: str | None = None) -> str:
    system = system or sys.platform
    if system == "win32":
        return "windows"
    if system == "darwin":
        return "macos"
    raise ValueError("Budowanie wydania wymaga Windows lub macOS.")


def architecture() -> str:
    machine = platform.machine().lower()
    return {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64"}.get(machine, machine)


def run(arguments: list, *, offscreen: bool = False, timeout: int | None = None, cwd: Path | None = None, isolated: bool = False):
    environment = os.environ.copy()
    if isolated:
        for name in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH"):
            environment.pop(name, None)
    if isolated and sys.platform == "win32":
        # Obce biblioteki DLL z PATH mogą zastąpić biblioteki systemowe Qt.
        windows = Path(environment.get("SystemRoot", r"C:\Windows"))
        environment["PATH"] = os.pathsep.join(str(path) for path in
            (windows / "System32", windows, Path(arguments[0]).resolve().parent, Path(sys.base_prefix)))
    if offscreen:
        environment["QT_QPA_PLATFORM"] = "offscreen"
    print("> " + " ".join(str(argument) for argument in arguments), flush=True)
    subprocess.run([str(argument) for argument in arguments], cwd=cwd or ROOT, env=environment, check=True, timeout=timeout)


def environment_python() -> Path:
    return ENVIRONMENT / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def setup_environment() -> Path:
    python = environment_python()
    uv = shutil.which("uv")
    if not python.exists():
        if uv:
            run([uv, "venv", ENVIRONMENT, "--python", sys.executable])
        else:
            venv.EnvBuilder(with_pip=True).create(ENVIRONMENT)
    fingerprint = hashlib.sha256((ROOT / "pyproject.toml").read_bytes() + VERSION_FILE.read_bytes() + sys.version.encode()).hexdigest()
    stamp = ENVIRONMENT / ".moviecheck-build.json"
    try:
        prepared = json.loads(stamp.read_text(encoding="utf-8")).get("fingerprint") == fingerprint
    except (OSError, ValueError):
        prepared = False
    if not prepared:
        if uv:
            run([uv, "pip", "install", "--python", python, "-e", ".[build]"])
        else:
            run([python, "-m", "pip", "install", "-e", ".[build]"])
        stamp.write_text(json.dumps({"fingerprint": fingerprint}), encoding="utf-8")
    return python


def windows_version_info(version: str) -> str:
    numbers = tuple(int(part) for part in version.split(".")) + (0,)
    return f'''VSVersionInfo(
    ffi=FixedFileInfo(filevers={numbers!r}, prodvers={numbers!r}, mask=0x3f, flags=0,
                      OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
    kids=[StringFileInfo([StringTable('040904B0', [
        StringStruct('FileDescription', 'MovieCheck — katalog filmów'),
        StringStruct('FileVersion', {version!r}),
        StringStruct('ProductName', 'MovieCheck'),
        StringStruct('ProductVersion', {version!r}),
        StringStruct('OriginalFilename', 'MovieCheck.exe')
    ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
'''


def ssl_support_files() -> list[tuple[str, str]]:
    # Dystrybucja interpretera może ładować dodatkowy zestaw CA przy tworzeniu SSLContext.
    # Zachowaj ten zasób obok ssl.py również w pakiecie PyInstaller.
    certificate = Path(ssl.__file__).with_name("codex-rejected-cas.pem")
    return [(str(certificate), ".")] if certificate.is_file() else []


def spec_source(target: str, version: str, work: Path) -> str:
    if target not in ("windows", "macos"):
        raise ValueError("Nieznany system wydania.")
    icon = ROOT / "build" / "icons" / ("moviecheck.ico" if target == "windows" else "moviecheck.icns")
    source = f'''a = Analysis(
    [{str(ROOT / 'run.py')!r}], pathex=[{str(ROOT)!r}], binaries=[],
    datas=[({str(ROOT / 'moviecheck' / 'templates')!r}, 'moviecheck/templates'),
           ({str(ROOT / 'moviecheck' / 'assets')!r}, 'moviecheck/assets')] + {ssl_support_files()!r},
    hiddenimports=[], hookspath=[], runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml',
              'PySide6.QtQuick', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets'], noarchive=False)
pyz = PYZ(a.pure)
'''
    if target == "windows":
        source += f'''exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='MovieCheck',
    debug=False, strip=False, upx=False, console=False, icon={str(icon)!r},
    version={str(work / 'windows-version.txt')!r})
'''
    else:
        source += f'''exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='MovieCheck',
    debug=False, strip=False, upx=False, console=False, icon={str(icon)!r})
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='MovieCheck')
app = BUNDLE(coll, name='MovieCheck.app', icon={str(icon)!r},
    bundle_identifier='pl.moviecheck.app', version={version!r},
    info_plist={{'CFBundleShortVersionString': {version!r}, 'CFBundleVersion': {version!r},
                 'CFBundleDisplayName': 'MovieCheck', 'NSHighResolutionCapable': True}})
'''
    return source


def artifact_path(target: str) -> Path:
    return ROOT / "dist" / target / ("MovieCheck.exe" if target == "windows" else "MovieCheck.app")


def smoke_test(target: str, version: str):
    artifact = artifact_path(target)
    executable = artifact if target == "windows" else artifact / "Contents" / "MacOS" / "MovieCheck"
    result_path = ROOT / "build" / "package" / target / "smoke.json"
    result_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="moviecheck-package-") as directory:
        run([executable, "--self-test", result_path], offscreen=True, timeout=120, cwd=Path(directory), isolated=True)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not result.get("ok") or not result.get("frozen") or result.get("version") != version:
        raise RuntimeError(f"Nieudana weryfikacja gotowej aplikacji: {result}")
    print(f"Gotowa aplikacja sprawdzona: {version}", flush=True)


def build_application(python: Path, target: str):
    version = read_version()
    work = ROOT / "build" / "package" / target
    work.mkdir(parents=True, exist_ok=True)
    run([python, "-m", "unittest", "discover", "-s", "tests", "-v"], offscreen=True)
    run([python, ROOT / "build_support" / "create_icons.py"], offscreen=True)
    (work / "windows-version.txt").write_text(windows_version_info(version), encoding="utf-8")
    spec = work / "MovieCheck.spec"
    spec.write_text(spec_source(target, version, work), encoding="utf-8")
    run([python, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", ROOT / "dist" / target, "--workpath", work / "work", spec], isolated=True)
    smoke_test(target, version)


def package_release(target: str):
    version = read_version()
    release = ROOT / "dist" / "releases"
    release.mkdir(parents=True, exist_ok=True)
    name = f"MovieCheck-{version}-{target}-{architecture()}"
    artifact = artifact_path(target)
    if target == "windows":
        result = release / (name + ".exe")
        shutil.copy2(artifact, result)
    else:
        result = release / (name + ".zip")
        run(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", artifact, result])
    with result.open("rb") as source:
        checksum = hashlib.file_digest(source, "sha256").hexdigest()
    (release / (name + ".sha256")).write_text(f"{checksum}  {result.name}\n", encoding="utf-8")
    manifest = {"name": "MovieCheck", "version": version, "target": target, "architecture": architecture(),
                "file": result.name, "bytes": result.stat().st_size, "sha256": checksum}
    (release / (name + ".json")).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wydanie: {result}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=("setup", "test", "icons", "build", "release", "verify", "version", "bump"), nargs="?", default="release")
    parser.add_argument("--target", choices=("auto", "windows", "macos"), default="auto")
    arguments = parser.parse_args()
    try:
        if arguments.task == "version":
            print(read_version())
            return 0
        if arguments.task == "bump":
            print(bump_version())
            return 0
        if arguments.task in ("build", "release", "verify"):
            target = native_target() if arguments.target == "auto" else arguments.target
            if target != native_target():
                raise ValueError(f"Wydanie {target} należy budować na tym systemie, a nie na {native_target()}.")
        else:
            target = None
        if arguments.task == "verify":
            smoke_test(target, read_version())
            return 0
        python = setup_environment()
        if arguments.task == "setup":
            print(f"Środowisko gotowe: {python}")
        elif arguments.task == "test":
            run([python, "-m", "unittest", "discover", "-s", "tests", "-v"], offscreen=True)
        elif arguments.task == "icons":
            run([python, ROOT / "build_support" / "create_icons.py"], offscreen=True)
        else:
            build_application(python, target)
            if arguments.task == "release":
                package_release(target)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Błąd zadania: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
