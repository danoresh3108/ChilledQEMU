from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_DISK_FORMATS = ("qcow2", "raw", "vmdk", "vdi")


class DiskImageError(RuntimeError):
    pass


@dataclass(frozen=True)
class CreatedDiskImage:
    path: Path
    format: str
    size_mib: int
    qemu_img: str
    output: str


def find_qemu_img(qemu_binary: str = "") -> str | None:
    candidates: list[Path] = []
    if qemu_binary:
        binary_path = Path(qemu_binary).expanduser()
        resolved = binary_path if binary_path.is_file() else None
        if not resolved:
            located = shutil.which(qemu_binary)
            resolved = Path(located) if located else None
        if resolved:
            candidates.append(resolved.resolve().with_name("qemu-img"))
            candidates.append(resolved.parent / "qemu-img")
    located_img = shutil.which("qemu-img")
    if located_img:
        candidates.append(Path(located_img))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    return None


def create_disk_image(
    path: str | Path,
    image_format: str,
    size_mib: int,
    qemu_binary: str = "",
    timeout: float = 60.0,
) -> CreatedDiskImage:
    target = Path(path).expanduser()
    image_format = image_format.strip().lower()
    if image_format not in SUPPORTED_DISK_FORMATS:
        raise DiskImageError(f"Неподдерживаемый формат образа: {image_format}")
    if not isinstance(size_mib, int) or size_mib < 1:
        raise DiskImageError("Размер диска должен быть положительным целым числом MiB.")
    if target.exists():
        raise DiskImageError(f"Файл уже существует: {target}")
    if not target.parent.is_dir():
        raise DiskImageError(f"Родительская папка не существует: {target.parent}")
    qemu_img = find_qemu_img(qemu_binary)
    if not qemu_img:
        raise DiskImageError("qemu-img не найден. Установите QEMU или укажите QEMU binary на вкладке «Основное».")
    command = [qemu_img, "create", "-f", image_format, str(target), f"{size_mib}M"]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DiskImageError(f"Не удалось запустить qemu-img: {exc}") from exc
    output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    if completed.returncode != 0:
        raise DiskImageError(f"qemu-img завершился с кодом {completed.returncode}: {output}")
    if not target.is_file():
        raise DiskImageError("qemu-img сообщил об успехе, но файл образа не появился.")
    return CreatedDiskImage(target.resolve(), image_format, size_mib, qemu_img, output)
