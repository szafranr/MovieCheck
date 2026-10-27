import ast
import hashlib
import importlib.util
import io
import json
import os
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import build as build_script
from moviecheck import __version__


class BuildTests(unittest.TestCase):
    def test_version_has_one_source_and_three_components(self):
        configuration = tomllib.loads((build_script.ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertNotIn("version", configuration["project"])
        self.assertIn("version", configuration["project"]["dynamic"])
        self.assertEqual(configuration["tool"]["setuptools"]["dynamic"]["version"]["attr"], "moviecheck.__version__")
        self.assertEqual(build_script.read_version(), __version__)
        self.assertRegex(__version__, r"^0\.1\.\d+$")
        self.assertGreaterEqual(int(__version__.split(".")[2]), 10)

    def test_bump_changes_only_patch_and_rejects_another_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "__init__.py"
            path.write_text('__version__ = "0.1.10"\n', encoding="utf-8")
            self.assertEqual(build_script.bump_version(path), "0.1.11")
            self.assertEqual(build_script.read_version(path), "0.1.11")
            path.write_text('__version__ = "0.2.10"\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                build_script.bump_version(path)
            self.assertIn("0.2.10", path.read_text(encoding="utf-8"))

    def test_platform_specs_include_templates_icons_and_metadata(self):
        for target in ("windows", "macos"):
            with self.subTest(target=target):
                source = build_script.spec_source(target, "0.1.10", Path("work"))
                ast.parse(source)
                self.assertIn("moviecheck/templates", source)
                self.assertIn("moviecheck/assets", source)
                self.assertIn("console=False", source)
                if target == "windows":
                    self.assertIn("a.scripts, a.binaries, a.datas", source)
                    self.assertIn("moviecheck.ico", source)
                    self.assertIn("windows-version.txt", source)
                else:
                    self.assertIn("BUNDLE(coll", source)
                    self.assertIn("moviecheck.icns", source)
                    self.assertIn("'CFBundleVersion': '0.1.10'", source)
                    self.assertIn("'CFBundleShortVersionString': '0.1.10'", source)
        resource = build_script.windows_version_info("0.1.10")
        ast.parse(resource)
        self.assertIn("filevers=(0, 1, 10, 0)", resource)
        self.assertIn("'FileVersion', '0.1.10'", resource)

    def test_isolated_windows_run_excludes_foreign_dll_search_paths(self):
        with patch.object(build_script.sys, "platform", "win32"), patch.dict(os.environ, {"PATH": "foreign-dlls", "PYTHONPATH": "foreign-python"}), patch.object(build_script.subprocess, "run") as execute:
            build_script.run(["python.exe", "--version"], isolated=True)
        environment = execute.call_args.kwargs["env"]
        self.assertNotIn("foreign-dlls", environment["PATH"])
        self.assertNotIn("PYTHONPATH", environment)
        self.assertTrue(environment["PATH"].split(os.pathsep)[0].endswith("System32"))

    def test_cross_build_is_rejected_before_environment_changes(self):
        with patch.object(build_script.sys, "argv", ["build.py", "release", "--target", "macos"]), patch.object(build_script.sys, "platform", "win32"), patch.object(build_script, "setup_environment") as setup, redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(build_script.main(), 1)
            setup.assert_not_called()
        self.assertIn("należy budować", stderr.getvalue())

    def test_release_manifest_matches_the_actual_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "dist" / "windows" / "MovieCheck.exe"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"package fixture")
            with patch.object(build_script, "ROOT", root), patch.object(build_script, "read_version", return_value="0.1.10"), patch.object(build_script, "architecture", return_value="x64"):
                result = build_script.package_release("windows")
            self.assertEqual(result.name, "MovieCheck-0.1.10-windows-x64.exe")
            manifest = json.loads(result.with_suffix(".json").read_text(encoding="utf-8"))
            checksum = hashlib.sha256(result.read_bytes()).hexdigest()
            self.assertEqual(manifest["sha256"], checksum)
            self.assertEqual(manifest["bytes"], len(b"package fixture"))
            self.assertIn(checksum, result.with_suffix(".sha256").read_text(encoding="utf-8"))

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Generowanie ikon wymaga dodatku .[build]")
    def test_icon_generation_produces_platform_formats(self):
        from PIL import Image
        from build_support.create_icons import create_icons

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / "moviecheck" / "assets"
            assets.mkdir(parents=True)
            (assets / "moviecheck.svg").write_bytes((build_script.ROOT / "moviecheck" / "assets" / "moviecheck.svg").read_bytes())
            create_icons(root)
            with Image.open(assets / "moviecheck.png") as image:
                self.assertEqual(image.size, (512, 512))
            with Image.open(root / "build" / "icons" / "moviecheck.ico") as image:
                self.assertIn((16, 16), image.ico.sizes())
                self.assertIn((256, 256), image.ico.sizes())
            with Image.open(root / "build" / "icons" / "moviecheck.icns") as image:
                self.assertEqual(image.size, (1024, 1024))
