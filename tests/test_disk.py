import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qemu_lle_workbench.disk import DiskImageError, create_disk_image


class DiskImageTests(unittest.TestCase):
    def test_create_disk_invokes_qemu_img_without_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "system.qcow2"

            def fake_run(command, **kwargs):
                self.assertEqual(command, ["/fake/qemu-img", "create", "-f", "qcow2", str(target), "65536M"])
                self.assertNotIn("shell", kwargs)
                target.write_bytes(b"image")
                return subprocess.CompletedProcess(command, 0, "Formatting...", "")

            with patch("qemu_lle_workbench.disk.find_qemu_img", return_value="/fake/qemu-img"), patch(
                "qemu_lle_workbench.disk.subprocess.run", side_effect=fake_run
            ):
                result = create_disk_image(target, "qcow2", 65536)
            self.assertEqual(result.path, target.resolve())
            self.assertEqual(result.format, "qcow2")

    def test_refuses_to_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "existing.raw"
            target.write_bytes(b"keep")
            with self.assertRaisesRegex(DiskImageError, "уже существует"):
                create_disk_image(target, "raw", 8)
            self.assertEqual(target.read_bytes(), b"keep")

    def test_rejects_unknown_format_and_invalid_size(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "disk.bad"
            with self.assertRaises(DiskImageError):
                create_disk_image(target, "unknown", 8)
            with self.assertRaises(DiskImageError):
                create_disk_image(target, "qcow2", 0)


if __name__ == "__main__":
    unittest.main()
