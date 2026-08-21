import json
import os
import tempfile
import unittest
from pathlib import Path

from qemu_lle_workbench.project import ProjectError, default_project, load_project, normalize_project, save_project


class ProjectTests(unittest.TestCase):
    def test_defaults_are_normalized(self):
        project = normalize_project({"format": "qemu-lle-project", "version": 1, "vm": {}, "lle": {}})
        self.assertEqual(project["vm"]["architecture"], "x86_64")
        self.assertIn("timingClockOptions", project["lle"])
        self.assertEqual(project["vm"]["security"]["profile"], "balanced")
        self.assertFalse(project["vm"]["security"]["sandboxRequired"])
        self.assertEqual(project["vm"]["security"]["sandboxLockUntil"], 0)
        self.assertFalse(project["vm"]["tracing"]["enabled"])

    def test_round_trip(self):
        project = default_project()
        project["name"] = "Тестовая ВМ"
        with tempfile.TemporaryDirectory() as directory:
            path = save_project(Path(directory) / "machine", project)
            self.assertEqual(path.suffix, ".lleproject")
            self.assertEqual(load_project(path)["name"], "Тестовая ВМ")

    def test_rejects_future_version(self):
        with self.assertRaises(ProjectError):
            normalize_project({"format": "qemu-lle-project", "version": 999, "vm": {}, "lle": {}})

    def test_rejects_invalid_sandbox_lock_timestamp(self):
        project = default_project()
        project["vm"]["security"]["sandboxLockUntil"] = -1
        with self.assertRaises(ProjectError):
            normalize_project(project)

    def test_example_is_valid(self):
        example = Path(__file__).parents[1] / "examples" / "minimal-x86_64.lleproject"
        project = load_project(example)
        self.assertTrue(project["lle"]["enabled"])
        self.assertEqual(json.loads(example.read_text(encoding="utf-8"))["version"], 1)

    def test_all_template_files_are_valid(self):
        directory = Path(__file__).parents[1] / "examples" / "templates"
        files = sorted(directory.glob("*.lleproject"))
        self.assertGreaterEqual(len(files), 5)
        for path in files:
            with self.subTest(path=path.name):
                load_project(path)

    def test_macos_launchers_are_portable_executable_scripts(self):
        root = Path(__file__).parents[1]
        for name in ("Запустить.command", "run_macos.command"):
            with self.subTest(name=name):
                path = root / name
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("#!/bin/zsh"))
                self.assertNotIn("/Users/daniiloreshin", text)
                self.assertTrue(os.access(path, os.X_OK))
        launcher = (root / "run_macos.command").read_text(encoding="utf-8")
        self.assertIn("python_is_compatible", launcher)
        self.assertIn("CHILLEDQEUM_PYTHON", launcher)
        self.assertIn('pip install --upgrade "pip>=23.1"', launcher)


if __name__ == "__main__":
    unittest.main()
