from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from .project import default_project


def _base(name: str) -> dict[str, Any]:
    project = default_project()
    project["name"] = name
    return project


def _x86_bios() -> dict[str, Any]:
    project = _base("x86_64 BIOS VM")
    project["vm"]["firmware"].update({"mode": "bios", "bios": ""})
    project["vm"]["video"]["model"] = "std"
    return project


def _x86_uefi() -> dict[str, Any]:
    project = _base("x86_64 UEFI VM")
    project["vm"]["firmware"].update({"mode": "uefi", "uefiCode": "", "uefiVars": ""})
    return project


def _x86_secure_boot() -> dict[str, Any]:
    project = _base("x86_64 UEFI Secure Boot VM")
    project["vm"]["firmware"].update(
        {"mode": "uefi", "secureBoot": True, "smm": True, "uefiCode": "", "uefiVars": ""}
    )
    return project


def _aarch64_uefi() -> dict[str, Any]:
    project = _base("AArch64 UEFI VM")
    vm = project["vm"]
    vm.update({"architecture": "aarch64", "machine": "virt", "accelerator": "hvf"})
    vm["firmware"].update({"mode": "uefi", "uefiCode": "", "uefiVars": ""})
    return project


def _aarch64_winpe() -> dict[str, Any]:
    project = _aarch64_uefi()
    project["name"] = "Windows PE ARM64"
    vm = project["vm"]
    vm["memoryMiB"] = 4096
    vm["video"].update({"model": "ramfb", "display": "cocoa"})
    vm["sound"].update({"model": "none", "codec": "hda-output", "backend": "coreaudio"})
    vm["network"]["mode"] = "none"
    vm["firmware"]["bootOrder"] = "cdn"
    return project


def _lle_scaffold() -> dict[str, Any]:
    project = _base("LLE project scaffold")
    project["lle"].update(
        {
            "enabled": True,
            "requiredQemuDevices": ["isa-debugcon"],
            "deviceModels": [
                {
                    "name": "Debug console",
                    "qemuDevice": "isa-debugcon",
                    "properties": {"iobase": "0x402"},
                    "enabled": True,
                    "description": "Replace or extend with the exact model required by the project.",
                }
            ],
            "notes": "Declare exact ROM, module and device-model dependencies before launch.",
            "instructions": "Run QEMU / LLE validation and resolve every warning relevant to the target.",
        }
    )
    return project


def _isolated_lab() -> dict[str, Any]:
    project = _base("Isolated analysis lab")
    project["vm"]["network"]["mode"] = "none"
    project["vm"]["security"].update({"enabled": True, "profile": "strict"})
    project["lle"]["notes"] = (
        "Strict security profile: network disabled and disk writes are ephemeral. "
        "Use balanced mode when changes must persist."
    )
    return project


TEMPLATES: dict[str, tuple[str, Callable[[], dict[str, Any]]]] = {
    "x86_64-bios": ("x86_64 — BIOS (SeaBIOS/default)", _x86_bios),
    "x86_64-uefi": ("x86_64 — UEFI (OVMF/EDK2)", _x86_uefi),
    "x86_64-secure-boot": ("x86_64 — UEFI Secure Boot", _x86_secure_boot),
    "aarch64-uefi": ("AArch64 — UEFI (EDK2)", _aarch64_uefi),
    "aarch64-winpe": ("AArch64 — WinPE/Windows UEFI", _aarch64_winpe),
    "lle-scaffold": ("LLE — каркас проекта", _lle_scaffold),
    "isolated-lab": ("Безопасность — изолированная лаборатория", _isolated_lab),
}


def template_names() -> list[tuple[str, str]]:
    return [(key, label) for key, (label, _factory) in TEMPLATES.items()]


def create_template(key: str) -> dict[str, Any]:
    try:
        _label, factory = TEMPLATES[key]
    except KeyError as exc:
        raise ValueError(f"Неизвестный шаблон: {key}") from exc
    return copy.deepcopy(factory())
