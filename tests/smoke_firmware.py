"""Optional live BIOS/UEFI smoke test against the installed qemu-system-x86_64."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from qemu_lle_workbench.project import ProjectContext, default_project
from qemu_lle_workbench.qemu import QemuInspector, build_command, find_firmware


def _minimal_project(binary: str, architecture: str = "x86_64") -> dict:
    project = default_project()
    vm = project["vm"]
    vm.update(
        {
            "qemuBinary": binary,
            "architecture": architecture,
            "machine": "virt" if architecture == "aarch64" else "q35",
            "accelerator": "tcg",
            "memoryMiB": 256,
        }
    )
    vm["cpu"]["model"] = "max"
    vm["storage"] = {"disks": [], "iso": ""}
    vm["network"]["mode"] = "none"
    vm["video"] = {"model": "none", "display": "none"}
    vm["sound"]["model"] = "none"
    vm["usb"]["enabled"] = False
    vm["extraArgs"] = ["-nodefaults", "-S"]
    return project


def _starts_without_firmware_error(name: str, project: dict, context: ProjectContext) -> None:
    command = build_command(project, context)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(0.6)
    early_code = process.poll()
    if early_code is None:
        process.terminate()
        try:
            process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=3)
        print(f"OK  {name}: QEMU accepted firmware configuration")
        return
    _stdout, stderr = process.communicate(timeout=3)
    if early_code != 0:
        raise RuntimeError(f"{name}: QEMU exited with {early_code}: {stderr.strip()}")
    print(f"OK  {name}: QEMU parsed firmware configuration")


def main() -> int:
    capabilities = QemuInspector().inspect("qemu-system-x86_64")
    if not capabilities.resolved_binary:
        raise RuntimeError("qemu-system-x86_64 not found")
    bios, code, vars_template = find_firmware(capabilities, "x86_64", secure_boot=False)
    _bios2, secure_code, secure_vars = find_firmware(capabilities, "x86_64", secure_boot=True)
    with tempfile.TemporaryDirectory(prefix="chilledqeum-firmware-") as directory:
        base = Path(directory)
        context = ProjectContext(base / "smoke.lleproject")

        builtin = _minimal_project(capabilities.resolved_binary)
        builtin["vm"]["firmware"].update({"mode": "bios", "bios": ""})
        _starts_without_firmware_error("built-in BIOS", builtin, context)

        if bios:
            external = _minimal_project(capabilities.resolved_binary)
            external["vm"]["firmware"].update({"mode": "bios", "bios": str(bios)})
            _starts_without_firmware_error("external BIOS", external, context)

        if code and vars_template:
            vars_copy = base / "UEFI_VARS.fd"
            shutil.copy2(vars_template, vars_copy)
            uefi = _minimal_project(capabilities.resolved_binary)
            uefi["vm"]["firmware"].update(
                {"mode": "uefi", "uefiCode": str(code), "uefiVars": str(vars_copy)}
            )
            _starts_without_firmware_error("UEFI code + writable NVRAM", uefi, context)

        if secure_code and secure_vars:
            secure_vars_copy = base / "UEFI_SECURE_VARS.fd"
            shutil.copy2(secure_vars, secure_vars_copy)
            secure = _minimal_project(capabilities.resolved_binary)
            secure["vm"]["firmware"].update(
                {
                    "mode": "uefi",
                    "uefiCode": str(secure_code),
                    "uefiVars": str(secure_vars_copy),
                    "secureBoot": True,
                    "smm": True,
                }
            )
            _starts_without_firmware_error("UEFI Secure Boot + SMM", secure, context)

        arm_capabilities = QemuInspector().inspect("qemu-system-aarch64")
        if arm_capabilities.resolved_binary:
            _arm_bios, arm_code, arm_vars = find_firmware(arm_capabilities, "aarch64")
            if arm_code and arm_vars:
                arm_vars_copy = base / "AARCH64_VARS.fd"
                shutil.copy2(arm_vars, arm_vars_copy)
                arm = _minimal_project(arm_capabilities.resolved_binary, "aarch64")
                arm["vm"]["firmware"].update(
                    {"mode": "uefi", "uefiCode": str(arm_code), "uefiVars": str(arm_vars_copy)}
                )
                _starts_without_firmware_error("AArch64 UEFI + writable NVRAM", arm, context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
