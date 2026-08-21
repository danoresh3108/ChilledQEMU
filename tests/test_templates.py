import unittest

from qemu_lle_workbench.project import validate_project
from qemu_lle_workbench.templates import create_template, template_names


class TemplateTests(unittest.TestCase):
    def test_all_templates_are_valid_projects(self):
        names = template_names()
        self.assertGreaterEqual(len(names), 5)
        for key, _label in names:
            with self.subTest(key=key):
                validate_project(create_template(key))

    def test_secure_boot_template_enables_smm(self):
        firmware = create_template("x86_64-secure-boot")["vm"]["firmware"]
        self.assertTrue(firmware["secureBoot"])
        self.assertTrue(firmware["smm"])

    def test_aarch64_template_selects_virt_machine(self):
        vm = create_template("aarch64-uefi")["vm"]
        self.assertEqual(vm["architecture"], "aarch64")
        self.assertEqual(vm["machine"], "virt")

    def test_winpe_arm64_template_avoids_input_audio_and_x86_bios(self):
        vm = create_template("aarch64-winpe")["vm"]
        self.assertEqual(vm["architecture"], "aarch64")
        self.assertEqual(vm["machine"], "virt")
        self.assertEqual(vm["video"]["model"], "ramfb")
        self.assertEqual(vm["sound"]["model"], "none")
        self.assertEqual(vm["firmware"]["mode"], "uefi")

    def test_isolated_lab_uses_strict_security(self):
        vm = create_template("isolated-lab")["vm"]
        self.assertTrue(vm["security"]["enabled"])
        self.assertEqual(vm["security"]["profile"], "strict")
        self.assertEqual(vm["network"]["mode"], "none")


if __name__ == "__main__":
    unittest.main()
