from __future__ import annotations

import os
import platform
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .project import ProjectContext


def _clean(value: Any) -> str:
    return str(value).strip()


def _csv(parts: Iterable[str]) -> str:
    return ",".join(part for part in parts if part)


def suggested_binary(architecture: str) -> str:
    return f"qemu-system-{architecture or 'x86_64'}"


MACHINE_PRESETS: dict[str, list[str]] = {
    "x86_64": ["q35", "pc", "microvm", "isapc"],
    "i386": ["q35", "pc", "microvm", "isapc"],
    "aarch64": ["virt"],
    "arm": ["virt"],
    "riscv64": ["virt"],
    "riscv32": ["virt"],
    "ppc64": ["pseries", "powernv"],
    "s390x": ["s390-ccw-virtio"],
}

CPU_PRESETS: dict[str, list[str]] = {
    "x86_64": [
        "host", "max", "qemu64", "kvm64", "Haswell", "Broadwell",
        "Skylake-Client", "Cascadelake-Server", "EPYC", "EPYC-Rome", "EPYC-Milan",
    ],
    "i386": ["host", "max", "qemu32", "kvm32", "pentium3", "core2duo"],
    "aarch64": [
        "host", "max", "cortex-a53", "cortex-a57", "cortex-a72", "cortex-a76",
        "neoverse-n1", "neoverse-n2", "a64fx",
    ],
    "arm": ["max", "cortex-a7", "cortex-a8", "cortex-a9", "cortex-a15", "arm1176"],
    "riscv64": ["max", "rv64", "sifive-u54"],
    "riscv32": ["max", "rv32", "sifive-e31"],
    "ppc64": ["host", "max", "POWER9", "POWER10"],
    "s390x": ["host", "max", "qemu"],
}

VIDEO_PRESETS = [
    "virtio",
    "virtio-gpu-pci",
    "virtio-gpu-device",
    "virtio-vga",
    "virtio-vga-gl",
    "virtio-gpu-gl-pci",
    "virtio-gpu-gl-device",
    "ramfb",
    "VGA",
    "bochs-display",
    "qxl-vga",
    "cirrus-vga",
    "vmware-svga",
    "std",
    "qxl",
    "cirrus",
    "vmware",
    "none",
]

NETWORK_MODEL_PRESETS = [
    "virtio-net-pci", "virtio-net-device", "e1000", "e1000e", "rtl8139",
    "igb", "vmxnet3", "usb-net",
]

SOUND_MODEL_PRESETS = [
    "none", "ich9-intel-hda", "intel-hda", "virtio-sound-pci",
    "virtio-sound-device", "AC97", "ES1370", "usb-audio",
]

SOUND_CODEC_PRESETS = ["hda-output", "hda-duplex", "hda-micro"]

USB_CONTROLLER_PRESETS = [
    "qemu-xhci", "nec-usb-xhci", "usb-ehci", "piix3-usb-uhci",
    "piix4-usb-uhci", "pci-ohci",
]


def machine_presets(architecture: str) -> list[str]:
    return list(MACHINE_PRESETS.get(_clean(architecture), ["virt"]))


def cpu_presets(architecture: str) -> list[str]:
    return list(CPU_PRESETS.get(_clean(architecture), ["host", "max"]))


def recommended_machine(architecture: str) -> str:
    return machine_presets(architecture)[0]


def effective_video_device(model: str, architecture: str) -> str | None:
    """Translate a UI video choice to the QEMU device checked/started."""
    value = _clean(model)
    if value in {"", "default", "none"}:
        return None
    if value == "virtio":
        return "virtio-gpu-pci" if architecture in {"aarch64", "arm", "riscv64", "riscv32"} else "virtio-vga"
    legacy = {
        "std": "VGA",
        "cirrus": "cirrus-vga",
        "qxl": "qxl-vga",
        "vmware": "vmware-svga",
    }
    return legacy.get(value, value)


def machine_is_known_for_other_architecture(machine: str, architecture: str) -> bool:
    value = _clean(machine)
    known = any(value in choices for choices in MACHINE_PRESETS.values())
    return known and value not in machine_presets(architecture)


def binary_architecture(binary: str) -> str | None:
    match = re.search(r"qemu-system-([A-Za-z0-9_+-]+)$", Path(binary).name)
    if not match:
        return None
    architecture = match.group(1).lower()
    return "aarch64" if architecture == "arm64" else architecture


def binary_supports_architecture(detected: str | None, requested: str) -> bool:
    if not detected:
        return True
    if detected == requested:
        return True
    return (detected, requested) in {("x86_64", "i386"), ("aarch64", "arm")}


def effective_binary(vm: dict[str, Any]) -> str:
    return _clean(vm.get("qemuBinary")) or suggested_binary(_clean(vm.get("architecture")))


def _path_value(value: str, context: ProjectContext) -> str:
    if not value:
        return ""
    return str(context.resolve(value))


