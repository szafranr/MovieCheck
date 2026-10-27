import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL = ("/bin/sh" if Path("/bin/sh").exists() else
         str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"))

FAKE_PYTHON = """#!/bin/sh
case "$*" in
  *sys.version_info*) exit "${PYTHON_VERSION_RESULT:-0}" ;;
  *'import PySide6'*) test -f installed ;;
  '-m venv .venv') mkdir -p .venv/bin; cp "$0" .venv/bin/python; chmod +x .venv/bin/python ;;
  '-m pip --version') exit 0 ;;
  '-m pip install -e .')
    echo install >> calls
    if [ "${FAIL_INSTALL:-0}" = 1 ]; then exit 7; fi
    touch installed ;;
  '-m moviecheck'*) printf '%s\\n' "$@" > launched ;;
  *) exit 9 ;;
esac
"""


@unittest.skipUnless(Path(SHELL).is_file(), "Test launchera wymaga powłoki POSIX")
class MacLauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="moviecheck launcher ")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        shutil.copyfile(ROOT / "start_macos.command", self.root / "start_macos.command")
        (self.root / "moviecheck").mkdir()
        (self.root / "moviecheck/__init__.py").write_text('__version__ = "0.1.12"', encoding="utf-8")
        (self.root / "pyproject.toml").write_text("fixture", encoding="utf-8")
        (self.root / "fakebin").mkdir()
        python = self.root / "fakebin/python3"
        python.write_text(FAKE_PYTHON, encoding="utf-8", newline="\n")
        python.chmod(0o755)

    def launch(self, **environment):
        return subprocess.run([SHELL, "-c", 'export PATH="$PWD/fakebin:$PATH"; exec sh ./start_macos.command "argument with spaces"'], cwd=self.root,
                              env={**os.environ, **environment}, capture_output=True, text=True, encoding="utf-8", timeout=20)

    def test_clean_clone_installs_once_and_preserves_arguments(self):
        first = self.launch()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue((self.root / ".venv/bin/python").is_file())
        self.assertIn("argument with spaces", (self.root / "launched").read_text())
        second = self.launch()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((self.root / "calls").read_text().splitlines(), ["install"])

    def test_configuration_change_refreshes_installation(self):
        self.assertEqual(self.launch().returncode, 0)
        (self.root / "pyproject.toml").write_text("changed fixture", encoding="utf-8")
        self.assertEqual(self.launch().returncode, 0)
        self.assertEqual((self.root / "calls").read_text().splitlines(), ["install", "install"])

    def test_installation_failure_stops_launch_and_can_be_retried(self):
        self.assertNotEqual(self.launch(FAIL_INSTALL="1").returncode, 0)
        self.assertFalse((self.root / "launched").exists())
        self.assertFalse((self.root / ".venv/.moviecheck-install.stamp").exists())
        self.assertEqual(self.launch().returncode, 0)
        self.assertTrue((self.root / "launched").exists())

    def test_old_python_does_not_create_environment(self):
        result = self.launch(PYTHON_VERSION_RESULT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("3.11", result.stderr)
        self.assertFalse((self.root / ".venv").exists())

    def test_foreign_environment_is_preserved(self):
        scripts = self.root / ".venv/Scripts"
        scripts.mkdir(parents=True)
        marker = scripts / "python.exe"
        marker.write_bytes(b"foreign environment fixture")
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("macOS", result.stderr)
        self.assertEqual(marker.read_bytes(), b"foreign environment fixture")
        self.assertFalse((self.root / "launched").exists())
