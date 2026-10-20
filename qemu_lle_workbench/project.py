from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_EXTENSION = ".lleproject"
PROJECT_FORMAT = "qemu-lle-project"
PROJECT_VERSION = 1


def default_project() -> dict[str, Any]:
    return {
        "format": PROJECT_FORMAT,
        "version": PROJECT_VERSION,
        "name": "New virtual machine",
        "vm": {
            "qemuBinary": "",
            "architecture": "x86_64",
            "machine": "q35",
            "accelerator": "hvf",
            "cpu": {"model": "host", "cores": 2, "sockets": 1, "threads": 1},
            "memoryMiB": 4096,
            "storage": {"disks": [], "iso": ""},
            "network": {
                "mode": "user",
                "model": "virtio-net-pci",
                "mac": "",
                "interface": "",
                "bridge": "",
                "hostForwards": [],
            },
            "video": {"model": "virtio", "display": "cocoa"},
            "sound": {"model": "none", "codec": "hda-output", "backend": "coreaudio"},
            "usb": {"enabled": True, "controller": "qemu-xhci", "devices": ["usb-tablet"]},
            "firmware": {
                "realUefiDump": False,
                "mode": "default",
                "bios": "",
                "uefiCode": "",
                "uefiVars": "",
                "pflashFormat": "raw",
                "uefiCodeReadOnly": True,
                "uefiVarsReadOnly": False,
                "secureBoot": False,
                "smm": False,
                "bootOrder": "cdn",
            },
            "security": {
                "enabled": False,
                "profile": "balanced",
                "noUserConfig": True,
                "noDefaults": False,
                "disableMonitor": True,
                "disableSerial": False,
                "networkIsolation": False,
                "ephemeralDisks": False,
                "sandbox": False,
                "sandboxRequired": False,
                "sandboxLockUntil": 0,
            },
            "tracing": {
                "enabled": False,
                "preset": "translation",
                "forceTcg": True,
                "guestAssembly": True,
                "hostAssembly": True,
                "tcgOps": False,
                "optimizedOps": True,
                "executedBlocks": False,
                "cpuState": False,
                "interrupts": False,
                "cpuReset": False,
                "unimplemented": False,
                "guestErrors": True,
                "noChain": False,
                "captureSerial": False,
                "addressFilter": "",
                "logFile": "",
            },
            "extraArgs": [],
        },
        "lle": {
            "enabled": False,
            "firmware": {"roms": []},
            "deviceModels": [],
            "timingClockOptions": {"rtc": "", "icount": "", "extraArgs": []},
            "requiredQemuDevices": [],
            "requiredModules": [],
            "notes": "",
            "instructions": "",
        },
    }


class ProjectError(ValueError):
    pass


def _deep_merge(default: Any, incoming: Any) -> Any:
    if isinstance(default, dict) and isinstance(incoming, dict):
        result = copy.deepcopy(default)
        for key, value in incoming.items():
            result[key] = _deep_merge(result[key], value) if key in result else copy.deepcopy(value)
        return result
    return copy.deepcopy(incoming)


def normalize_project(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ProjectError("Корень проекта должен быть JSON-объектом.")
    if data.get("format", PROJECT_FORMAT) != PROJECT_FORMAT:
        raise ProjectError(f"Неизвестный формат проекта: {data.get('format')!r}")
    version = data.get("version", PROJECT_VERSION)
    if not isinstance(version, int) or version > PROJECT_VERSION:
        raise ProjectError(f"Версия проекта {version!r} не поддерживается.")
    result = _deep_merge(default_project(), data)
    result["format"] = PROJECT_FORMAT
    result["version"] = PROJECT_VERSION
    validate_project(result)
    return result


def validate_project(data: dict[str, Any]) -> None:
    vm = data.get("vm")
    lle = data.get("lle")
    if not isinstance(vm, dict) or not isinstance(lle, dict):
        raise ProjectError("Проект должен содержать объекты vm и lle.")
    if not isinstance(vm.get("memoryMiB"), int) or vm["memoryMiB"] < 16:
        raise ProjectError("vm.memoryMiB должен быть целым числом не меньше 16.")
    cpu = vm.get("cpu")
    if not isinstance(cpu, dict):
        raise ProjectError("vm.cpu должен быть объектом.")
    for field in ("cores", "sockets", "threads"):
        if not isinstance(cpu.get(field), int) or cpu[field] < 1:
            raise ProjectError(f"vm.cpu.{field} должен быть положительным целым числом.")
    disks = vm.get("storage", {}).get("disks")
    if not isinstance(disks, list):
        raise ProjectError("vm.storage.disks должен быть массивом.")
    firmware = vm.get("firmware")
    if not isinstance(firmware, dict):
        raise ProjectError("vm.firmware должен быть объектом.")
    if firmware.get("mode") not in {"default", "bios", "uefi"}:
        raise ProjectError("vm.firmware.mode должен быть default, bios или uefi.")
    if firmware.get("pflashFormat") not in {"raw", "qcow2"}:
        raise ProjectError("vm.firmware.pflashFormat должен быть raw или qcow2.")
    security = vm.get("security")
    if not isinstance(security, dict):
        raise ProjectError("vm.security должен быть объектом.")
    if security.get("profile") not in {"balanced", "strict", "custom"}:
        raise ProjectError("vm.security.profile должен быть balanced, strict или custom.")
    lock_until = security.get("sandboxLockUntil", 0)
    if not isinstance(lock_until, (int, float)) or isinstance(lock_until, bool) or lock_until < 0:
        raise ProjectError("vm.security.sandboxLockUntil должен быть неотрицательным Unix timestamp.")
    tracing = vm.get("tracing")
    if not isinstance(tracing, dict):
        raise ProjectError("vm.tracing должен быть объектом.")
    if tracing.get("preset") not in {"translation", "instructions", "diagnostics", "custom"}:
        raise ProjectError("vm.tracing.preset имеет неизвестное значение.")
    for name in ("deviceModels", "requiredQemuDevices", "requiredModules"):
        if not isinstance(lle.get(name), list):
            raise ProjectError(f"lle.{name} должен быть массивом.")
    if not isinstance(lle.get("firmware", {}).get("roms"), list):
        raise ProjectError("lle.firmware.roms должен быть массивом.")


def load_project(path: str | Path) -> dict[str, Any]:
    project_path = Path(path)
    try:
        data = json.loads(project_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectError(f"Не удалось открыть проект: {exc}") from exc
    return normalize_project(data)


def save_project(path: str | Path, data: dict[str, Any]) -> Path:
    project_path = Path(path)
    if project_path.suffix.lower() != PROJECT_EXTENSION:
        project_path = project_path.with_suffix(PROJECT_EXTENSION)
    normalized = normalize_project(data)
    try:
        project_path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        raise ProjectError(f"Не удалось сохранить проект: {exc}") from exc
    return project_path


@dataclass(frozen=True)
class ProjectContext:
    project_file: Path | None = None

    @property
    def base_dir(self) -> Path:
        return self.project_file.parent if self.project_file else Path.cwd()

    def resolve(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.base_dir / path