def effective_security(vm: dict[str, Any]) -> dict[str, Any]:
    configured = vm.get("security", {})
    sandbox_required = bool(configured.get("sandboxRequired"))
    if not configured.get("enabled") and not sandbox_required:
        return {"enabled": False}
    profile = _clean(configured.get("profile")) or "balanced"
    presets: dict[str, dict[str, bool]] = {
        "balanced": {
            "noUserConfig": True, "noDefaults": False, "disableMonitor": True,
            "disableSerial": False, "networkIsolation": False, "ephemeralDisks": False,
            "sandbox": False,
        },
        "strict": {
            "noUserConfig": True, "noDefaults": True, "disableMonitor": True,
            "disableSerial": True, "networkIsolation": True, "ephemeralDisks": True,
            "sandbox": False,
        },
    }
    values = dict(presets.get(profile, {
        key: bool(configured.get(key)) for key in (
            "noUserConfig", "noDefaults", "disableMonitor", "disableSerial",
            "networkIsolation", "ephemeralDisks", "sandbox",
        )
    }))
    # Sandbox is an independent policy outside the profile presets. This makes
    # it possible to add it to balanced/strict and prevents a profile change
    # from silently removing a required sandbox.
    values["sandbox"] = bool(configured.get("sandbox")) or sandbox_required
    return {
        "enabled": True,
        "profile": profile,
        "sandboxRequired": sandbox_required,
        "sandboxLockUntil": configured.get("sandboxLockUntil", 0),
        **values,
    }


def effective_tracing(vm: dict[str, Any]) -> dict[str, Any]:
    configured = vm.get("tracing", {})
    if not configured.get("enabled"):
        return {"enabled": False}
    preset = _clean(configured.get("preset")) or "translation"
    presets: dict[str, dict[str, bool]] = {
        "translation": {
            "guestAssembly": True, "hostAssembly": True, "tcgOps": False,
            "optimizedOps": True, "executedBlocks": False, "cpuState": False,
            "interrupts": False, "cpuReset": False, "unimplemented": False,
            "guestErrors": True, "noChain": False,
        },
        "instructions": {
            "guestAssembly": True, "hostAssembly": False, "tcgOps": False,
            "optimizedOps": False, "executedBlocks": True, "cpuState": False,
            "interrupts": False, "cpuReset": False, "unimplemented": False,
            "guestErrors": True, "noChain": True,
        },
        "diagnostics": {
            "guestAssembly": False, "hostAssembly": False, "tcgOps": False,
            "optimizedOps": False, "executedBlocks": False, "cpuState": False,
            "interrupts": True, "cpuReset": True, "unimplemented": True,
            "guestErrors": True, "noChain": False,
        },
    }
    keys = (
        "guestAssembly", "hostAssembly", "tcgOps", "optimizedOps", "executedBlocks",
        "cpuState", "interrupts", "cpuReset", "unimplemented", "guestErrors", "noChain",
    )
    values = presets.get(preset, {key: bool(configured.get(key)) for key in keys})
    return {
        "enabled": True,
        "preset": preset,
        "forceTcg": bool(configured.get("forceTcg", True)),
        "captureSerial": bool(configured.get("captureSerial", False)),
        "addressFilter": _clean(configured.get("addressFilter")),
        "logFile": _clean(configured.get("logFile")),
        **values,
    }


def tracing_log_items(tracing: dict[str, Any]) -> list[str]:
    mapping = (
        ("guestAssembly", "in_asm"), ("hostAssembly", "out_asm"),
        ("tcgOps", "op"), ("optimizedOps", "op_opt"),
        ("executedBlocks", "exec"), ("cpuState", "cpu"),
        ("interrupts", "int"), ("cpuReset", "cpu_reset"),
        ("unimplemented", "unimp"), ("guestErrors", "guest_errors"),
        ("noChain", "nochain"),
    )
    return [qemu_name for field, qemu_name in mapping if tracing.get(field)]


def tracing_log_path(
    project: dict[str, Any], context: ProjectContext | None = None
) -> Path:
    context = context or ProjectContext()
    configured = _clean(project["vm"].get("tracing", {}).get("logFile"))
    if configured:
        return context.resolve(configured)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(project.get("name") or "virtual-machine")).strip("-")
    return context.base_dir / f"{safe_name or 'virtual-machine'}.qemu-trace.log"


def _drive_argument(
    disk: dict[str, Any], index: int, context: ProjectContext, force_snapshot: bool = False
) -> list[str]:
    path = _path_value(_clean(disk.get("path")), context)
    if not path:
        return []
    interface = _clean(disk.get("interface")) or "virtio"
    fmt = _clean(disk.get("format")) or "raw"
    common = [f"file={path}", f"format={fmt}"]
    if disk.get("readOnly"):
        common.append("readonly=on")
    if disk.get("snapshot") or force_snapshot:
        common.append("snapshot=on")
    if interface in {"nvme", "usb"}:
        drive_id = f"drive{index}"
        args = ["-drive", _csv([*common, "if=none", f"id={drive_id}"])]
        if interface == "nvme":
            args += ["-device", f"nvme,drive={drive_id},serial=LLE{index:04d}"]
        else:
            args += ["-device", f"usb-storage,drive={drive_id}"]
        return args
    return ["-drive", _csv([*common, f"if={interface}"])]


