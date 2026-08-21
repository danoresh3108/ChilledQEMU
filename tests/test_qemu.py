import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qemu_lle_workbench.project import ProjectContext, default_project
from qemu_lle_workbench.qemu import (
    QemuCapabilities,
    QemuInspector,
    build_command,
    command_text,
    find_firmware,
    machine_presets,
    recommended_machine,
    tracing_log_path,
    validate_against_qemu,
    validate_firmware,
    validate_security,
    validate_tracing,
)


class CommandTests(unittest.TestCase):
    def test_builds_common_and_lle_arguments(self):
        project = default_project()
        project["name"] = "VM with spaces"
        project["vm"]["storage"]["disks"] = [
            {"path": "disk.qcow2", "format": "qcow2", "interface": "virtio", "readOnly": False}
        ]
        project["lle"]["enabled"] = True
        project["lle"]["deviceModels"] = [
            {"name": "debug", "qemuDevice": "isa-debugcon", "properties": {"iobase": "0x402"}}
        ]
        project["lle"]["timingClockOptions"]["rtc"] = "base=utc"
        command = build_command(project, ProjectContext(Path("/tmp/project/test.lleproject")))
        self.assertEqual(command[0], "qemu-system-x86_64")
        self.assertIn("file=/tmp/project/disk.qcow2,format=qcow2,if=virtio", command)
        self.assertIn("isa-debugcon,iobase=0x402", command)
        self.assertIn("base=utc", command)
        self.assertIn("'VM with spaces'", command_text(command))

    def test_nvme_uses_backend_and_device(self):
        project = default_project()
        project["vm"]["storage"]["disks"] = [
            {"path": "disk.raw", "format": "raw", "interface": "nvme"}
        ]
        command = build_command(project)
        self.assertIn("file=" + str(Path.cwd() / "disk.raw") + ",format=raw,if=none,id=drive0", command)
        self.assertIn("nvme,drive=drive0,serial=LLE0000", command)

    def test_specific_cpu_model_is_passed_to_qemu(self):
        project = default_project()
        project["vm"]["cpu"]["model"] = "cortex-a72"
        command = build_command(project)
        self.assertEqual(command[command.index("-cpu") + 1], "cortex-a72")

    def test_builds_complete_uefi_pflash_configuration(self):
        project = default_project()
        project["vm"]["firmware"].update(
            {
                "mode": "uefi",
                "uefiCode": "OVMF_CODE.fd",
                "uefiVars": "OVMF_VARS.fd",
                "pflashFormat": "raw",
                "uefiCodeReadOnly": True,
                "uefiVarsReadOnly": False,
                "smm": True,
            }
        )
        command = build_command(project, ProjectContext(Path("/tmp/test.lleproject")))
        self.assertIn("q35,accel=hvf,smm=on", command)
        self.assertIn("if=pflash,unit=0,format=raw,readonly=on,file=/tmp/OVMF_CODE.fd", command)
        self.assertIn("if=pflash,unit=1,format=raw,file=/tmp/OVMF_VARS.fd", command)

    def test_builds_external_bios(self):
        project = default_project()
        project["vm"]["firmware"].update({"mode": "bios", "bios": "bios.bin"})
        command = build_command(project, ProjectContext(Path("/tmp/test.lleproject")))
        self.assertEqual(command[command.index("-bios") + 1], "/tmp/bios.bin")

    def test_aarch64_virtio_video_alias_uses_supported_pci_device(self):
        project = default_project()
        project["vm"].update({"architecture": "aarch64", "machine": "virt"})
        project["vm"]["video"]["model"] = "virtio"
        command = build_command(project)
        self.assertIn("virtio-gpu-pci", command)
        self.assertNotIn("virtio-vga", command)

    def test_explicit_video_device_is_passed_through(self):
        project = default_project()
        project["vm"]["video"]["model"] = "virtio-gpu-pci"
        command = build_command(project)
        self.assertEqual(command[command.index("-device") + 1], "virtio-net-pci,netdev=net0")
        self.assertIn("virtio-gpu-pci", command)

    def test_coreaudio_hda_defaults_to_output_only_codec(self):
        project = default_project()
        project["vm"]["sound"].update(
            {"model": "intel-hda", "codec": "hda-output", "backend": "coreaudio"}
        )
        command = build_command(project)
        self.assertIn("hda-output,audiodev=audio0", command)
        self.assertNotIn("hda-duplex,audiodev=audio0", command)

    def test_balanced_security_profile_disables_user_config_and_monitor(self):
        project = default_project()
        project["vm"]["security"].update({"enabled": True, "profile": "balanced"})
        command = build_command(project)
        self.assertIn("-no-user-config", command)
        self.assertEqual(command[command.index("-monitor") + 1], "none")
        self.assertNotIn("-nodefaults", command)
        self.assertNotIn("-sandbox", command)

    def test_sandbox_can_be_added_to_balanced_profile(self):
        project = default_project()
        project["vm"]["security"].update(
            {"enabled": True, "profile": "balanced", "sandbox": True}
        )
        self.assertIn("-sandbox", build_command(project))

    def test_strict_security_profile_isolates_network_and_disk_writes(self):
        project = default_project()
        project["vm"]["storage"]["disks"] = [
            {"path": "disk.qcow2", "format": "qcow2", "interface": "virtio"}
        ]
        project["vm"]["security"].update({"enabled": True, "profile": "strict"})
        command = build_command(project)
        self.assertIn("-nodefaults", command)
        self.assertIn("-serial", command)
        self.assertIn("-nic", command)
        self.assertEqual(command[command.index("-nic") + 1], "none")
        drive = command[command.index("-drive") + 1]
        self.assertIn("snapshot=on", drive)

    def test_required_sandbox_overrides_disabled_profile_and_emits_hardened_flags(self):
        project = default_project()
        project["vm"]["security"].update(
            {"enabled": False, "profile": "balanced", "sandbox": False, "sandboxRequired": True}
        )
        command = build_command(project)
        self.assertIn("-sandbox", command)
        value = command[command.index("-sandbox") + 1]
        self.assertIn("obsolete=deny", value)
        self.assertIn("elevateprivileges=deny", value)
        self.assertIn("spawn=deny", value)
        self.assertIn("resourcecontrol=deny", value)

    def test_translation_trace_forces_tcg_and_writes_host_assembly_log(self):
        project = default_project()
        project["name"] = "Trace VM"
        project["vm"]["tracing"].update(
            {"enabled": True, "preset": "translation", "forceTcg": True}
        )
        context = ProjectContext(Path("/tmp/project.lleproject"))
        command = build_command(project, context)
        machine = command[command.index("-machine") + 1]
        self.assertIn("accel=tcg", machine)
        self.assertEqual(command[command.index("-cpu") + 1], "max")
        log_items = command[command.index("-d") + 1]
        self.assertIn("in_asm", log_items)
        self.assertIn("out_asm", log_items)
        self.assertIn("op_opt", log_items)
        self.assertEqual(command[command.index("-D") + 1], "/tmp/Trace-VM.qemu-trace.log")

    def test_tracing_is_disabled_by_default(self):
        command = build_command(default_project())
        self.assertNotIn("-d", command)
        self.assertNotIn("-D", command)

    def test_serial_capture_overrides_security_serial_disable(self):
        project = default_project()
        project["vm"]["security"].update({"enabled": True, "profile": "strict"})
        project["vm"]["tracing"].update(
            {"enabled": True, "preset": "diagnostics", "captureSerial": True}
        )
        command = build_command(project)
        serial_values = [command[index + 1] for index, value in enumerate(command[:-1]) if value == "-serial"]
        self.assertEqual(serial_values, ["stdio"])


