import os
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication, QMessageBox

from qemu_lle_workbench.main_window import MainWindow
from qemu_lle_workbench.project import default_project


class SandboxUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()

    def tearDown(self):
        self.window.sandbox_lock_timer.stop()
        self.window.dirty = False
        self.window.close()

    def test_required_sandbox_forces_security_and_command_option(self):
        self.window.security_require_sandbox.setChecked(True)
        self.assertTrue(self.window.security_enabled.isChecked())
        self.assertTrue(self.window.security_sandbox.isChecked())
        project = self.window.collect_project()
        self.assertTrue(project["vm"]["security"]["sandboxRequired"])

    def test_ten_minute_lock_prevents_programmatic_uncheck(self):
        before = time.time()
        self.window.security_lock_sandbox.setChecked(True)
        self.assertGreaterEqual(self.window._sandbox_lock_until, before + 599)
        self.assertFalse(self.window.security_sandbox.isEnabled())
        with patch("qemu_lle_workbench.main_window.QMessageBox.warning") as warning:
            self.window.security_sandbox.setChecked(False)
        self.assertTrue(self.window.security_sandbox.isChecked())
        warning.assert_called_once()

    def test_future_lock_is_restored_from_project(self):
        project = default_project()
        project["vm"]["security"]["sandboxLockUntil"] = time.time() + 300
        self.window.set_project(project)
        self.assertTrue(self.window.security_lock_sandbox.isChecked())
        self.assertTrue(self.window.security_require_sandbox.isChecked())
        self.assertTrue(self.window.security_sandbox.isChecked())
        self.assertFalse(self.window.security_enabled.isEnabled())

    def test_confirmed_removal_requests_stop_for_running_sandboxed_vm(self):
        self.window.security_sandbox.setChecked(True)
        self.window._running_with_sandbox = True
        with (
            patch.object(self.window.process, "state", return_value=QProcess.Running),
            patch.object(self.window, "stop_qemu") as stop_qemu,
            patch(
                "qemu_lle_workbench.main_window.QMessageBox.question",
                return_value=QMessageBox.Yes,
            ),
        ):
            self.window.security_sandbox.setChecked(False)
        self.assertFalse(self.window.security_sandbox.isChecked())
        stop_qemu.assert_called_once()

    def test_specific_cpu_selection_is_saved_and_architecture_aware(self):
        self.window.arch_combo.setCurrentText("aarch64")
        self.assertGreater(self.window.cpu_model.findText("cortex-a72"), -1)
        self.window.cpu_model.setCurrentText("cortex-a72")
        project = self.window.collect_project()
        self.assertEqual(project["vm"]["cpu"]["model"], "cortex-a72")

    def test_arm_video_and_output_only_audio_choices_are_visible_and_saved(self):
        self.assertGreater(self.window.video_model.findText("virtio-gpu-pci"), -1)
        self.assertGreater(self.window.video_model.findText("ramfb"), -1)
        self.window.video_model.setCurrentText("virtio-gpu-pci")
        self.window.sound_model.setCurrentText("intel-hda")
        self.window.sound_codec.setCurrentText("hda-output")
        project = self.window.collect_project()
        self.assertEqual(project["vm"]["video"]["model"], "virtio-gpu-pci")
        self.assertEqual(project["vm"]["sound"]["codec"], "hda-output")


if __name__ == "__main__":
    unittest.main()