def build_command(project: dict[str, Any], context: ProjectContext | None = None) -> list[str]:
    context = context or ProjectContext()
    vm = project["vm"]
    firmware = vm.get("firmware", {})
    security = effective_security(vm)
    tracing = effective_tracing(vm)
    args: list[str] = [effective_binary(vm)]

    machine_parts = [_clean(vm.get("machine"))]
    accelerator = _clean(vm.get("accelerator"))
    if tracing.get("enabled") and tracing.get("forceTcg"):
        accelerator = "tcg"
    if accelerator and accelerator != "default":
        machine_parts.append(f"accel={accelerator}")
    if firmware.get("smm"):
        machine_parts.append("smm=on")
    if machine_parts[0]:
        args += ["-machine", _csv(machine_parts)]

    cpu = vm.get("cpu", {})
    model = _clean(cpu.get("model"))
    if tracing.get("enabled") and tracing.get("forceTcg") and model == "host":
        model = "max"
    if model:
        args += ["-cpu", model]
    args += [
        "-smp",
        _csv(
            [
                f"cores={int(cpu.get('cores', 1))}",
                f"sockets={int(cpu.get('sockets', 1))}",
                f"threads={int(cpu.get('threads', 1))}",
            ]
        ),
        "-m",
        str(int(vm.get("memoryMiB", 1024))),
    ]
    if project.get("name"):
        args += ["-name", str(project["name"])]

    storage = vm.get("storage", {})
    for index, disk in enumerate(storage.get("disks", [])):
        args.extend(_drive_argument(disk, index, context, bool(security.get("ephemeralDisks"))))
    iso = _path_value(_clean(storage.get("iso")), context)
    if iso:
        args += ["-cdrom", iso]

    mode = _clean(firmware.get("mode"))
    bios = _path_value(_clean(firmware.get("bios")), context)
    uefi_code = _path_value(_clean(firmware.get("uefiCode")), context)
    uefi_vars = _path_value(_clean(firmware.get("uefiVars")), context)
    if mode == "bios" and bios:
        args += ["-bios", bios]
    elif mode == "uefi":
        pflash_format = _clean(firmware.get("pflashFormat")) or "raw"
        if uefi_code:
            code_parts = ["if=pflash", "unit=0", f"format={pflash_format}"]
            if firmware.get("uefiCodeReadOnly", True):
                code_parts.append("readonly=on")
            code_parts.append(f"file={uefi_code}")
            args += ["-drive", _csv(code_parts)]
        if uefi_vars:
            vars_parts = ["if=pflash", "unit=1", f"format={pflash_format}"]
            if firmware.get("uefiVarsReadOnly", False):
                vars_parts.append("readonly=on")
            vars_parts.append(f"file={uefi_vars}")
            args += ["-drive", _csv(vars_parts)]
    boot_order = _clean(firmware.get("bootOrder"))
    if boot_order:
        args += ["-boot", f"order={boot_order}"]

    network = vm.get("network", {})
    net_mode = "none" if security.get("networkIsolation") else _clean(network.get("mode"))
    if net_mode == "none":
        args += ["-nic", "none"]
    elif net_mode:
        net_parts = [net_mode, "id=net0"]
        if net_mode == "tap":
            if network.get("interface"):
                net_parts.append(f"ifname={network['interface']}")
            net_parts += ["script=no", "downscript=no"]
        elif net_mode == "bridge" and network.get("bridge"):
            net_parts.append(f"br={network['bridge']}")
        elif net_mode == "user":
            for forwarding in network.get("hostForwards", []):
                spec = _clean(forwarding)
                if spec:
                    net_parts.append(f"hostfwd={spec}")
        args += ["-netdev", _csv(net_parts)]
        device_parts = [_clean(network.get("model")) or "virtio-net-pci", "netdev=net0"]
        if network.get("mac"):
            device_parts.append(f"mac={network['mac']}")
        args += ["-device", _csv(device_parts)]

    video = vm.get("video", {})
    display = _clean(video.get("display"))
    video_model = _clean(video.get("model"))
    video_device = effective_video_device(video_model, _clean(vm.get("architecture")))
    if display:
        args += ["-display", display]
    if video_model == "none":
        args += ["-vga", "none"]
    elif video_model in {"std", "cirrus", "qxl", "vmware"}:
        args += ["-vga", video_model]
    elif video_device:
        args += ["-device", video_device]

    sound = vm.get("sound", {})
    sound_model = _clean(sound.get("model"))
    backend = _clean(sound.get("backend"))
    if sound_model and sound_model != "none":
        if backend and backend != "default":
            args += ["-audiodev", f"{backend},id=audio0"]
        if sound_model in {"ich9-intel-hda", "intel-hda"}:
            args += ["-device", sound_model]
            codec_model = _clean(sound.get("codec")) or "hda-output"
            codec = codec_model + (",audiodev=audio0" if backend and backend != "default" else "")
            args += ["-device", codec]
        else:
            device = sound_model + (",audiodev=audio0" if backend and backend != "default" else "")
            args += ["-device", device]

    usb = vm.get("usb", {})
    if usb.get("enabled"):
        controller = _clean(usb.get("controller"))
        if controller:
            args += ["-device", controller]
        for device in usb.get("devices", []):
            if _clean(device):
                args += ["-device", _clean(device)]

    lle = project.get("lle", {})
    if lle.get("enabled"):
        for device in lle.get("deviceModels", []):
            if not isinstance(device, dict) or device.get("enabled", True) is False:
                continue
            qemu_device = _clean(device.get("qemuDevice"))
            if not qemu_device:
                continue
            properties = device.get("properties", {})
            device_parts = [qemu_device]
            if isinstance(properties, dict):
                device_parts.extend(f"{key}={value}" for key, value in properties.items())
            args += ["-device", _csv(device_parts)]
        timing = lle.get("timingClockOptions", {})
        if _clean(timing.get("rtc")):
            args += ["-rtc", _clean(timing["rtc"])]
        if _clean(timing.get("icount")):
            args += ["-icount", _clean(timing["icount"])]
        args.extend(str(value) for value in timing.get("extraArgs", []) if str(value))
        for rom in lle.get("firmware", {}).get("roms", []):
            if not isinstance(rom, dict) or rom.get("enabled", True) is False:
                continue
            rom_path = _path_value(_clean(rom.get("path")), context)
            qemu_args = rom.get("qemuArgs", [])
            if rom_path and isinstance(qemu_args, list):
                args.extend(str(token).replace("{path}", rom_path) for token in qemu_args)

    if security.get("enabled"):
        if security.get("noUserConfig"):
            args.append("-no-user-config")
        if security.get("noDefaults"):
            args.append("-nodefaults")
        if security.get("disableMonitor"):
            args += ["-monitor", "none"]
        if security.get("disableSerial") and not tracing.get("captureSerial"):
            args += ["-serial", "none"]
        if security.get("sandbox"):
            args += [
                "-sandbox",
                "on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny",
            ]
    if tracing.get("enabled"):
        log_items = tracing_log_items(tracing)
        if log_items:
            args += ["-d", ",".join(log_items), "-D", str(tracing_log_path(project, context))]
        if tracing.get("addressFilter"):
            args += ["-dfilter", str(tracing["addressFilter"])]
        if tracing.get("captureSerial"):
            args += ["-serial", "stdio"]
    args.extend(str(value) for value in vm.get("extraArgs", []) if str(value))
    return args