class InspectorTests(unittest.TestCase):
    def test_parsers_accept_typical_qemu_help(self):
        machines = QemuInspector._parse_machines("Supported machines are:\nq35 Standard PC\nvirt Generic")
        devices = QemuInspector._parse_devices('Controller/Bridge/Hub devices:\nname "qemu-xhci", bus PCI\nname "isa-debugcon"')
        cpu_models = QemuInspector._parse_cpu_models(
            "Available CPUs:\n  host\n  cortex-a72\n  neoverse-n1\n"
        )
        self.assertEqual(machines, {"q35", "virt"})
        self.assertEqual(devices, {"qemu-xhci", "isa-debugcon"})
        self.assertEqual(cpu_models, {"host", "cortex-a72", "neoverse-n1"})

    def test_device_category_and_backend_parsers(self):
        output = (
            'Display devices:\nname "virtio-gpu-pci", bus PCI\n'
            'Sound devices:\nname "hda-output", bus HDA\n'
        )
        categories = QemuInspector._parse_device_categories(output)
        self.assertEqual(categories["display devices"], {"virtio-gpu-pci"})
        self.assertEqual(categories["sound devices"], {"hda-output"})
        self.assertEqual(
            QemuInspector._parse_backends("Available audio drivers:\nnone\ncoreaudio\n"),
            {"none", "coreaudio"},
        )

    def test_cpu_parser_accepts_older_architecture_prefixed_format(self):
        cpu_models = QemuInspector._parse_cpu_models(
            "Available CPUs:\n  x86 Broadwell Intel Core Processor\n  x86 EPYC AMD EPYC\n"
            "Recognized CPUID flags:\n  fpu vme de\n"
        )
        self.assertEqual(cpu_models, {"Broadwell", "EPYC"})

    def test_validation_reports_missing_lle_requirements(self):
        project = default_project()
        project["lle"].update(
            {
                "enabled": True,
                "requiredQemuDevices": ["missing-device"],
                "requiredModules": ["missing-module"],
                "firmware": {"roms": [{"path": "missing.rom", "required": True}]},
            }
        )
        capabilities = QemuCapabilities(
            binary="qemu-system-x86_64",
            resolved_binary="/usr/bin/qemu-system-x86_64",
            version="QEMU emulator version 9.0",
            machines={"q35"},
            devices={"virtio-net-pci"},
        )
        with tempfile.TemporaryDirectory() as directory:
            issues = validate_against_qemu(project, capabilities, ProjectContext(Path(directory) / "test.lleproject"))
        warnings = [issue.message for issue in issues if issue.severity == "warning"]
        self.assertTrue(any("missing-device" in message for message in warnings))
        self.assertTrue(any("missing-module" in message for message in warnings))
        self.assertTrue(any("missing.rom" in message for message in warnings))

    def test_arm64_recommends_virt_and_rejects_pc(self):
        project = default_project()
        project["vm"].update({"architecture": "aarch64", "machine": "pc"})
        capabilities = QemuCapabilities(
            binary="qemu-system-aarch64",
            resolved_binary="/opt/homebrew/bin/qemu-system-aarch64",
            version="QEMU emulator version 11.0",
            machines={"virt"},
        )
        issues = validate_against_qemu(project, capabilities)
        self.assertEqual(recommended_machine("aarch64"), "virt")
        self.assertEqual(machine_presets("aarch64"), ["virt"])
        self.assertTrue(
            any(issue.severity == "error" and "выберите 'virt'" in issue.message for issue in issues)
        )

    def test_validation_rejects_binary_architecture_mismatch(self):
        project = default_project()
        project["vm"].update({"architecture": "aarch64", "machine": "virt"})
        capabilities = QemuCapabilities(
            binary="qemu-system-x86_64",
            resolved_binary="/opt/homebrew/bin/qemu-system-x86_64",
            machines={"virt"},
        )
        issues = validate_against_qemu(project, capabilities)
        self.assertTrue(any(issue.severity == "error" and issue.category == "Architecture" for issue in issues))

    def test_validation_rejects_cpu_model_missing_from_selected_qemu(self):
        project = default_project()
        project["vm"]["cpu"]["model"] = "not-a-real-cpu"
        capabilities = QemuCapabilities(
            binary="qemu-system-x86_64",
            resolved_binary="/opt/homebrew/bin/qemu-system-x86_64",
            machines={"q35"},
            cpu_models={"host", "max", "Broadwell"},
        )
        issues = validate_against_qemu(project, capabilities)
        self.assertTrue(any(issue.severity == "error" and issue.category == "CPU" for issue in issues))

    def test_firmware_discovery_prefers_arch_and_secure_boot(self):
        capabilities = QemuCapabilities(
            binary="qemu-system-x86_64",
            firmware_files=[
                Path("/qemu/bios.bin"),
                Path("/qemu/edk2-i386-vars.fd"),
                Path("/qemu/edk2-x86_64-code.fd"),
                Path("/qemu/edk2-x86_64-secure-code.fd"),
                Path("/qemu/edk2-aarch64-code.fd"),
            ],
        )
        bios, code, vars_template = find_firmware(capabilities, "x86_64", secure_boot=True)
        self.assertEqual(bios, Path("/qemu/bios.bin"))
        self.assertEqual(code, Path("/qemu/edk2-x86_64-secure-code.fd"))
        self.assertEqual(vars_template, Path("/qemu/edk2-i386-vars.fd"))

    def test_aarch64_firmware_discovery_never_returns_x86_bios(self):
        capabilities = QemuCapabilities(
            binary="qemu-system-aarch64",
            firmware_files=[
                Path("/qemu/bios.bin"),
                Path("/qemu/edk2-i386-code.fd"),
                Path("/qemu/edk2-aarch64-code.fd"),
                Path("/qemu/edk2-arm-vars.fd"),
            ],
        )
        bios, code, vars_template = find_firmware(capabilities, "aarch64")
        self.assertIsNone(bios)
        self.assertEqual(code, Path("/qemu/edk2-aarch64-code.fd"))
        self.assertEqual(vars_template, Path("/qemu/edk2-arm-vars.fd"))

    def test_uefi_validation_requires_code_and_separate_nvram(self):
        project = default_project()
        project["vm"]["firmware"]["mode"] = "uefi"
        issues = validate_firmware(project)
        self.assertTrue(any(issue.severity == "error" and "UEFI code" in issue.message for issue in issues))
        with tempfile.TemporaryDirectory() as directory:
            firmware = Path(directory) / "firmware.fd"
            firmware.write_bytes(b"firmware")
            project["vm"]["firmware"].update({"uefiCode": str(firmware), "uefiVars": str(firmware)})
            issues = validate_firmware(project)
        self.assertTrue(any(issue.severity == "error" and "один файл" in issue.message for issue in issues))

    def test_x86_bios_can_use_qemu_builtin_image(self):
        project = default_project()
        project["vm"]["firmware"].update({"mode": "bios", "bios": ""})
        issues = validate_firmware(project)
        self.assertFalse(any(issue.severity == "error" for issue in issues))

    def test_aarch64_rejects_qemu_x86_bios_bin(self):
        project = default_project()
        project["vm"].update({"architecture": "aarch64", "machine": "virt"})
        with tempfile.TemporaryDirectory() as directory:
            bios = Path(directory) / "bios.bin"
            bios.write_bytes(b"x86 bios")
            project["vm"]["firmware"].update({"mode": "bios", "bios": str(bios)})
            issues = validate_firmware(project)
        self.assertTrue(
            any(issue.severity == "error" and "x86 SeaBIOS" in issue.message for issue in issues)
        )

    def test_coreaudio_duplex_codec_is_rejected_before_launch(self):
        project = default_project()
        project["vm"]["sound"].update(
            {"model": "intel-hda", "codec": "hda-duplex", "backend": "coreaudio"}
        )
        capabilities = QemuCapabilities(
            binary="qemu-system-x86_64",
            resolved_binary="/usr/bin/qemu-system-x86_64",
            devices={"virtio-net-pci", "virtio-vga", "intel-hda", "hda-duplex", "qemu-xhci", "usb-tablet"},
        )
        issues = validate_against_qemu(project, capabilities)
        self.assertTrue(any(issue.severity == "error" and "adc" in issue.message for issue in issues))

    def test_selected_missing_video_device_is_rejected_without_lle(self):
        project = default_project()
        project["vm"]["network"]["mode"] = "none"
        project["vm"]["usb"]["enabled"] = False
        project["vm"]["video"]["model"] = "virtio-gpu-pci"
        capabilities = QemuCapabilities(
            binary="qemu-system-x86_64",
            resolved_binary="/usr/bin/qemu-system-x86_64",
            devices={"VGA"},
        )
        issues = validate_against_qemu(project, capabilities)
        self.assertTrue(
            any(issue.severity == "error" and "virtio-gpu-pci" in issue.message for issue in issues)
        )

    def test_security_validation_rejects_unsupported_sandbox(self):
        project = default_project()
        project["vm"]["security"].update(
            {"enabled": True, "profile": "custom", "sandbox": True}
        )
        capabilities = QemuCapabilities(
            binary="qemu-system-aarch64",
            resolved_binary="/opt/homebrew/bin/qemu-system-aarch64",
            sandbox_supported=False,
        )
        issues = validate_security(project, capabilities)
        self.assertTrue(any(issue.severity == "error" and "sandbox" in issue.message for issue in issues))

    def test_required_sandbox_reports_launch_block_when_seccomp_is_unavailable(self):
        project = default_project()
        project["vm"]["security"].update(
            {"enabled": False, "sandbox": False, "sandboxRequired": True}
        )
        capabilities = QemuCapabilities(
            binary="qemu-system-aarch64",
            resolved_binary="/opt/homebrew/bin/qemu-system-aarch64",
            sandbox_supported=False,
        )
        issues = validate_security(project, capabilities)
        self.assertTrue(
            any(
                issue.severity == "error" and "блокирует запуск" in issue.message
                for issue in issues
            )
        )

    def test_required_sandbox_rejects_extra_args_override(self):
        project = default_project()
        project["vm"]["security"].update(
            {"enabled": True, "sandboxRequired": True}
        )
        project["vm"]["extraArgs"] = ["-sandbox", "off"]
        capabilities = QemuCapabilities(
            binary="qemu-system-x86_64",
            resolved_binary="/usr/bin/qemu-system-x86_64",
            sandbox_supported=True,
        )
        issues = validate_security(project, capabilities)
        self.assertTrue(
            any(issue.severity == "error" and "extraArgs" in issue.message for issue in issues)
        )

    def test_trace_validation_explains_arm64_host_output(self):
        project = default_project()
        project["vm"]["tracing"].update(
            {"enabled": True, "preset": "translation", "forceTcg": True}
        )
        with tempfile.TemporaryDirectory() as directory, patch(
            "qemu_lle_workbench.qemu.platform.machine", return_value="arm64"
        ):
            context = ProjectContext(Path(directory) / "project.lleproject")
            issues = validate_tracing(project, context)
            self.assertEqual(tracing_log_path(project, context).parent, Path(directory))
        self.assertTrue(any("ARM64-код" in issue.message for issue in issues))
        self.assertTrue(any(issue.category == "Performance" for issue in issues))


if __name__ == "__main__":
    unittest.main()
