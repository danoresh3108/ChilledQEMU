"""Optional live TCG trace smoke test against the installed x86_64 QEMU."""

from __future__ import annotations

import platform
import subprocess
import tempfile
import time
from pathlib import Path

from qemu_lle_workbench.project import ProjectContext, default_project
from qemu_lle_workbench.qemu import QemuInspector, build_command


def main() -> int:
    capabilities = QemuInspector().inspect("qemu-system-x86_64")
    if not capabilities.resolved_binary:
        raise RuntimeError("qemu-system-x86_64 not found")
    with tempfile.TemporaryDirectory(prefix="chilledqeum-trace-") as directory:
        base = Path(directory); log = base / "translation.log"
        project = default_project(); vm = project["vm"]
        vm.update({"qemuBinary": capabilities.resolved_binary, "memoryMiB": 128})
        vm["video"] = {"model": "none", "display": "none"}; vm["network"]["mode"] = "none"
        vm["sound"]["model"] = "none"; vm["usb"]["enabled"] = False
        vm["firmware"].update({"mode": "bios", "bios": ""})
        vm["tracing"].update(
            {"enabled": True, "preset": "translation", "forceTcg": True, "logFile": str(log)}
        )
        vm["extraArgs"] = ["-nodefaults", "-no-reboot"]
        command = build_command(project, ProjectContext(base / "trace.lleproject"))
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(0.8)
        if process.poll() is None:
            process.terminate()
        _stdout, stderr = process.communicate(timeout=5)
        if process.returncode not in (0, -15):
            raise RuntimeError(stderr.strip())
        data = log.read_text(encoding="utf-8", errors="replace")
        if "IN:" not in data or "OUT:" not in data:
            raise RuntimeError("QEMU trace does not contain both guest and host assembly")
        print(
            f"OK  TCG translation trace: host={platform.machine()}, bytes={log.stat().st_size}, "
            "guest_asm=yes, host_asm=yes"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