def command_text(command: list[str]) -> str:
    return shlex.join(command)


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    category: str
    message: str


@dataclass
class QemuCapabilities:
    binary: str
    resolved_binary: str | None = None
    version: str = ""
    machines: set[str] = field(default_factory=set)
    cpu_models: set[str] = field(default_factory=set)
    devices: set[str] = field(default_factory=set)
    device_categories: dict[str, set[str]] = field(default_factory=dict)
    display_backends: set[str] = field(default_factory=set)
    audio_backends: set[str] = field(default_factory=set)
    module_files: set[str] = field(default_factory=set)
    module_dirs: list[Path] = field(default_factory=list)
    firmware_files: list[Path] = field(default_factory=list)
    data_dirs: list[Path] = field(default_factory=list)
    sandbox_supported: bool = False
    errors: list[str] = field(default_factory=list)


class QemuInspector:
    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def inspect(self, binary: str) -> QemuCapabilities:
        candidate = shutil.which(binary) if not Path(binary).is_file() else str(Path(binary))
        resolved = str(Path(candidate).resolve()) if candidate else None
        result = QemuCapabilities(binary=binary, resolved_binary=resolved)
        if not resolved:
            result.errors.append(f"Бинарник QEMU не найден: {binary}")
            return result
        version_output = self._run(resolved, ["--version"], result)
        if version_output:
            result.version = version_output.splitlines()[0]
        result.machines = self._parse_machines(self._run(resolved, ["-machine", "help"], result))
        result.cpu_models = self._parse_cpu_models(self._run(resolved, ["-cpu", "help"], result))
        device_output = self._run(resolved, ["-device", "help"], result)
        result.devices = self._parse_devices(device_output)
        result.device_categories = self._parse_device_categories(device_output)
        result.display_backends = self._parse_backends(
            self._run(resolved, ["-display", "help"], result)
        )
        result.audio_backends = self._parse_backends(
            self._run(resolved, ["-audiodev", "help"], result)
        )
        result.sandbox_supported = self._probe_sandbox(resolved)
        result.module_dirs = self._module_dirs(Path(resolved))
        for directory in result.module_dirs:
            try:
                for item in directory.iterdir():
                    if item.is_file():
                        result.module_files.add(item.name)
                        result.module_files.add(item.stem)
            except OSError:
                continue
        result.data_dirs = self._data_dirs(Path(resolved))
        for directory in result.data_dirs:
            try:
                result.firmware_files.extend(
                    path.resolve() for path in directory.rglob("*")
                    if path.is_file() and path.suffix.lower() in {".fd", ".bin", ".rom"}
                )
            except OSError:
                continue
        result.firmware_files = sorted(set(result.firmware_files))
        return result

    def _probe_sandbox(self, binary: str) -> bool:
        try:
            completed = subprocess.run(
                [binary, "-sandbox", "on", "--version"],
                capture_output=True, text=True, timeout=self.timeout, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return completed.returncode == 0

    def _run(self, binary: str, args: list[str], result: QemuCapabilities) -> str:
        try:
            completed = subprocess.run(
                [binary, *args], capture_output=True, text=True, timeout=self.timeout, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            result.errors.append(f"{Path(binary).name} {' '.join(args)}: {exc}")
            return ""
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
        if completed.returncode not in (0, 1):
            result.errors.append(f"Команда {' '.join(args)} завершилась с кодом {completed.returncode}")
        return output

    @staticmethod
    def _parse_machines(output: str) -> set[str]:
        machines: set[str] = set()
        for line in output.splitlines():
            match = re.match(r"^\s*([A-Za-z0-9_.+-]+)\s+", line)
            if match and match.group(1).lower() not in {"supported", "none"}:
                machines.add(match.group(1))
        return machines

    @staticmethod
    def _parse_devices(output: str) -> set[str]:
        devices: set[str] = set()
        for line in output.splitlines():
            quoted = re.match(r'^\s*name\s+"([^"]+)"', line)
            simple = re.match(r"^\s*([A-Za-z0-9_.+-]+)\s+", line)
            if quoted:
                devices.add(quoted.group(1))
            elif simple and not line.lstrip().startswith(("Controller/", "Network/", "Storage/", "USB/")):
                devices.add(simple.group(1))
        return devices

    @staticmethod
    def _parse_device_categories(output: str) -> dict[str, set[str]]:
        categories: dict[str, set[str]] = {}
        current = ""
        for line in output.splitlines():
            header = re.match(r"^\s*([^:]+ devices):\s*$", line, re.IGNORECASE)
            if header:
                current = header.group(1).strip().lower()
                categories.setdefault(current, set())
                continue
            quoted = re.match(r'^\s*name\s+"([^"]+)"', line)
            if current and quoted:
                categories[current].add(quoted.group(1))
        return categories

    @staticmethod
    def _parse_backends(output: str) -> set[str]:
        choices: set[str] = set()
        for line in output.splitlines():
            value = line.strip()
            if re.fullmatch(r"[A-Za-z0-9_.+-]+", value) and value.lower() not in {
                "available", "audio", "display", "drivers", "backends", "types",
            }:
                choices.add(value)
        return choices

    @staticmethod
    def _parse_cpu_models(output: str) -> set[str]:
        models: set[str] = set()
        architecture_prefixes = {"x86", "arm", "aarch64", "powerpc", "ppc", "s390x", "riscv"}
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped or stripped.lower().startswith("available cpus"):
                continue
            if stripped.lower().startswith(("recognized cpuid", "recognized feature", "default cpu")):
                break
            tokens = stripped.split()
            if not tokens:
                continue
            candidate = tokens[1] if tokens[0].lower() in architecture_prefixes and len(tokens) > 1 else tokens[0]
            if re.fullmatch(r"[A-Za-z0-9_.+-]+", candidate):
                models.add(candidate)
        return models

    @staticmethod
    def _module_dirs(binary: Path) -> list[Path]:
        candidates: list[Path] = []
        env_dir = os.environ.get("QEMU_MODULE_DIR")
        if env_dir:
            candidates.append(Path(env_dir).expanduser())
        prefix = binary.parent.parent
        candidates += [
            prefix / "lib" / "qemu",
            prefix / "lib64" / "qemu",
            Path("/opt/homebrew/lib/qemu"),
            Path("/usr/local/lib/qemu"),
            Path("/usr/lib/qemu"),
            Path("/usr/lib64/qemu"),
        ]
        unique: list[Path] = []
        for path in candidates:
            if path.is_dir() and path not in unique:
                unique.append(path)
        return unique

    @staticmethod
    def _data_dirs(binary: Path) -> list[Path]:
        prefix = binary.parent.parent
        candidates = [
            prefix / "share" / "qemu",
            Path("/opt/homebrew/share/qemu"),
            Path("/usr/local/share/qemu"),
            Path("/usr/share/qemu"),
        ]
        unique: list[Path] = []
        for path in candidates:
            if path.is_dir() and path not in unique:
                unique.append(path)
        return unique


def find_firmware(
    capabilities: QemuCapabilities, architecture: str, secure_boot: bool = False
) -> tuple[Path | None, Path | None, Path | None]:
    """Return the best (BIOS, UEFI code, UEFI vars template) candidates."""
    files = capabilities.firmware_files
    lowered = [(path, path.name.lower()) for path in files]

    bios = (
        next((path for path, name in lowered if name == "bios.bin"), None)
        if architecture in {"x86_64", "i386"}
        else None
    )
    arch_tokens = {
        "x86_64": ("x86_64", "i386", "ovmf"),
        "i386": ("i386", "x86_64", "ovmf"),
        "aarch64": ("aarch64", "arm", "aavmf"),
        "arm": ("arm", "aarch64", "aavmf"),
        "riscv64": ("riscv",),
        "loongarch64": ("loongarch64",),
    }.get(architecture, (architecture.lower(),))

    def score(path: Path, name: str, role: str) -> tuple[int, str]:
        points = 0
        if role in name:
            points += 10
        for index, token in enumerate(arch_tokens):
            if token and token in name:
                points += max(1, 6 - index * 2)
                break
        if "edk2" in name or "ovmf" in name or "aavmf" in name:
            points += 3
        has_secure = "secure" in name or "secboot" in name
        if secure_boot == has_secure:
            points += 4
        elif has_secure:
            points -= 5
        return points, str(path)

    def matches_architecture(name: str) -> bool:
        return any(token and token in name for token in arch_tokens)

    code_candidates = [
        (score(path, name, "code"), path)
        for path, name in lowered
        if "code" in name and matches_architecture(name)
    ]
    vars_candidates = [
        (score(path, name, "vars"), path)
        for path, name in lowered
        if "vars" in name and matches_architecture(name)
    ]
    code = max(code_candidates, default=((0, ""), None))[1]
    vars_template = max(vars_candidates, default=((0, ""), None))[1]
    return bios, code, vars_template


def _validate_readable_file(
    value: str, label: str, context: ProjectContext, issues: list[ValidationIssue], required: bool
) -> Path | None:
    if not value:
        if required:
            issues.append(ValidationIssue("error", "Firmware", f"Не указан {label}."))
        return None
    path = context.resolve(value)
    if not path.is_file() or not os.access(path, os.R_OK):
        issues.append(ValidationIssue("error", "Firmware", f"{label} не найден или не читается: {value}"))
        return None
    issues.append(ValidationIssue("ok", "Firmware", f"Доступен {label}: {value}"))
    return path


def validate_firmware(
    project: dict[str, Any], context: ProjectContext | None = None
) -> list[ValidationIssue]:
    context = context or ProjectContext()
    vm = project["vm"]
    firmware = vm.get("firmware", {})
    mode = _clean(firmware.get("mode")) or "default"
    issues: list[ValidationIssue] = []
    if mode == "default":
        issues.append(ValidationIssue("ok", "Firmware", "Используется firmware по умолчанию выбранной machine."))
        return issues
    if mode == "bios":
        bios = _clean(firmware.get("bios"))
        if bios:
            bios_path = _validate_readable_file(bios, "BIOS image", context, issues, required=True)
            architecture = _clean(vm.get("architecture"))
            if (
                bios_path
                and architecture in {"aarch64", "arm"}
                and bios_path.name.lower() == "bios.bin"
            ):
                issues.append(
                    ValidationIssue(
                        "error",
                        "Firmware",
                        "QEMU bios.bin — x86 SeaBIOS и не загружает ARM64 Windows. "
                        "Выберите режим uefi, edk2-aarch64-code.fd и отдельную копию edk2-arm-vars.fd.",
                    )
                )
        elif _clean(vm.get("architecture")) in {"x86_64", "i386"}:
            issues.append(ValidationIssue("ok", "Firmware", "Используется встроенный SeaBIOS/BIOS этой сборки QEMU."))
        else:
            issues.append(ValidationIssue("warning", "Firmware", "BIOS image не задан; результат зависит от firmware выбранной machine."))
        return issues
    if mode != "uefi":
        issues.append(ValidationIssue("error", "Firmware", f"Неизвестный режим firmware: {mode}"))
        return issues

    code_value = _clean(firmware.get("uefiCode"))
    vars_value = _clean(firmware.get("uefiVars"))
    code_path = _validate_readable_file(code_value, "UEFI code", context, issues, required=True)
    vars_path = _validate_readable_file(vars_value, "UEFI vars/NVRAM", context, issues, required=False)
    if not vars_value:
        issues.append(ValidationIssue("warning", "Firmware", "UEFI vars не указан: NVRAM не будет сохраняться."))
    if code_path and vars_path and code_path.resolve() == vars_path.resolve():
        issues.append(ValidationIssue("error", "Firmware", "UEFI code и vars указывают на один файл; создайте отдельную копию NVRAM."))
    if vars_path and not firmware.get("uefiVarsReadOnly", False) and not os.access(vars_path, os.W_OK):
        issues.append(ValidationIssue("warning", "Firmware", f"UEFI vars не доступен для записи: {vars_value}"))
    if firmware.get("secureBoot"):
        name = code_path.name.lower() if code_path else ""
        if "secure" not in name and "secboot" not in name:
            issues.append(ValidationIssue("warning", "Secure Boot", "Имя UEFI code не похоже на Secure Boot build; проверьте образ вручную."))
        if _clean(vm.get("machine")) == "q35" and not firmware.get("smm"):
            issues.append(ValidationIssue("warning", "Secure Boot", "Для q35 Secure Boot обычно требуется SMM."))
    return issues


def validate_security(
    project: dict[str, Any], capabilities: QemuCapabilities
) -> list[ValidationIssue]:
    vm = project["vm"]
    security = effective_security(vm)
    if not security.get("enabled"):
        return []
    profile = security.get("profile", "custom")
    issues = [ValidationIssue("ok", "Security", f"Активен профиль безопасного запуска: {profile}.")]
    if security.get("networkIsolation"):
        issues.append(ValidationIssue("ok", "Security", "Сеть гостя принудительно отключена."))
    if security.get("ephemeralDisks"):
        issues.append(ValidationIssue("ok", "Security", "Записи дисков временные (snapshot=on)."))
    if security.get("sandbox"):
        if capabilities.sandbox_supported:
            qualifier = " и обязателен для запуска" if security.get("sandboxRequired") else ""
            issues.append(ValidationIssue("ok", "Security", f"QEMU sandbox поддерживается бинарником{qualifier}."))
        else:
            action = (
                "Обязательная политика блокирует запуск: установите QEMU для Linux, собранный с seccomp, "
                "либо после подтверждения снимите обязательность."
                if security.get("sandboxRequired")
                else "Отключите sandbox или используйте QEMU для Linux, собранный с seccomp."
            )
            issues.append(
                ValidationIssue(
                    "error", "Security",
                    "Запрошен QEMU -sandbox, но выбранный бинарник собран без его поддержки. "
                    "На macOS Homebrew это ожидаемо. " + action,
                )
            )
    extra_args = [str(value) for value in vm.get("extraArgs", [])]
    conflicts: list[str] = []
    if security.get("disableMonitor") and any(value in {"-monitor", "-qmp"} for value in extra_args):
        conflicts.append("monitor/QMP")
    if security.get("disableSerial") and "-serial" in extra_args:
        conflicts.append("serial")
    if security.get("sandboxRequired") and any(
        value in {"-sandbox", "--sandbox"} for value in extra_args
    ):
        issues.append(
            ValidationIssue(
                "error",
                "Security",
                "Обязательный -sandbox нельзя переопределять через extraArgs; изменяйте его только на вкладке Безопасность.",
            )
        )
    if conflicts:
        issues.append(
            ValidationIssue(
                "warning", "Security",
                "Дополнительные аргументы снова включают отключённые интерфейсы: " + ", ".join(conflicts),
            )
        )
    return issues


def validate_tracing(
    project: dict[str, Any], context: ProjectContext | None = None
) -> list[ValidationIssue]:
    context = context or ProjectContext()
    vm = project["vm"]
    tracing = effective_tracing(vm)
    if not tracing.get("enabled"):
        return []
    items = tracing_log_items(tracing)
    issues: list[ValidationIssue] = []
    if not items and not tracing.get("captureSerial"):
        issues.append(ValidationIssue("warning", "Tracing", "Трассировка включена, но ни один источник логов не выбран."))
    else:
        issues.append(ValidationIssue("ok", "Tracing", "Активны источники: " + ", ".join(items or ["serial"])))
    tcg_specific = any(tracing.get(key) for key in ("hostAssembly", "tcgOps", "optimizedOps"))
    if tcg_specific and not tracing.get("forceTcg"):
        issues.append(
            ValidationIssue("warning", "Tracing", "Перевод TCG выбран без принудительного TCG; с HVF/KVM out_asm/op могут быть пустыми.")
        )
    if tracing.get("forceTcg"):
        issues.append(ValidationIssue("warning", "Performance", "Трассировка принудительно использует TCG вместо аппаратного ускорителя."))
        if _clean(vm.get("cpu", {}).get("model")) == "host":
            issues.append(ValidationIssue("ok", "Tracing", "CPU=host временно заменён на CPU=max, совместимый с TCG."))
    host_arch = platform.machine().lower()
    if tracing.get("hostAssembly"):
        if host_arch in {"arm64", "aarch64"}:
            issues.append(ValidationIssue("ok", "Tracing", "out_asm будет содержать сгенерированный ARM64-код хоста."))
        else:
            issues.append(ValidationIssue("warning", "Tracing", f"out_asm покажет код архитектуры хоста {host_arch}, а не ARM64."))
    if tracing.get("executedBlocks") or tracing.get("cpuState"):
        issues.append(ValidationIssue("warning", "Performance", "exec/cpu создают очень большие логи и значительно замедляют ВМ."))
    log_path = tracing_log_path(project, context)
    if not log_path.parent.is_dir():
        issues.append(ValidationIssue("error", "Tracing", f"Папка журнала не существует: {log_path.parent}"))
    elif log_path.exists() and not os.access(log_path, os.W_OK):
        issues.append(ValidationIssue("error", "Tracing", f"Файл журнала недоступен для записи: {log_path}"))
    if tracing.get("captureSerial") and effective_security(vm).get("disableSerial"):
        issues.append(ValidationIssue("warning", "Security", "Трассировка serial временно переопределяет отключение serial в профиле безопасности."))
    return issues


def validate_against_qemu(
    project: dict[str, Any], capabilities: QemuCapabilities, context: ProjectContext | None = None
) -> list[ValidationIssue]:
    context = context or ProjectContext()
    issues: list[ValidationIssue] = []
    if not capabilities.resolved_binary:
        issues.append(ValidationIssue("error", "QEMU", f"Не найден {capabilities.binary}"))
        return issues
    issues.append(ValidationIssue("ok", "QEMU", capabilities.version or capabilities.resolved_binary))
    for error in capabilities.errors:
        issues.append(ValidationIssue("warning", "QEMU inspection", error))
    vm = project["vm"]
    architecture = _clean(vm.get("architecture"))
    detected_architecture = binary_architecture(capabilities.resolved_binary or capabilities.binary)
    if not binary_supports_architecture(detected_architecture, architecture):
        issues.append(
            ValidationIssue(
                "error",
                "Architecture",
                f"Выбрана architecture={architecture}, но QEMU binary предназначен для {detected_architecture}: "
                f"{capabilities.resolved_binary or capabilities.binary}",
            )
        )
    machine = _clean(vm.get("machine"))
    if machine and capabilities.machines and machine not in capabilities.machines:
        suggestion = recommended_machine(architecture)
        issues.append(
            ValidationIssue(
                "error",
                "Machine",
                f"Machine {machine!r} не поддерживается {Path(capabilities.resolved_binary).name}. "
                f"Для architecture={architecture} выберите {suggestion!r} или другую модель из списка QEMU.",
            )
        )

    cpu_model = _clean(vm.get("cpu", {}).get("model"))
    cpu_base_model = cpu_model.split(",", 1)[0]
    if cpu_base_model and capabilities.cpu_models:
        if cpu_base_model in capabilities.cpu_models:
            issues.append(ValidationIssue("ok", "CPU", f"Модель CPU доступна: {cpu_base_model}"))
        else:
            issues.append(
                ValidationIssue(
                    "error",
                    "CPU",
                    f"Модель CPU {cpu_base_model!r} не объявлена {Path(capabilities.resolved_binary).name}. "
                    "Загрузите список моделей из выбранного QEMU.",
                )
            )

    configured_devices: list[tuple[str, str]] = []
    network = vm.get("network", {})
    if _clean(network.get("mode")) not in {"", "none"}:
        configured_devices.append(("Network", _clean(network.get("model")) or "virtio-net-pci"))
    video_device = effective_video_device(
        _clean(vm.get("video", {}).get("model")), architecture
    )
    if video_device:
        configured_devices.append(("Video", video_device))
    sound = vm.get("sound", {})
    sound_model = _clean(sound.get("model"))
    if sound_model and sound_model != "none":
        configured_devices.append(("Audio", sound_model))
        if sound_model in {"ich9-intel-hda", "intel-hda"}:
            configured_devices.append(("Audio codec", _clean(sound.get("codec")) or "hda-output"))
    usb = vm.get("usb", {})
    if usb.get("enabled"):
        if _clean(usb.get("controller")):
            configured_devices.append(("USB", _clean(usb.get("controller"))))
        configured_devices.extend(
            ("USB", _clean(device)) for device in usb.get("devices", []) if _clean(device)
        )
    for category, device in configured_devices:
        if capabilities.devices and device not in capabilities.devices:
            issues.append(
                ValidationIssue(
                    "error",
                    category,
                    f"Выбранное устройство {device!r} отсутствует в {Path(capabilities.resolved_binary).name}.",
                )
            )
        else:
            issues.append(ValidationIssue("ok", category, f"Устройство доступно: {device}"))

    codec = _clean(sound.get("codec")) or "hda-output"
    if (
        sound_model in {"ich9-intel-hda", "intel-hda"}
        and _clean(sound.get("backend")) == "coreaudio"
        and codec in {"hda-duplex", "hda-micro"}
    ):
        issues.append(
            ValidationIssue(
                "error",
                "Audio",
                "CoreAudio в QEMU поддерживает только воспроизведение: кодек с микрофоном "
                f"{codec!r} вызывает ошибку adc. Выберите hda-output или отключите звук.",
            )
        )

    issues.extend(validate_firmware(project, context))
    issues.extend(validate_security(project, capabilities))
    issues.extend(validate_tracing(project, context))

    lle = project.get("lle", {})
    if not lle.get("enabled"):
        issues.append(ValidationIssue("ok", "LLE", "Секция LLE отключена; проверены только базовые параметры."))
        return issues

    required_devices = {_clean(item) for item in lle.get("requiredQemuDevices", []) if _clean(item)}
    for model in lle.get("deviceModels", []):
        if isinstance(model, dict) and model.get("enabled", True):
            name = _clean(model.get("qemuDevice"))
            if name:
                required_devices.add(name)
    for device in sorted(required_devices):
        if device in capabilities.devices:
            issues.append(ValidationIssue("ok", "Device", f"Доступно: {device}"))
        else:
            issues.append(ValidationIssue("warning", "Device", f"Не найдено устройство QEMU: {device}"))

    for rom in lle.get("firmware", {}).get("roms", []):
        if not isinstance(rom, dict) or rom.get("enabled", True) is False:
            continue
        value = _clean(rom.get("path"))
        if not value:
            issues.append(ValidationIssue("warning", "ROM", "У записи ROM не указан path."))
            continue
        path = context.resolve(value)
        if path.is_file() and os.access(path, os.R_OK):
            issues.append(ValidationIssue("ok", "ROM", f"Доступен: {value}"))
        elif rom.get("required", True):
            issues.append(ValidationIssue("warning", "ROM", f"Файл не найден или не читается: {value}"))

    available_lower = {name.lower() for name in capabilities.module_files}
    for module in lle.get("requiredModules", []):
        value = _clean(module)
        if not value:
            continue
        explicit = context.resolve(value)
        found = explicit.is_file() if ("/" in value or "\\" in value) else False
        needle = Path(value).name.lower()
        found = found or needle in available_lower or Path(needle).stem in available_lower
        if not found:
            found = any(needle in candidate for candidate in available_lower)
        if found:
            issues.append(ValidationIssue("ok", "Module", f"Доступен: {value}"))
        else:
            searched = ", ".join(str(path) for path in capabilities.module_dirs) or "каталоги модулей не найдены"
            issues.append(ValidationIssue("warning", "Module", f"Не найден модуль {value!r} ({searched})."))

    if not required_devices and not lle.get("firmware", {}).get("roms") and not lle.get("requiredModules"):
        issues.append(ValidationIssue("warning", "LLE", "LLE включён, но зависимости не перечислены."))
    return issues
