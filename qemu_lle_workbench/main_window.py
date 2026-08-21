from __future__ import annotations

import json
import shlex
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QProcess, QTimer, Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QDesktopServices, QFontDatabase, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog as QtFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox as QtMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .disk import DiskImageError, SUPPORTED_DISK_FORMATS, create_disk_image
from .i18n import (
    language_preference,
    localize_widget_tree,
    restart_application,
    set_language_preference,
    tr,
)
from .project import ProjectContext, ProjectError, default_project, load_project, save_project
from .qemu import (
    NETWORK_MODEL_PRESETS,
    QemuInspector,
    SOUND_CODEC_PRESETS,
    SOUND_MODEL_PRESETS,
    USB_CONTROLLER_PRESETS,
    VIDEO_PRESETS,
    ValidationIssue,
    binary_architecture,
    binary_supports_architecture,
    build_command,
    command_text,
    cpu_presets,
    effective_binary,
    find_firmware,
    machine_presets,
    machine_is_known_for_other_architecture,
    recommended_machine,
    suggested_binary,
    tracing_log_path,
    validate_against_qemu,
)
from .templates import create_template, template_names


STEAM_PROFILE_URL = "https://steamcommunity.com/id/SarovOffical/"


def _lines(widget: QPlainTextEdit) -> list[str]:
    return [line.strip() for line in widget.toPlainText().splitlines() if line.strip()]


def _set_lines(widget: QPlainTextEdit, values: list[Any]) -> None:
    widget.setPlainText("\n".join(str(value) for value in values))


def _combo(combo: QComboBox, value: Any) -> None:
    text = str(value)
    index = combo.findText(text)
    if index < 0:
        combo.addItem(text)
        index = combo.findText(text)
    combo.setCurrentIndex(index)


def _item(text: Any, checked: bool | None = None) -> QTableWidgetItem:
    result = QTableWidgetItem(str(text))
    if checked is not None:
        result.setFlags(result.flags() | Qt.ItemIsUserCheckable)
        result.setCheckState(Qt.Checked if checked else Qt.Unchecked)
    return result


class QMessageBox(QtMessageBox):
    """Translate every modal message, including dynamically formatted diagnostics."""

    @staticmethod
    def information(parent: QWidget | None, title: str, text: str, *args: Any, **kwargs: Any) -> Any:
        return QtMessageBox.information(parent, tr(title), tr(text), *args, **kwargs)

    @staticmethod
    def warning(parent: QWidget | None, title: str, text: str, *args: Any, **kwargs: Any) -> Any:
        return QtMessageBox.warning(parent, tr(title), tr(text), *args, **kwargs)

    @staticmethod
    def critical(parent: QWidget | None, title: str, text: str, *args: Any, **kwargs: Any) -> Any:
        return QtMessageBox.critical(parent, tr(title), tr(text), *args, **kwargs)

    @staticmethod
    def question(parent: QWidget | None, title: str, text: str, *args: Any, **kwargs: Any) -> Any:
        return QtMessageBox.question(parent, tr(title), tr(text), *args, **kwargs)


class QFileDialog(QtFileDialog):
    @staticmethod
    def getOpenFileName(parent: QWidget | None, caption: str = "", directory: str = "", filter_text: str = "", *args: Any, **kwargs: Any) -> Any:
        return QtFileDialog.getOpenFileName(parent, tr(caption), directory, tr(filter_text), *args, **kwargs)

    @staticmethod
    def getSaveFileName(parent: QWidget | None, caption: str = "", directory: str = "", filter_text: str = "", *args: Any, **kwargs: Any) -> Any:
        return QtFileDialog.getSaveFileName(parent, tr(caption), directory, tr(filter_text), *args, **kwargs)


class PathField(QWidget):
    def __init__(self, caption: str, filter_text: str = "Все файлы (*)") -> None:
        super().__init__()
        self.caption = caption
        self.filter_text = filter_text
        self.edit = QLineEdit()
        button = QPushButton("Обзор…")
        button.clicked.connect(self._browse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(button)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.caption, self.edit.text(), self.filter_text)
        if path:
            self.edit.setText(path)

    def text(self) -> str:
        return self.edit.text().strip()

    def setText(self, value: Any) -> None:
        self.edit.setText(str(value or ""))


class CreateDiskDialog(QDialog):
    def __init__(self, initial_directory: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Создать новый диск")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        path_row = QWidget(); path_layout = QHBoxLayout(path_row); path_layout.setContentsMargins(0, 0, 0, 0)
        self.path_edit = QLineEdit(str(initial_directory / "disk.qcow2"))
        browse = QPushButton("Обзор…"); browse.clicked.connect(self._browse)
        path_layout.addWidget(self.path_edit, 1); path_layout.addWidget(browse)

        self.format_combo = QComboBox(); self.format_combo.addItems(list(SUPPORTED_DISK_FORMATS))
        self.size_spin = QSpinBox(); self.size_spin.setRange(1, 1048576); self.size_spin.setValue(64)
        self.size_unit = QComboBox(); self.size_unit.addItems(["GiB", "MiB"])
        size_row = QWidget(); size_layout = QHBoxLayout(size_row); size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.addWidget(self.size_spin, 1); size_layout.addWidget(self.size_unit)
        self.interface_combo = QComboBox(); self.interface_combo.addItems(["virtio", "nvme", "scsi", "ide", "sd", "usb"])
        self.description_edit = QLineEdit("Системный диск")

        form.addRow("Файл образа", path_row); form.addRow("Формат", self.format_combo)
        form.addRow("Виртуальный размер", size_row); form.addRow("Интерфейс", self.interface_combo)
        form.addRow("Описание", self.description_edit)
        layout.addLayout(form)
        note = QLabel("QCOW2 рекомендуется: образ растёт по мере записи и не занимает весь виртуальный размер сразу.")
        note.setWordWrap(True); layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Создать")
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        localize_widget_tree(self)

    def _browse(self) -> None:
        image_format = self.format_combo.currentText()
        filters = {
            "qcow2": "QCOW2 (*.qcow2)", "raw": "RAW (*.raw *.img)",
            "vmdk": "VMDK (*.vmdk)", "vdi": "VDI (*.vdi)",
        }
        path, _ = QFileDialog.getSaveFileName(
            self, "Создать образ диска", self.path_edit.text(), filters.get(image_format, "Все файлы (*)")
        )
        if path:
            self.path_edit.setText(path)

    def _accept(self) -> None:
        value = self.path_edit.text().strip()
        if not value:
            QMessageBox.warning(self, "Не указан файл", "Выберите путь для нового образа диска.")
            return
        path = self.disk_path()
        if path.exists():
            QMessageBox.warning(self, "Файл уже существует", f"Выберите новое имя: {path}")
            return
        if not path.parent.is_dir():
            QMessageBox.warning(self, "Папка не существует", f"Выберите существующую папку: {path.parent}")
            return
        self.accept()

    def disk_path(self) -> Path:
        path = Path(self.path_edit.text().strip()).expanduser()
        if not path.suffix:
            path = path.with_suffix("." + self.format_combo.currentText())
        return path

    def size_mib(self) -> int:
        multiplier = 1024 if self.size_unit.currentText() == "GiB" else 1
        return self.size_spin.value() * multiplier


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("QEMU LLE Workbench")
        self.resize(1180, 800)
        self.current_file: Path | None = None
        self._detected_vars_template: Path | None = None
        self._sandbox_lock_until = 0.0
        self._sandbox_ui_guard = False
        self._running_with_sandbox = False
        self.dirty = False
        self.loading = False
        self.trace_timer = QTimer(self); self.trace_timer.setInterval(1000)
        self.trace_timer.timeout.connect(self.refresh_trace_log)
        self.sandbox_lock_timer = QTimer(self); self.sandbox_lock_timer.setInterval(1000)
        self.sandbox_lock_timer.timeout.connect(self._update_sandbox_lock)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_process_output)
        self.process.started.connect(self._process_started)
        self.process.finished.connect(self._process_finished)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self._make_general_tab()
        self._make_storage_tab()
        self._make_devices_tab()
        self._make_firmware_tab()
        self._make_security_tab()
        self._make_tracing_tab()
        self._make_advanced_tab()
        self._make_lle_tab()
        self._make_console_tab()
        self._make_actions()
        localize_widget_tree(self)
        self._connect_change_signals()
        self.set_project(default_project())
        self.statusBar().showMessage(tr("Готово"))

    # --- UI construction -------------------------------------------------
    def _make_general_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.binary_field = PathField("Выберите qemu-system-*", "QEMU (qemu-system-*);;Все файлы (*)")
        self.binary_field.edit.setPlaceholderText("Пусто = qemu-system-<architecture> из PATH")
        self.arch_combo = QComboBox()
        self.arch_combo.setEditable(True)
        self.arch_combo.addItems(["x86_64", "i386", "aarch64", "arm", "riscv64", "riscv32", "ppc64", "s390x"])
        self.machine_combo = QComboBox()
        self.machine_combo.setEditable(True)
        self.machine_combo.addItems(machine_presets("x86_64"))
        self.arch_combo.currentTextChanged.connect(self._architecture_changed)
        self.accel_combo = QComboBox()
        self.accel_combo.setEditable(True)
        self.accel_combo.addItems(["hvf", "tcg", "kvm", "whpx", "default"])
        self.cpu_model = QComboBox()
        self.cpu_model.setEditable(True)
        self.cpu_model.addItems(cpu_presets("x86_64"))
        self.cpu_model.setToolTip("Конкретная модель из QEMU -cpu help; можно ввести значение вручную")
        self.cpu_models_button = QPushButton("Из QEMU…")
        self.cpu_models_button.setToolTip("Загрузить точный список моделей из выбранного бинарника QEMU")
        self.cpu_models_button.clicked.connect(self.detect_cpu_models)
        self.cpu_cores = QSpinBox(); self.cpu_cores.setRange(1, 256)
        self.cpu_sockets = QSpinBox(); self.cpu_sockets.setRange(1, 64)
        self.cpu_threads = QSpinBox(); self.cpu_threads.setRange(1, 64)
        cpu_row = QWidget(); cpu_layout = QHBoxLayout(cpu_row); cpu_layout.setContentsMargins(0, 0, 0, 0)
        cpu_layout.addWidget(QLabel("Модель")); cpu_layout.addWidget(self.cpu_model, 1); cpu_layout.addWidget(self.cpu_models_button)
        cpu_layout.addWidget(QLabel("Ядра")); cpu_layout.addWidget(self.cpu_cores)
        cpu_layout.addWidget(QLabel("Сокеты")); cpu_layout.addWidget(self.cpu_sockets)
        cpu_layout.addWidget(QLabel("Потоки")); cpu_layout.addWidget(self.cpu_threads)
        self.memory_spin = QSpinBox(); self.memory_spin.setRange(16, 1048576); self.memory_spin.setSuffix(" MiB")
        form.addRow("Имя ВМ", self.name_edit)
        form.addRow("QEMU binary", self.binary_field)
        form.addRow("Архитектура", self.arch_combo)
        form.addRow("Machine", self.machine_combo)
        form.addRow("Ускоритель", self.accel_combo)
        form.addRow("CPU", cpu_row)
        form.addRow("RAM", self.memory_spin)
        layout.addLayout(form)
        note = QLabel(
            "На macOS обычно используется HVF. Доступность выбранной machine и устройств проверяется "
            "кнопкой «Проверить QEMU / LLE»."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        self.tabs.addTab(page, "Основное")

    def _architecture_changed(self, architecture: str) -> None:
        if self.loading:
            return
        choices = machine_presets(architecture)
        current_machine = self.machine_combo.currentText().strip()
        self.machine_combo.blockSignals(True)
        self.machine_combo.clear(); self.machine_combo.addItems(choices)
        self.machine_combo.setCurrentText(current_machine if current_machine in choices else recommended_machine(architecture))
        self.machine_combo.blockSignals(False)

        current_cpu = self.cpu_model.currentText().strip()
        cpu_choices = cpu_presets(architecture)
        selected_cpu = current_cpu if current_cpu in cpu_choices else cpu_choices[0]
        self._populate_cpu_models(cpu_choices, selected_cpu)

        binary = self.binary_field.text()
        detected = binary_architecture(binary) if binary else None
        if detected and detected != architecture:
            binary_path = Path(binary)
            replacement = binary_path.with_name(suggested_binary(architecture))
            if binary_path.parent == Path("."):
                self.binary_field.setText(suggested_binary(architecture))
            elif replacement.is_file():
                self.binary_field.setText(str(replacement))
        self.statusBar().showMessage(
            f"Architecture={architecture}: machine={self.machine_combo.currentText()}, CPU={self.cpu_model.currentText()}.", 5000
        )

    def _populate_cpu_models(self, models: Any, selected: str = "") -> None:
        values = {str(model).strip() for model in models if str(model).strip()}
        current = selected.strip() or self.cpu_model.currentText().strip()
        ordered = [value for value in ("host", "max") if value in values]
        ordered.extend(sorted(values.difference(ordered), key=str.casefold))
        if current and current not in values:
            ordered.append(current)
        self.cpu_model.blockSignals(True)
        try:
            self.cpu_model.clear()
            self.cpu_model.addItems(ordered)
            if current:
                self.cpu_model.setCurrentText(current)
        finally:
            self.cpu_model.blockSignals(False)

    def _make_storage_tab(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        iso_group = QGroupBox("Установочный / загрузочный ISO")
        iso_layout = QFormLayout(iso_group)
        self.iso_field = PathField("Выберите ISO", "ISO (*.iso);;Все файлы (*)")
        iso_layout.addRow("ISO-образ", self.iso_field)
        layout.addWidget(iso_group)
        disk_group = QGroupBox("Диски")
        disk_layout = QVBoxLayout(disk_group)
        self.disk_table = QTableWidget(0, 6)
        self.disk_table.setHorizontalHeaderLabels(["Путь", "Формат", "Интерфейс", "Только чтение", "Snapshot", "Описание"])
        self.disk_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.disk_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        buttons = QHBoxLayout()
        add_disk = QPushButton("Добавить диск…"); add_disk.clicked.connect(self._add_disk)
        create_disk = QPushButton("Создать диск…"); create_disk.clicked.connect(self._create_disk)
        remove_disk = QPushButton("Удалить выбранные"); remove_disk.clicked.connect(lambda: self._remove_rows(self.disk_table))
        buttons.addWidget(create_disk); buttons.addWidget(add_disk); buttons.addWidget(remove_disk); buttons.addStretch()
        disk_layout.addWidget(self.disk_table); disk_layout.addLayout(buttons)
        layout.addWidget(disk_group, 1)
        self.tabs.addTab(page, "Накопители")

    def _make_devices_tab(self) -> None:
        page = QWidget(); layout = QGridLayout(page)
        network = QGroupBox("Сеть"); form = QFormLayout(network)
        self.net_mode = QComboBox(); self.net_mode.addItems(["user", "none", "tap", "bridge"])
        self.net_model = QComboBox(); self.net_model.setEditable(True); self.net_model.addItems(NETWORK_MODEL_PRESETS)
        self.net_mac = QLineEdit(); self.net_mac.setPlaceholderText("необязательно")
        self.net_interface = QLineEdit(); self.net_interface.setPlaceholderText("tap0")
        self.net_bridge = QLineEdit(); self.net_bridge.setPlaceholderText("br0")
        self.net_forwards = QPlainTextEdit(); self.net_forwards.setMaximumHeight(90)
        self.net_forwards.setPlaceholderText("tcp::2222-:22\nОдна QEMU hostfwd-спецификация на строку")
        form.addRow("Режим", self.net_mode); form.addRow("Модель", self.net_model)
        form.addRow("MAC", self.net_mac); form.addRow("Tap interface", self.net_interface)
        form.addRow("Bridge", self.net_bridge); form.addRow("Проброс портов", self.net_forwards)

        graphics = QGroupBox("Видео и звук"); form2 = QFormLayout(graphics)
        self.video_model = QComboBox(); self.video_model.setEditable(True); self.video_model.addItems(VIDEO_PRESETS)
        self.video_model.setToolTip("virtio выбирает подходящий вариант автоматически; можно выбрать точное имя из QEMU -device help")
        self.display_combo = QComboBox(); self.display_combo.setEditable(True); self.display_combo.addItems(["cocoa", "gtk", "sdl", "none"])
        self.sound_model = QComboBox(); self.sound_model.setEditable(True); self.sound_model.addItems(SOUND_MODEL_PRESETS)
        self.sound_codec = QComboBox(); self.sound_codec.setEditable(True); self.sound_codec.addItems(SOUND_CODEC_PRESETS)
        self.sound_codec.setToolTip("На macOS используйте hda-output: CoreAudio в QEMU не поддерживает захват микрофона")
        self.sound_backend = QComboBox(); self.sound_backend.setEditable(True); self.sound_backend.addItems(["coreaudio", "sdl", "pa", "alsa", "default"])
        form2.addRow("Видео", self.video_model); form2.addRow("Display", self.display_combo)
        form2.addRow("Звуковое устройство", self.sound_model); form2.addRow("HDA-кодек", self.sound_codec)
        form2.addRow("Audio backend", self.sound_backend)

        usb = QGroupBox("USB"); form3 = QFormLayout(usb)
        self.usb_enabled = QCheckBox("Добавить USB-контроллер и устройства")
        self.usb_controller = QComboBox(); self.usb_controller.setEditable(True); self.usb_controller.addItems(USB_CONTROLLER_PRESETS)
        self.usb_devices = QPlainTextEdit(); self.usb_devices.setMaximumHeight(90); self.usb_devices.setPlaceholderText("usb-tablet\nusb-kbd")
        form3.addRow(self.usb_enabled); form3.addRow("Контроллер", self.usb_controller); form3.addRow("Устройства", self.usb_devices)
        load_devices = QPushButton("Загрузить модели устройств из установленного QEMU…")
        load_devices.clicked.connect(self.detect_device_models)
        layout.addWidget(network, 0, 0, 2, 1); layout.addWidget(graphics, 0, 1); layout.addWidget(usb, 1, 1)
        layout.addWidget(load_devices, 2, 0, 1, 2)
        self.tabs.addTab(page, "Устройства")

    def _make_firmware_tab(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        group = QGroupBox("Firmware / BIOS / UEFI"); form = QFormLayout(group)
        self.firmware_mode = QComboBox(); self.firmware_mode.addItems(["default", "bios", "uefi"])
        self.bios_field = PathField("Выберите BIOS/firmware", "BIOS (*.bin *.rom *.fd);;Все файлы (*)")
        self.uefi_code_field = PathField("Выберите UEFI code (например, OVMF_CODE.fd)", "UEFI firmware (*.fd *.bin);;Все файлы (*)")
        self.uefi_vars_field = PathField("Выберите UEFI vars (записываемая копия)", "UEFI NVRAM (*.fd *.bin *.qcow2);;Все файлы (*)")
        self.pflash_format = QComboBox(); self.pflash_format.addItems(["raw", "qcow2"])
        self.uefi_code_readonly = QCheckBox("защитить UEFI code от записи"); self.uefi_code_readonly.setChecked(True)
        self.uefi_vars_readonly = QCheckBox("открыть NVRAM только для чтения")
        self.secure_boot = QCheckBox("проект требует Secure Boot firmware")
        self.smm_enabled = QCheckBox("добавить smm=on к machine (обычно для q35 Secure Boot)")
        self.boot_order = QLineEdit(); self.boot_order.setPlaceholderText("cdn")
        form.addRow("Режим", self.firmware_mode); form.addRow("BIOS", self.bios_field)
        form.addRow("UEFI code", self.uefi_code_field); form.addRow("UEFI vars", self.uefi_vars_field)
        form.addRow("PFlash format", self.pflash_format)
        form.addRow("UEFI code", self.uefi_code_readonly); form.addRow("UEFI vars", self.uefi_vars_readonly)
        form.addRow("Secure Boot", self.secure_boot); form.addRow("SMM", self.smm_enabled)
        form.addRow("Порядок загрузки", self.boot_order)
        layout.addWidget(group)
        actions = QHBoxLayout()
        detect = QPushButton("Найти firmware установленного QEMU"); detect.clicked.connect(self.detect_firmware)
        create_nvram = QPushButton("Создать копию UEFI NVRAM…"); create_nvram.clicked.connect(self.create_nvram_copy)
        actions.addWidget(detect); actions.addWidget(create_nvram); actions.addStretch(); layout.addLayout(actions)
        warning = QLabel(
            "BIOS без выбранного файла использует встроенный BIOS QEMU. Для UEFI нужен code image; vars/NVRAM "
            "должен быть отдельной записываемой копией, а не оригиналом из пакета QEMU/EDK2."
        )
        warning.setWordWrap(True); layout.addWidget(warning); layout.addStretch()
        self.tabs.addTab(page, "Firmware")

    def _make_advanced_tab(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        label = QLabel("Дополнительные аргументы QEMU — один готовый аргумент на строку. Команда запускается без shell.")
        label.setWordWrap(True); layout.addWidget(label)
        self.extra_args = QPlainTextEdit(); self.extra_args.setPlaceholderText("-serial\nstdio\n-no-reboot")
        self.extra_args.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        layout.addWidget(self.extra_args)
        self.tabs.addTab(page, "Дополнительно")

    def _make_security_tab(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        self.security_enabled = QCheckBox("Включить безопасный запуск QEMU")
        layout.addWidget(self.security_enabled)
        intro = QLabel(
            "Этот режим уменьшает поверхность атаки и случайные каналы связи с хостом. Он не делает ВМ "
            "невидимой и не подменяет firmware, драйверы, CPU или GPU для обхода защит."
        )
        intro.setWordWrap(True); layout.addWidget(intro)

        group = QGroupBox("Профиль"); form = QFormLayout(group)
        self.security_profile = QComboBox()
        self.security_profile.addItem("Сбалансированный", "balanced")
        self.security_profile.addItem("Строгая изоляция", "strict")
        self.security_profile.addItem("Пользовательский", "custom")
        self.security_no_user_config = QCheckBox("Не читать пользовательскую конфигурацию QEMU")
        self.security_no_defaults = QCheckBox("Не создавать устройства QEMU по умолчанию")
        self.security_disable_monitor = QCheckBox("Отключить QEMU monitor / QMP")
        self.security_disable_serial = QCheckBox("Отключить serial console")
        self.security_network_isolation = QCheckBox("Полностью отключить сеть гостя")
        self.security_ephemeral_disks = QCheckBox("Не сохранять изменения дисков (snapshot=on)")
        self.security_sandbox = QCheckBox("Добавить QEMU -sandbox (Linux seccomp)")
        self.security_require_sandbox = QCheckBox("Требовать -sandbox для запуска")
        self.security_lock_sandbox = QCheckBox("Запретить отключение sandbox на 10 минут")
        self.security_lock_status = QLabel("Блокировка переключателя не активна.")
        form.addRow("Режим", self.security_profile)
        for checkbox in (
            self.security_no_user_config, self.security_no_defaults, self.security_disable_monitor,
            self.security_disable_serial, self.security_network_isolation,
            self.security_ephemeral_disks,
        ):
            form.addRow(checkbox)
        form.addRow(self.security_sandbox)
        form.addRow(self.security_require_sandbox)
        form.addRow(self.security_lock_sandbox)
        form.addRow("Блокировка", self.security_lock_status)
        layout.addWidget(group)
        platform_note = QLabel(
            "На macOS используется HVF; KVM доступен только на Linux. Seccomp sandbox обычно отсутствует в "
            "Homebrew QEMU, поэтому обязательный режим блокирует запуск, если проверка не пройдена. "
            "10-минутная блокировка — защита интерфейса, а не криптографическая защита файла проекта."
        )
        platform_note.setWordWrap(True); layout.addWidget(platform_note)
        validate = QPushButton("Проверить поддержку текущим QEMU"); validate.clicked.connect(self.validate_qemu)
        layout.addWidget(validate); layout.addStretch()
        self.security_enabled.toggled.connect(self._security_enabled_toggled)
        self.security_profile.currentIndexChanged.connect(self._security_profile_changed)
        self.security_sandbox.toggled.connect(self._sandbox_toggled)
        self.security_require_sandbox.toggled.connect(self._sandbox_required_toggled)
        self.security_lock_sandbox.toggled.connect(self._sandbox_lock_toggled)
        self._security_profile_changed()
        self.tabs.addTab(page, "Безопасность")

    def _make_tracing_tab(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        self.trace_enabled = QCheckBox("Включить трассировку QEMU / TCG")
        layout.addWidget(self.trace_enabled)
        note = QLabel(
            "Выключено по умолчанию для скорости. out_asm показывает машинный код, сгенерированный TCG для "
            "процессора хоста; на этом ARM64 Mac это ARM64-код. Это трассировка инструкций, а не история shell-команд внутри гостевой ОС."
        )
        note.setWordWrap(True); layout.addWidget(note)

        options = QGroupBox("Источники"); grid = QGridLayout(options)
        self.trace_preset = QComboBox()
        self.trace_preset.addItem("Перевод Guest → TCG → ARM64", "translation")
        self.trace_preset.addItem("Выполненные гостевые блоки", "instructions")
        self.trace_preset.addItem("Диагностика устройств/ошибок", "diagnostics")
        self.trace_preset.addItem("Пользовательский", "custom")
        self.trace_force_tcg = QCheckBox("Автоматически использовать TCG для перевода"); self.trace_force_tcg.setChecked(True)
        self.trace_capture_serial = QCheckBox("Показывать serial-вывод гостя в общей консоли")
        grid.addWidget(QLabel("Профиль"), 0, 0); grid.addWidget(self.trace_preset, 0, 1, 1, 3)
        grid.addWidget(self.trace_force_tcg, 1, 0, 1, 2); grid.addWidget(self.trace_capture_serial, 1, 2, 1, 2)

        self.trace_guest_asm = QCheckBox("Guest assembly (in_asm)")
        self.trace_host_asm = QCheckBox("Host assembly (out_asm)")
        self.trace_tcg_ops = QCheckBox("TCG micro-ops (op)")
        self.trace_optimized_ops = QCheckBox("Optimized TCG ops (op_opt)")
        self.trace_exec = QCheckBox("Executed blocks (exec, много данных)")
        self.trace_cpu = QCheckBox("CPU state (cpu, очень много данных)")
        self.trace_interrupts = QCheckBox("Interrupts/exceptions (int)")
        self.trace_cpu_reset = QCheckBox("CPU reset")
        self.trace_unimplemented = QCheckBox("Unimplemented devices")
        self.trace_guest_errors = QCheckBox("Guest errors")
        self.trace_no_chain = QCheckBox("Disable TB chaining (nochain)")
        trace_checks = (
            self.trace_guest_asm, self.trace_host_asm, self.trace_tcg_ops, self.trace_optimized_ops,
            self.trace_exec, self.trace_cpu, self.trace_interrupts, self.trace_cpu_reset,
            self.trace_unimplemented, self.trace_guest_errors, self.trace_no_chain,
        )
        for index, checkbox in enumerate(trace_checks):
            grid.addWidget(checkbox, 2 + index // 2, index % 2 * 2, 1, 2)
        layout.addWidget(options)

        path_row = QWidget(); path_layout = QHBoxLayout(path_row); path_layout.setContentsMargins(0, 0, 0, 0)
        self.trace_log_edit = QLineEdit(); self.trace_log_edit.setPlaceholderText("Пусто = <имя ВМ>.qemu-trace.log рядом с проектом")
        browse = QPushButton("Выбрать…"); browse.clicked.connect(self._browse_trace_log)
        path_layout.addWidget(self.trace_log_edit, 1); path_layout.addWidget(browse)
        self.trace_filter = QLineEdit(); self.trace_filter.setPlaceholderText("Например: 0x40000000..0x4000ffff")
        form = QFormLayout(); form.addRow("Файл журнала", path_row); form.addRow("Фильтр адресов (-dfilter)", self.trace_filter)
        layout.addLayout(form)

        viewer_group = QGroupBox("Просмотр журнала (последние 2 MiB)"); viewer_layout = QVBoxLayout(viewer_group)
        self.trace_log_view = QPlainTextEdit(); self.trace_log_view.setReadOnly(True)
        self.trace_log_view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.trace_log_view.document().setMaximumBlockCount(20000)
        view_buttons = QHBoxLayout()
        refresh = QPushButton("Обновить"); refresh.clicked.connect(self.refresh_trace_log)
        copy = QPushButton("Копировать"); copy.clicked.connect(lambda: QApplication.clipboard().setText(self.trace_log_view.toPlainText()))
        clear = QPushButton("Очистить окно"); clear.clicked.connect(self.trace_log_view.clear)
        view_buttons.addWidget(refresh); view_buttons.addWidget(copy); view_buttons.addWidget(clear); view_buttons.addStretch()
        viewer_layout.addWidget(self.trace_log_view); viewer_layout.addLayout(view_buttons)
        layout.addWidget(viewer_group, 1)
        self.trace_enabled.toggled.connect(self._refresh_tracing_controls)
        self.trace_preset.currentIndexChanged.connect(self._tracing_preset_changed)
        self._tracing_preset_changed()
        self.tabs.addTab(page, "Трассировка")

    def _tracing_preset_changed(self, *_args: Any) -> None:
        profile = self.trace_preset.currentData()
        presets = {
            "translation": (True, True, False, True, False, False, False, False, False, True, False),
            "instructions": (True, False, False, False, True, False, False, False, False, True, True),
            "diagnostics": (False, False, False, False, False, False, True, True, True, True, False),
        }
        checkboxes = self._trace_source_checkboxes()
        if profile in presets:
            for checkbox, value in zip(checkboxes, presets[profile]):
                checkbox.setChecked(value)
        self._refresh_tracing_controls()

    def _trace_source_checkboxes(self) -> tuple[QCheckBox, ...]:
        return (
            self.trace_guest_asm, self.trace_host_asm, self.trace_tcg_ops, self.trace_optimized_ops,
            self.trace_exec, self.trace_cpu, self.trace_interrupts, self.trace_cpu_reset,
            self.trace_unimplemented, self.trace_guest_errors, self.trace_no_chain,
        )

    def _refresh_tracing_controls(self, *_args: Any) -> None:
        enabled = self.trace_enabled.isChecked()
        self.trace_preset.setEnabled(enabled)
        custom = enabled and self.trace_preset.currentData() == "custom"
        for checkbox in self._trace_source_checkboxes():
            checkbox.setEnabled(custom)
        for widget in (self.trace_force_tcg, self.trace_capture_serial, self.trace_log_edit, self.trace_filter):
            widget.setEnabled(enabled)

    def _browse_trace_log(self) -> None:
        initial = self.trace_log_edit.text().strip() or str(self._context().base_dir / "qemu-trace.log")
        path, _ = QFileDialog.getSaveFileName(self, "Файл трассировки QEMU", initial, "Log (*.log);;Все файлы (*)")
        if path:
            self.trace_log_edit.setText(path)

    def refresh_trace_log(self) -> None:
        if not hasattr(self, "trace_log_view"):
            return
        try:
            project = self.collect_project()
            path = tracing_log_path(project, self._context())
            if not path.is_file():
                self.trace_log_view.setPlainText(tr(f"Журнал ещё не создан:\n{path}"))
                return
            max_bytes = 2 * 1024 * 1024
            with path.open("rb") as stream:
                size = path.stat().st_size
                if size > max_bytes:
                    stream.seek(size - max_bytes)
                data = stream.read()
            prefix = tr(f"[Показаны последние {len(data)} из {size} байт]\n") if size > max_bytes else ""
            self.trace_log_view.setPlainText(prefix + data.decode("utf-8", errors="replace"))
            self.trace_log_view.moveCursor(QTextCursor.End)
        except (OSError, ProjectError) as exc:
            self.trace_log_view.setPlainText(tr(f"Не удалось прочитать журнал: {exc}"))

    def _security_profile_changed(self, *_args: Any) -> None:
        profile = self.security_profile.currentData()
        presets = {
            "balanced": (True, False, True, False, False, False),
            "strict": (True, True, True, True, True, True),
        }
        checkboxes = (
            self.security_no_user_config, self.security_no_defaults, self.security_disable_monitor,
            self.security_disable_serial, self.security_network_isolation,
            self.security_ephemeral_disks,
        )
        if profile in presets:
            for checkbox, value in zip(checkboxes, presets[profile]):
                checkbox.setChecked(value)
        self._refresh_security_controls()

    def _refresh_security_controls(self, *_args: Any) -> None:
        enabled = self.security_enabled.isChecked()
        locked = self._sandbox_lock_remaining() > 0
        self.security_enabled.setEnabled(not locked)
        self.security_profile.setEnabled(enabled)
        custom = enabled and self.security_profile.currentData() == "custom"
        for checkbox in (
            self.security_no_user_config, self.security_no_defaults, self.security_disable_monitor,
            self.security_disable_serial, self.security_network_isolation,
            self.security_ephemeral_disks,
        ):
            checkbox.setEnabled(custom)
        self.security_sandbox.setEnabled(enabled and not locked)
        self.security_require_sandbox.setEnabled(not locked)
        self.security_lock_sandbox.setEnabled(not locked)

    def _sandbox_lock_remaining(self) -> int:
        return max(0, int(self._sandbox_lock_until - time.time() + 0.999))

    def _set_sandbox_checkbox(self, checkbox: QCheckBox, checked: bool) -> None:
        self._sandbox_ui_guard = True
        try:
            checkbox.setChecked(checked)
        finally:
            self._sandbox_ui_guard = False

    def _confirm_sandbox_removal(self) -> bool:
        remaining = self._sandbox_lock_remaining()
        if remaining:
            minutes, seconds = divmod(remaining, 60)
            QMessageBox.warning(
                self,
                "Sandbox заблокирован",
                f"Отключение -sandbox запрещено ещё {minutes:02d}:{seconds:02d}.",
            )
            return False
        running = self.process.state() != QProcess.NotRunning and self._running_with_sandbox
        message = (
            "QEMU сейчас работает с -sandbox. Виртуальная машина будет остановлена, а параметр будет "
            "убран из следующих запусков.\n\nВы действительно хотите отключить -sandbox?"
            if running
            else "Параметр -sandbox будет убран из следующих запусков. Это уменьшит изоляцию процесса "
            "QEMU от ядра хоста.\n\nВы действительно хотите отключить -sandbox?"
        )
        answer = QMessageBox.question(
            self,
            "Отключить QEMU sandbox?",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return False
        if running:
            self.stop_qemu()
        return True

    def _security_enabled_toggled(self, checked: bool) -> None:
        if self.loading or self._sandbox_ui_guard:
            self._refresh_security_controls()
            return
        if not checked and (self.security_sandbox.isChecked() or self.security_require_sandbox.isChecked()):
            if not self._confirm_sandbox_removal():
                self._set_sandbox_checkbox(self.security_enabled, True)
            else:
                self._sandbox_ui_guard = True
                try:
                    self.security_require_sandbox.setChecked(False)
                    self.security_sandbox.setChecked(False)
                finally:
                    self._sandbox_ui_guard = False
        self._refresh_security_controls()

    def _sandbox_toggled(self, checked: bool) -> None:
        if self.loading or self._sandbox_ui_guard:
            return
        if checked:
            if not self.security_enabled.isChecked():
                self._set_sandbox_checkbox(self.security_enabled, True)
            self._refresh_security_controls()
            return
        if not self._confirm_sandbox_removal():
            self._set_sandbox_checkbox(self.security_sandbox, True)
        else:
            self._set_sandbox_checkbox(self.security_require_sandbox, False)
        self._refresh_security_controls()

    def _sandbox_required_toggled(self, checked: bool) -> None:
        if self.loading or self._sandbox_ui_guard:
            return
        if not checked and self._sandbox_lock_remaining():
            self._set_sandbox_checkbox(self.security_require_sandbox, True)
            self._confirm_sandbox_removal()
            return
        if checked:
            self._sandbox_ui_guard = True
            try:
                self.security_enabled.setChecked(True)
                self.security_sandbox.setChecked(True)
            finally:
                self._sandbox_ui_guard = False
        self._refresh_security_controls()

    def _sandbox_lock_toggled(self, checked: bool) -> None:
        if self.loading or self._sandbox_ui_guard:
            return
        if checked:
            self._sandbox_lock_until = time.time() + 600
            self._sandbox_ui_guard = True
            try:
                self.security_enabled.setChecked(True)
                self.security_sandbox.setChecked(True)
                self.security_require_sandbox.setChecked(True)
            finally:
                self._sandbox_ui_guard = False
            self.sandbox_lock_timer.start()
        elif self._sandbox_lock_remaining():
            self._set_sandbox_checkbox(self.security_lock_sandbox, True)
            self._confirm_sandbox_removal()
        self._update_sandbox_lock()

    def _update_sandbox_lock(self) -> None:
        remaining = self._sandbox_lock_remaining()
        if remaining:
            minutes, seconds = divmod(remaining, 60)
            self.security_lock_status.setText(tr(f"Отключение запрещено ещё {minutes:02d}:{seconds:02d}"))
            if not self.sandbox_lock_timer.isActive():
                self.sandbox_lock_timer.start()
        else:
            expired = self._sandbox_lock_until > 0
            self._sandbox_lock_until = 0
            self.sandbox_lock_timer.stop()
            self.security_lock_status.setText(tr("Блокировка переключателя не активна."))
            if self.security_lock_sandbox.isChecked():
                self._set_sandbox_checkbox(self.security_lock_sandbox, False)
            if expired and not self.loading:
                self._changed()
        self._refresh_security_controls()

    def _make_lle_tab(self) -> None:
        page = QWidget(); outer = QVBoxLayout(page)
        self.lle_enabled = QCheckBox("Включить LLE-секцию этого проекта")
        outer.addWidget(self.lle_enabled)
        disclaimer = QLabel(
            "LLE здесь — декларация конкретных ROM, модулей, моделей устройств и параметров времени. "
            "Оболочка не превращает произвольное устройство в LLE: совместимость определяется установленной сборкой QEMU и предоставленными моделями/firmware."
        )
        disclaimer.setWordWrap(True); outer.addWidget(disclaimer)
        sub_tabs = QTabWidget(); outer.addWidget(sub_tabs, 1)

        dependencies = QWidget(); dep_layout = QVBoxLayout(dependencies)
        dep_splitter = QSplitter(Qt.Horizontal)
        req_devices_group = QGroupBox("Обязательные QEMU devices"); rd_layout = QVBoxLayout(req_devices_group)
        self.lle_required_devices = QPlainTextEdit(); self.lle_required_devices.setPlaceholderText("isa-debugcon\ncustom-device-name")
        rd_layout.addWidget(self.lle_required_devices)
        modules_group = QGroupBox("Обязательные модули QEMU"); rm_layout = QVBoxLayout(modules_group)
        self.lle_required_modules = QPlainTextEdit(); self.lle_required_modules.setPlaceholderText("ui-cocoa\n/path/to/module.dylib")
        rm_layout.addWidget(self.lle_required_modules)
        dep_splitter.addWidget(req_devices_group); dep_splitter.addWidget(modules_group)
        dep_layout.addWidget(dep_splitter)
        sub_tabs.addTab(dependencies, "Зависимости")

        rom_page = QWidget(); rom_layout = QVBoxLayout(rom_page)
        self.rom_table = QTableWidget(0, 5)
        self.rom_table.setHorizontalHeaderLabels(["Путь", "Тип/роль", "Обязателен", "QEMU args с {path}", "Описание"])
        self.rom_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.rom_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.rom_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        rom_buttons = QHBoxLayout(); add_rom = QPushButton("Добавить ROM…"); add_rom.clicked.connect(self._add_rom)
        del_rom = QPushButton("Удалить выбранные"); del_rom.clicked.connect(lambda: self._remove_rows(self.rom_table))
        rom_buttons.addWidget(add_rom); rom_buttons.addWidget(del_rom); rom_buttons.addStretch()
        rom_layout.addWidget(self.rom_table); rom_layout.addLayout(rom_buttons)
        sub_tabs.addTab(rom_page, "Firmware / ROMs")

        models_page = QWidget(); models_layout = QVBoxLayout(models_page)
        self.model_table = QTableWidget(0, 5)
        self.model_table.setHorizontalHeaderLabels(["Имя", "QEMU device", "Properties (JSON)", "Включён", "Описание"])
        self.model_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.model_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.model_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        model_buttons = QHBoxLayout(); add_model = QPushButton("Добавить модель"); add_model.clicked.connect(self._add_model)
        del_model = QPushButton("Удалить выбранные"); del_model.clicked.connect(lambda: self._remove_rows(self.model_table))
        model_buttons.addWidget(add_model); model_buttons.addWidget(del_model); model_buttons.addStretch()
        models_layout.addWidget(self.model_table); models_layout.addLayout(model_buttons)
        sub_tabs.addTab(models_page, "Модели устройств")

        timing_page = QWidget(); timing_form = QFormLayout(timing_page)
        self.lle_rtc = QLineEdit(); self.lle_rtc.setPlaceholderText("base=utc,clock=host,driftfix=slew")
        self.lle_icount = QLineEdit(); self.lle_icount.setPlaceholderText("shift=auto,align=on,sleep=on")
        self.lle_timing_args = QPlainTextEdit(); self.lle_timing_args.setPlaceholderText("Дополнительные timing/clock аргументы, один токен на строку")
        timing_form.addRow("-rtc", self.lle_rtc); timing_form.addRow("-icount", self.lle_icount); timing_form.addRow("Доп. аргументы", self.lle_timing_args)
        sub_tabs.addTab(timing_page, "Timing / Clock")

        notes_page = QWidget(); notes_layout = QGridLayout(notes_page)
        self.lle_notes = QPlainTextEdit(); self.lle_instructions = QPlainTextEdit()
        notes_layout.addWidget(QLabel("Заметки"), 0, 0); notes_layout.addWidget(QLabel("Инструкции"), 0, 1)
        notes_layout.addWidget(self.lle_notes, 1, 0); notes_layout.addWidget(self.lle_instructions, 1, 1)
        sub_tabs.addTab(notes_page, "Заметки")

        validate_button = QPushButton("Проверить QEMU / LLE"); validate_button.clicked.connect(self.validate_qemu)
        outer.addWidget(validate_button)
        self.tabs.addTab(page, "LLE Project")

    def _make_console_tab(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page)
        command_group = QGroupBox("Собираемая командная строка"); command_layout = QVBoxLayout(command_group)
        self.command_preview = QPlainTextEdit(); self.command_preview.setReadOnly(True); self.command_preview.setMaximumHeight(150)
        self.command_preview.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        command_buttons = QHBoxLayout()
        copy_button = QPushButton("Копировать"); copy_button.clicked.connect(lambda: QApplication.clipboard().setText(self.command_preview.toPlainText()))
        refresh_button = QPushButton("Обновить"); refresh_button.clicked.connect(self.update_command_preview)
        command_buttons.addWidget(copy_button); command_buttons.addWidget(refresh_button); command_buttons.addStretch()
        command_layout.addWidget(self.command_preview); command_layout.addLayout(command_buttons)
        layout.addWidget(command_group)
        self.validation_table = QTableWidget(0, 3); self.validation_table.setHorizontalHeaderLabels(["Статус", "Категория", "Результат"])
        self.validation_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.validation_table.setMaximumHeight(180)
        layout.addWidget(self.validation_table)
        self.console = QPlainTextEdit(); self.console.setReadOnly(True); self.console.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        layout.addWidget(self.console, 1)
        controls = QHBoxLayout()
        self.run_button = QPushButton("Запустить QEMU"); self.run_button.clicked.connect(self.start_qemu)
        self.stop_button = QPushButton("Остановить"); self.stop_button.clicked.connect(self.stop_qemu); self.stop_button.setEnabled(False)
        validate = QPushButton("Проверить QEMU / LLE"); validate.clicked.connect(self.validate_qemu)
        clear = QPushButton("Очистить вывод"); clear.clicked.connect(self.console.clear)
        controls.addWidget(self.run_button); controls.addWidget(self.stop_button); controls.addWidget(validate); controls.addWidget(clear); controls.addStretch()
        layout.addLayout(controls)
        self.tabs.addTab(page, "Запуск и проверка")

    def _make_actions(self) -> None:
        file_menu = self.menuBar().addMenu("Файл")
        new_action = QAction("Новый", self); new_action.setShortcut("Ctrl+N"); new_action.triggered.connect(self.new_project)
        open_action = QAction("Открыть / импортировать…", self); open_action.setShortcut("Ctrl+O"); open_action.triggered.connect(self.open_project)
        save_action = QAction("Сохранить", self); save_action.setShortcut("Ctrl+S"); save_action.triggered.connect(self.save_project)
        save_as_action = QAction("Сохранить / экспортировать как…", self); save_as_action.setShortcut("Ctrl+Shift+S"); save_as_action.triggered.connect(self.save_project_as)
        quit_action = QAction("Выход", self); quit_action.setShortcut("Ctrl+Q"); quit_action.triggered.connect(self.close)
        for action in (new_action, open_action, save_action, save_as_action): file_menu.addAction(action)
        file_menu.addSeparator(); file_menu.addAction(quit_action)
        templates_menu = self.menuBar().addMenu("Заготовки")
        for template_key, label in template_names():
            action = QAction(label, self)
            action.triggered.connect(lambda _checked=False, key=template_key: self.apply_template(key))
            templates_menu.addAction(action)
        run_menu = self.menuBar().addMenu("QEMU")
        run_action = QAction("Запустить", self); run_action.setShortcut("Ctrl+R"); run_action.triggered.connect(self.start_qemu)
        stop_action = QAction("Остановить", self); stop_action.triggered.connect(self.stop_qemu)
        validate_action = QAction("Проверить QEMU / LLE", self); validate_action.triggered.connect(self.validate_qemu)
        run_menu.addAction(run_action); run_menu.addAction(stop_action); run_menu.addAction(validate_action)
        settings_menu = self.menuBar().addMenu("Настройки")
        language_menu = settings_menu.addMenu("Язык")
        language_group = QActionGroup(self); language_group.setExclusive(True)
        self.language_actions: dict[str, QAction] = {}
        for code, label in (("system", "Системный язык"), ("ru", "Русский"), ("en", "English")):
            action = QAction(label, self)
            action.setCheckable(True); action.setData(code)
            action.setChecked(language_preference() == code)
            action.triggered.connect(lambda _checked=False, value=code: self.change_language(value))
            language_group.addAction(action); language_menu.addAction(action)
            self.language_actions[code] = action
        help_menu = self.menuBar().addMenu("Справка")
        steam_action = QAction("Профиль автора в Steam — danya_3108 (danya_31082)", self)
        steam_action.triggered.connect(self.open_steam_profile)
        about_action = QAction("О программе", self); about_action.triggered.connect(self.show_about)
        help_menu.addAction(steam_action); help_menu.addAction(about_action)
        toolbar = QToolBar("Основные действия"); self.addToolBar(toolbar)
        toolbar.addAction(new_action); toolbar.addAction(open_action); toolbar.addAction(save_action)
        toolbar.addSeparator(); toolbar.addAction(run_action); toolbar.addAction(stop_action); toolbar.addAction(validate_action)

    def change_language(self, value: str) -> None:
        if value == language_preference():
            return
        set_language_preference(value)
        for code, action in self.language_actions.items():
            action.setChecked(code == value)
        answer = QMessageBox.question(
            self,
            "Язык изменён",
            "Новый язык будет применён после перезапуска программы. Перезапустить сейчас?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        if self.process.state() != QProcess.NotRunning:
            QMessageBox.warning(self, "QEMU запущен", "Остановите QEMU перед перезапуском программы.")
            return
        if self._confirm_discard():
            restart_application()

    def open_steam_profile(self) -> None:
        QDesktopServices.openUrl(QUrl(STEAM_PROFILE_URL))

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            "О программе",
            "ChilledQEUM 0.8.0\n\n"
            "Рабочая оболочка QEMU с форматом .lleproject.\n\n"
            f"Автор: danya_3108 (danya_31082)\nSteam: {STEAM_PROFILE_URL}",
        )

    def _connect_change_signals(self) -> None:
        for widget in self.findChildren(QLineEdit):
            widget.textChanged.connect(self._changed)
        for widget in self.findChildren(QComboBox):
            widget.currentTextChanged.connect(self._changed)
        for widget in self.findChildren(QSpinBox):
            widget.valueChanged.connect(self._changed)
        for widget in self.findChildren(QCheckBox):
            widget.toggled.connect(self._changed)
        for widget in self.findChildren(QPlainTextEdit):
            if widget not in (self.command_preview, self.console, self.trace_log_view):
                widget.textChanged.connect(self._changed)
        for widget in (self.disk_table, self.rom_table, self.model_table):
            widget.itemChanged.connect(self._changed)

    # --- project serialization ------------------------------------------
    def collect_project(self) -> dict[str, Any]:
        disks: list[dict[str, Any]] = []
        for row in range(self.disk_table.rowCount()):
            path = self._cell(self.disk_table, row, 0)
            if path:
                disks.append({
                    "path": path,
                    "format": self._cell(self.disk_table, row, 1) or "raw",
                    "interface": self._cell(self.disk_table, row, 2) or "virtio",
                    "readOnly": self._checked(self.disk_table, row, 3),
                    "snapshot": self._checked(self.disk_table, row, 4),
                    "description": self._cell(self.disk_table, row, 5),
                })
        roms: list[dict[str, Any]] = []
        for row in range(self.rom_table.rowCount()):
            path = self._cell(self.rom_table, row, 0)
            if path:
                raw_args = self._cell(self.rom_table, row, 3)
                try:
                    qemu_args = shlex.split(raw_args) if raw_args else []
                except ValueError as exc:
                    raise ProjectError(f"ROM, строка {row + 1}: неверные QEMU args: {exc}") from exc
                roms.append({
                    "path": path,
                    "kind": self._cell(self.rom_table, row, 1),
                    "required": self._checked(self.rom_table, row, 2),
                    "enabled": True,
                    "qemuArgs": qemu_args,
                    "description": self._cell(self.rom_table, row, 4),
                })
        models: list[dict[str, Any]] = []
        for row in range(self.model_table.rowCount()):
            name = self._cell(self.model_table, row, 0)
            device = self._cell(self.model_table, row, 1)
            if name or device:
                raw_properties = self._cell(self.model_table, row, 2) or "{}"
                try:
                    properties = json.loads(raw_properties)
                except json.JSONDecodeError as exc:
                    raise ProjectError(f"Модель устройства, строка {row + 1}: properties не являются JSON: {exc}") from exc
                if not isinstance(properties, dict):
                    raise ProjectError(f"Модель устройства, строка {row + 1}: properties должны быть JSON-объектом.")
                models.append({
                    "name": name,
                    "qemuDevice": device,
                    "properties": properties,
                    "enabled": self._checked(self.model_table, row, 3),
                    "description": self._cell(self.model_table, row, 4),
                })
        return {
            "format": "qemu-lle-project",
            "version": 1,
            "name": self.name_edit.text().strip() or "Virtual machine",
            "vm": {
                "qemuBinary": self.binary_field.text(),
                "architecture": self.arch_combo.currentText().strip(),
                "machine": self.machine_combo.currentText().strip(),
                "accelerator": self.accel_combo.currentText().strip(),
                "cpu": {"model": self.cpu_model.currentText().strip(), "cores": self.cpu_cores.value(), "sockets": self.cpu_sockets.value(), "threads": self.cpu_threads.value()},
                "memoryMiB": self.memory_spin.value(),
                "storage": {"disks": disks, "iso": self.iso_field.text()},
                "network": {"mode": self.net_mode.currentText(), "model": self.net_model.currentText(), "mac": self.net_mac.text().strip(), "interface": self.net_interface.text().strip(), "bridge": self.net_bridge.text().strip(), "hostForwards": _lines(self.net_forwards)},
                "video": {"model": self.video_model.currentText(), "display": self.display_combo.currentText()},
                "sound": {"model": self.sound_model.currentText(), "codec": self.sound_codec.currentText(), "backend": self.sound_backend.currentText()},
                "usb": {"enabled": self.usb_enabled.isChecked(), "controller": self.usb_controller.currentText(), "devices": _lines(self.usb_devices)},
                "firmware": {
                    "mode": self.firmware_mode.currentText(),
                    "bios": self.bios_field.text(),
                    "uefiCode": self.uefi_code_field.text(),
                    "uefiVars": self.uefi_vars_field.text(),
                    "pflashFormat": self.pflash_format.currentText(),
                    "uefiCodeReadOnly": self.uefi_code_readonly.isChecked(),
                    "uefiVarsReadOnly": self.uefi_vars_readonly.isChecked(),
                    "secureBoot": self.secure_boot.isChecked(),
                    "smm": self.smm_enabled.isChecked(),
                    "bootOrder": self.boot_order.text().strip(),
                },
                "security": {
                    "enabled": self.security_enabled.isChecked(),
                    "profile": self.security_profile.currentData(),
                    "noUserConfig": self.security_no_user_config.isChecked(),
                    "noDefaults": self.security_no_defaults.isChecked(),
                    "disableMonitor": self.security_disable_monitor.isChecked(),
                    "disableSerial": self.security_disable_serial.isChecked(),
                    "networkIsolation": self.security_network_isolation.isChecked(),
                    "ephemeralDisks": self.security_ephemeral_disks.isChecked(),
                    "sandbox": self.security_sandbox.isChecked(),
                    "sandboxRequired": self.security_require_sandbox.isChecked(),
                    "sandboxLockUntil": self._sandbox_lock_until if self._sandbox_lock_remaining() else 0,
                },
                "tracing": {
                    "enabled": self.trace_enabled.isChecked(),
                    "preset": self.trace_preset.currentData(),
                    "forceTcg": self.trace_force_tcg.isChecked(),
                    "guestAssembly": self.trace_guest_asm.isChecked(),
                    "hostAssembly": self.trace_host_asm.isChecked(),
                    "tcgOps": self.trace_tcg_ops.isChecked(),
                    "optimizedOps": self.trace_optimized_ops.isChecked(),
                    "executedBlocks": self.trace_exec.isChecked(),
                    "cpuState": self.trace_cpu.isChecked(),
                    "interrupts": self.trace_interrupts.isChecked(),
                    "cpuReset": self.trace_cpu_reset.isChecked(),
                    "unimplemented": self.trace_unimplemented.isChecked(),
                    "guestErrors": self.trace_guest_errors.isChecked(),
                    "noChain": self.trace_no_chain.isChecked(),
                    "captureSerial": self.trace_capture_serial.isChecked(),
                    "addressFilter": self.trace_filter.text().strip(),
                    "logFile": self.trace_log_edit.text().strip(),
                },
                "extraArgs": _lines(self.extra_args),
            },
            "lle": {
                "enabled": self.lle_enabled.isChecked(),
                "firmware": {"roms": roms},
                "deviceModels": models,
                "timingClockOptions": {"rtc": self.lle_rtc.text().strip(), "icount": self.lle_icount.text().strip(), "extraArgs": _lines(self.lle_timing_args)},
                "requiredQemuDevices": _lines(self.lle_required_devices),
                "requiredModules": _lines(self.lle_required_modules),
                "notes": self.lle_notes.toPlainText(),
                "instructions": self.lle_instructions.toPlainText(),
            },
        }

    def set_project(self, project: dict[str, Any]) -> None:
        self.loading = True
        corrections: list[str] = []
        try:
            vm = project["vm"]; cpu = vm["cpu"]; storage = vm["storage"]
            architecture = str(vm.get("architecture", "x86_64"))
            machine = str(vm.get("machine", recommended_machine(architecture)))
            if machine_is_known_for_other_architecture(machine, architecture):
                old_machine = machine; machine = recommended_machine(architecture)
                corrections.append(f"machine {old_machine} → {machine}")
            binary = str(vm.get("qemuBinary", ""))
            detected = binary_architecture(binary) if binary else None
            if binary and not binary_supports_architecture(detected, architecture):
                binary_path = Path(binary); replacement = binary_path.with_name(suggested_binary(architecture))
                if binary_path.parent == Path(".") or replacement.is_file():
                    old_binary = binary; binary = str(replacement if binary_path.parent != Path(".") else suggested_binary(architecture))
                    corrections.append(f"QEMU binary {old_binary} → {binary}")
            self.name_edit.setText(project.get("name", "")); self.binary_field.setText(binary)
            _combo(self.arch_combo, architecture); _combo(self.machine_combo, machine); _combo(self.accel_combo, vm.get("accelerator", "default"))
            self._populate_cpu_models(cpu_presets(architecture), str(cpu.get("model", "")))
            self.cpu_cores.setValue(int(cpu.get("cores", 1))); self.cpu_sockets.setValue(int(cpu.get("sockets", 1))); self.cpu_threads.setValue(int(cpu.get("threads", 1)))
            self.memory_spin.setValue(int(vm.get("memoryMiB", 1024))); self.iso_field.setText(storage.get("iso", ""))
            self.disk_table.setRowCount(0)
            for disk in storage.get("disks", []):
                self._insert_disk(disk)
            network = vm["network"]; _combo(self.net_mode, network.get("mode", "user")); _combo(self.net_model, network.get("model", "virtio-net-pci"))
            self.net_mac.setText(network.get("mac", "")); self.net_interface.setText(network.get("interface", "")); self.net_bridge.setText(network.get("bridge", "")); _set_lines(self.net_forwards, network.get("hostForwards", []))
            video = vm["video"]; _combo(self.video_model, video.get("model", "virtio")); _combo(self.display_combo, video.get("display", "cocoa"))
            sound = vm["sound"]; _combo(self.sound_model, sound.get("model", "none")); _combo(self.sound_codec, sound.get("codec", "hda-output")); _combo(self.sound_backend, sound.get("backend", "default"))
            usb = vm["usb"]; self.usb_enabled.setChecked(bool(usb.get("enabled"))); _combo(self.usb_controller, usb.get("controller", "qemu-xhci")); _set_lines(self.usb_devices, usb.get("devices", []))
            firmware = vm["firmware"]
            _combo(self.firmware_mode, firmware.get("mode", "default")); self.bios_field.setText(firmware.get("bios", ""))
            self.uefi_code_field.setText(firmware.get("uefiCode", "")); self.uefi_vars_field.setText(firmware.get("uefiVars", ""))
            _combo(self.pflash_format, firmware.get("pflashFormat", "raw"))
            self.uefi_code_readonly.setChecked(bool(firmware.get("uefiCodeReadOnly", True)))
            self.uefi_vars_readonly.setChecked(bool(firmware.get("uefiVarsReadOnly", False)))
            self.secure_boot.setChecked(bool(firmware.get("secureBoot", False))); self.smm_enabled.setChecked(bool(firmware.get("smm", False)))
            self.boot_order.setText(firmware.get("bootOrder", ""))
            security = vm.get("security", {})
            self.security_enabled.setChecked(bool(security.get("enabled", False)))
            profile_index = self.security_profile.findData(security.get("profile", "balanced"))
            self.security_profile.setCurrentIndex(max(0, profile_index))
            self.security_no_user_config.setChecked(bool(security.get("noUserConfig", True)))
            self.security_no_defaults.setChecked(bool(security.get("noDefaults", False)))
            self.security_disable_monitor.setChecked(bool(security.get("disableMonitor", True)))
            self.security_disable_serial.setChecked(bool(security.get("disableSerial", False)))
            self.security_network_isolation.setChecked(bool(security.get("networkIsolation", False)))
            self.security_ephemeral_disks.setChecked(bool(security.get("ephemeralDisks", False)))
            try:
                self._sandbox_lock_until = max(0.0, float(security.get("sandboxLockUntil", 0)))
            except (TypeError, ValueError):
                self._sandbox_lock_until = 0.0
            lock_active = self._sandbox_lock_remaining() > 0
            sandbox_required = bool(security.get("sandboxRequired", False)) or lock_active
            self.security_enabled.setChecked(bool(security.get("enabled", False)) or sandbox_required)
            self.security_sandbox.setChecked(bool(security.get("sandbox", False)) or sandbox_required)
            self.security_require_sandbox.setChecked(sandbox_required)
            self.security_lock_sandbox.setChecked(lock_active)
            self._update_sandbox_lock()
            tracing = vm.get("tracing", {})
            self.trace_enabled.setChecked(bool(tracing.get("enabled", False)))
            trace_index = self.trace_preset.findData(tracing.get("preset", "translation"))
            self.trace_preset.setCurrentIndex(max(0, trace_index))
            self.trace_force_tcg.setChecked(bool(tracing.get("forceTcg", True)))
            trace_fields = (
                (self.trace_guest_asm, "guestAssembly", True), (self.trace_host_asm, "hostAssembly", True),
                (self.trace_tcg_ops, "tcgOps", False), (self.trace_optimized_ops, "optimizedOps", True),
                (self.trace_exec, "executedBlocks", False), (self.trace_cpu, "cpuState", False),
                (self.trace_interrupts, "interrupts", False), (self.trace_cpu_reset, "cpuReset", False),
                (self.trace_unimplemented, "unimplemented", False), (self.trace_guest_errors, "guestErrors", True),
                (self.trace_no_chain, "noChain", False),
            )
            for checkbox, field, default in trace_fields:
                checkbox.setChecked(bool(tracing.get(field, default)))
            self.trace_capture_serial.setChecked(bool(tracing.get("captureSerial", False)))
            self.trace_filter.setText(str(tracing.get("addressFilter", ""))); self.trace_log_edit.setText(str(tracing.get("logFile", "")))
            self._refresh_tracing_controls()
            _set_lines(self.extra_args, vm.get("extraArgs", []))
            lle = project["lle"]; self.lle_enabled.setChecked(bool(lle.get("enabled"))); _set_lines(self.lle_required_devices, lle.get("requiredQemuDevices", [])); _set_lines(self.lle_required_modules, lle.get("requiredModules", []))
            self.rom_table.setRowCount(0)
            for rom in lle.get("firmware", {}).get("roms", []): self._insert_rom(rom)
            self.model_table.setRowCount(0)
            for model in lle.get("deviceModels", []): self._insert_model(model)
            timing = lle.get("timingClockOptions", {}); self.lle_rtc.setText(timing.get("rtc", "")); self.lle_icount.setText(timing.get("icount", "")); _set_lines(self.lle_timing_args, timing.get("extraArgs", []))
            self.lle_notes.setPlainText(lle.get("notes", "")); self.lle_instructions.setPlainText(lle.get("instructions", ""))
        finally:
            self.loading = False
        self.dirty = bool(corrections); self.update_title(); self.update_command_preview()
        if corrections:
            self.statusBar().showMessage("Исправлена несовместимая конфигурация: " + "; ".join(corrections), 10000)

    # --- rows ------------------------------------------------------------
    def _insert_disk(self, disk: dict[str, Any]) -> None:
        row = self.disk_table.rowCount(); self.disk_table.insertRow(row)
        values = [disk.get("path", ""), disk.get("format", "raw"), disk.get("interface", "virtio")]
        for column, value in enumerate(values): self.disk_table.setItem(row, column, _item(value))
        self.disk_table.setItem(row, 3, _item("", bool(disk.get("readOnly"))))
        self.disk_table.setItem(row, 4, _item("", bool(disk.get("snapshot"))))
        self.disk_table.setItem(row, 5, _item(disk.get("description", "")))

    def _add_disk(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите образ диска", "", "Образы (*.qcow2 *.qcow *.raw *.img *.vmdk *.vdi);;Все файлы (*)")
        if path:
            suffix = Path(path).suffix.lower().lstrip("."); fmt = suffix if suffix in {"qcow2", "qcow", "vmdk", "vdi"} else "raw"
            self._insert_disk({"path": path, "format": fmt, "interface": "virtio"}); self._changed()

    def _create_disk(self) -> None:
        dialog = CreateDiskDialog(self._context().base_dir, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            project = self.collect_project()
            qemu_binary = effective_binary(project["vm"])
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                created = create_disk_image(
                    dialog.disk_path(), dialog.format_combo.currentText(), dialog.size_mib(), qemu_binary
                )
            finally:
                QApplication.restoreOverrideCursor()
        except (DiskImageError, ProjectError) as exc:
            QMessageBox.critical(self, "Не удалось создать диск", str(exc))
            return
        self._insert_disk(
            {
                "path": str(created.path),
                "format": created.format,
                "interface": dialog.interface_combo.currentText(),
                "readOnly": False,
                "snapshot": False,
                "description": dialog.description_edit.text().strip(),
            }
        )
        self._changed()
        self.console.appendPlainText(
            f"[Workbench] Создан диск: {created.path} ({created.format}, {created.size_mib} MiB)\n{created.output}"
        )
        QMessageBox.information(
            self, "Диск создан", f"Образ создан и подключён к ВМ:\n{created.path}\n\nВиртуальный размер: {created.size_mib} MiB"
        )

    def _insert_rom(self, rom: dict[str, Any]) -> None:
        row = self.rom_table.rowCount(); self.rom_table.insertRow(row)
        self.rom_table.setItem(row, 0, _item(rom.get("path", ""))); self.rom_table.setItem(row, 1, _item(rom.get("kind", "rom")))
        self.rom_table.setItem(row, 2, _item("", bool(rom.get("required", True))))
        self.rom_table.setItem(row, 3, _item(shlex.join([str(x) for x in rom.get("qemuArgs", [])])))
        self.rom_table.setItem(row, 4, _item(rom.get("description", "")))

    def _add_rom(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите ROM / firmware", "", "ROM/Firmware (*.rom *.bin *.fd *.elf);;Все файлы (*)")
        if path:
            self._insert_rom({"path": path, "kind": "rom", "required": True, "qemuArgs": []}); self._changed()

    def _insert_model(self, model: dict[str, Any]) -> None:
        row = self.model_table.rowCount(); self.model_table.insertRow(row)
        self.model_table.setItem(row, 0, _item(model.get("name", ""))); self.model_table.setItem(row, 1, _item(model.get("qemuDevice", "")))
        self.model_table.setItem(row, 2, _item(json.dumps(model.get("properties", {}), ensure_ascii=False, separators=(",", ":"))))
        self.model_table.setItem(row, 3, _item("", bool(model.get("enabled", True)))); self.model_table.setItem(row, 4, _item(model.get("description", "")))

    def _add_model(self) -> None:
        self._insert_model({"name": "Device", "qemuDevice": "", "properties": {}, "enabled": True}); self._changed()

    @staticmethod
    def _remove_rows(table: QTableWidget) -> None:
        rows = sorted({index.row() for index in table.selectedIndexes()}, reverse=True)
        for row in rows: table.removeRow(row)

    @staticmethod
    def _cell(table: QTableWidget, row: int, column: int) -> str:
        item = table.item(row, column)
        return item.text().strip() if item else ""

    @staticmethod
    def _checked(table: QTableWidget, row: int, column: int) -> bool:
        item = table.item(row, column)
        return bool(item and item.checkState() == Qt.Checked)

    # --- file actions ----------------------------------------------------
    def apply_template(self, key: str) -> None:
        if self.process.state() != QProcess.NotRunning:
            QMessageBox.warning(self, "QEMU запущен", "Остановите QEMU перед применением заготовки.")
            return
        if not self._confirm_discard():
            return
        try:
            project = create_template(key)
        except ValueError as exc:
            QMessageBox.critical(self, "Ошибка заготовки", str(exc))
            return
        self.current_file = None
        self._detected_vars_template = None
        self.set_project(project)
        self.dirty = True
        self.update_title()
        self.statusBar().showMessage("Заготовка применена — укажите образы и сохраните новый проект.", 8000)

    def _inspect_current_qemu(self):
        try:
            project = self.collect_project()
        except ProjectError as exc:
            QMessageBox.warning(self, "Конфигурация некорректна", str(exc))
            return None, None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            capabilities = QemuInspector().inspect(effective_binary(project["vm"]))
        finally:
            QApplication.restoreOverrideCursor()
        if not capabilities.resolved_binary:
            QMessageBox.critical(self, "QEMU не найден", f"Не найден {capabilities.binary}")
            return None, None
        return project, capabilities

    def detect_cpu_models(self) -> None:
        project, capabilities = self._inspect_current_qemu()
        if not project or not capabilities:
            return
        if not capabilities.cpu_models:
            QMessageBox.warning(
                self,
                "Модели CPU не найдены",
                "Выбранный QEMU не вернул список для -cpu help.",
            )
            return
        selected = self.cpu_model.currentText().strip()
        self._populate_cpu_models(capabilities.cpu_models, selected)
        self.statusBar().showMessage(
            f"Загружено моделей CPU: {len(capabilities.cpu_models)}", 8000
        )
        QMessageBox.information(
            self,
            "Модели CPU загружены",
            f"Бинарник: {capabilities.resolved_binary}\n"
            f"Найдено моделей: {len(capabilities.cpu_models)}\n\n"
            "Выберите конкретную модель в поле CPU.",
        )

    def detect_device_models(self) -> None:
        project, capabilities = self._inspect_current_qemu()
        if not project or not capabilities:
            return

        def merge(combo: QComboBox, values: Any) -> None:
            selected = combo.currentText().strip()
            for value in sorted({str(item).strip() for item in values if str(item).strip()}, key=str.casefold):
                if combo.findText(value) < 0:
                    combo.addItem(value)
            if selected:
                combo.setCurrentText(selected)

        categories = capabilities.device_categories
        network = categories.get("network devices", set())
        displays = categories.get("display devices", set())
        sound = categories.get("sound devices", set())
        codecs = {name for name in sound if name.startswith("hda-")}
        sound_devices = sound.difference(codecs)
        usb_candidates = categories.get("usb devices", set()).union(
            categories.get("controller/bridge/hub devices", set())
        )
        usb_controllers = {
            name for name in usb_candidates
            if "usb" in name.lower() and not name.startswith(("usb-storage", "usb-audio", "usb-net"))
        }

        merge(self.net_model, network)
        merge(self.video_model, displays)
        merge(self.sound_model, sound_devices)
        merge(self.sound_codec, codecs)
        merge(self.usb_controller, usb_controllers)
        merge(self.display_combo, capabilities.display_backends)
        merge(self.sound_backend, capabilities.audio_backends)

        found = len(network) + len(displays) + len(sound) + len(usb_controllers)
        self.statusBar().showMessage(f"Добавлено/проверено моделей устройств: {found}", 8000)
        QMessageBox.information(
            self,
            "Модели устройств загружены",
            f"Бинарник: {capabilities.resolved_binary}\n"
            f"Видео: {len(displays)}, сеть: {len(network)}, звук: {len(sound)}, USB-контроллеры: {len(usb_controllers)}.\n\n"
            "Списки дополнены только моделями, объявленными выбранным QEMU.",
        )

    def detect_firmware(self) -> None:
        project, capabilities = self._inspect_current_qemu()
        if not project or not capabilities:
            return
        firmware = project["vm"]["firmware"]
        bios, code, vars_template = find_firmware(
            capabilities, project["vm"]["architecture"], bool(firmware.get("secureBoot"))
        )
        self._detected_vars_template = vars_template
        mode = firmware.get("mode", "default")
        selected = ""
        if mode == "bios" and bios:
            self.bios_field.setText(str(bios)); selected = f"BIOS: {bios}"
        elif mode == "uefi" and code:
            self.uefi_code_field.setText(str(code)); self.pflash_format.setCurrentText("raw")
            selected = f"UEFI code: {code}"
        details = [f"Найдено firmware-файлов: {len(capabilities.firmware_files)}"]
        if selected:
            details.append(f"Выбрано автоматически: {selected}")
        elif mode == "default":
            details.append("Режим default: пути не изменены.")
        else:
            details.append("Подходящий образ для выбранного режима не найден.")
        if vars_template:
            details.append(f"Шаблон NVRAM: {vars_template}\nИспользуйте «Создать копию UEFI NVRAM…».")
        QMessageBox.information(self, "Firmware установленного QEMU", "\n".join(details))

    def create_nvram_copy(self) -> None:
        template = self._detected_vars_template
        if not template or not template.is_file():
            project, capabilities = self._inspect_current_qemu()
            if not project or not capabilities:
                return
            _bios, _code, template = find_firmware(
                capabilities,
                project["vm"]["architecture"],
                bool(project["vm"]["firmware"].get("secureBoot")),
            )
        if not template or not template.is_file():
            QMessageBox.warning(self, "Шаблон NVRAM не найден", "В установленном QEMU не найден подходящий UEFI vars image.")
            return
        default_name = "UEFI_VARS.fd"
        initial = str(self._context().base_dir / default_name)
        target, _ = QFileDialog.getSaveFileName(self, "Создать записываемую копию UEFI NVRAM", initial, "UEFI NVRAM (*.fd);;Все файлы (*)")
        if not target:
            return
        target_path = Path(target)
        if target_path.resolve() == template.resolve():
            QMessageBox.critical(self, "Нельзя перезаписать шаблон", "Выберите другой путь: оригинал из пакета QEMU должен оставаться неизменным.")
            return
        try:
            shutil.copy2(template, target_path)
        except OSError as exc:
            QMessageBox.critical(self, "Не удалось создать NVRAM", str(exc))
            return
        self.firmware_mode.setCurrentText("uefi"); self.pflash_format.setCurrentText("raw")
        self.uefi_vars_readonly.setChecked(False); self.uefi_vars_field.setText(str(target_path))
        self.statusBar().showMessage(f"Создана записываемая копия NVRAM: {target_path}", 8000)

    def new_project(self) -> None:
        if not self._confirm_discard(): return
        self.current_file = None; self.set_project(default_project()); self.console.clear(); self.validation_table.setRowCount(0)

    def open_project(self) -> None:
        if not self._confirm_discard(): return
        path, _ = QFileDialog.getOpenFileName(self, "Открыть .lleproject", "", "LLE Project (*.lleproject);;JSON (*.json);;Все файлы (*)")
        if not path: return
        try:
            project = load_project(path)
        except ProjectError as exc:
            QMessageBox.critical(self, "Ошибка импорта", str(exc)); return
        self.current_file = Path(path); self.set_project(project); self.statusBar().showMessage(f"Открыт {path}", 5000)

    def save_project(self) -> bool:
        if not self.current_file: return self.save_project_as()
        return self._save_to(self.current_file)

    def save_project_as(self) -> bool:
        initial = str(self.current_file or Path.cwd() / "virtual-machine.lleproject")
        path, _ = QFileDialog.getSaveFileName(self, "Экспортировать .lleproject", initial, "LLE Project (*.lleproject)")
        return self._save_to(Path(path)) if path else False

    def _save_to(self, path: Path) -> bool:
        try:
            actual = save_project(path, self.collect_project())
        except ProjectError as exc:
            QMessageBox.critical(self, "Ошибка сохранения", str(exc)); return False
        self.current_file = actual; self.dirty = False; self.update_title(); self.statusBar().showMessage(tr(f"Сохранено: {actual}"), 5000)
        self.update_command_preview(); return True

    def _confirm_discard(self) -> bool:
        if not self.dirty: return True
        answer = QMessageBox.question(self, "Несохранённые изменения", "Сохранить изменения текущего проекта?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if answer == QMessageBox.Save: return self.save_project()
        return answer == QMessageBox.Discard

    # --- command, validation, process -----------------------------------
    def _context(self) -> ProjectContext:
        return ProjectContext(self.current_file)

    def update_command_preview(self) -> None:
        try:
            command = build_command(self.collect_project(), self._context())
            self.command_preview.setPlainText(command_text(command))
        except (ProjectError, ValueError, TypeError) as exc:
            self.command_preview.setPlainText(tr(f"Ошибка конфигурации: {exc}"))

    def validate_qemu(self) -> list[ValidationIssue]:
        try:
            project = self.collect_project()
        except ProjectError as exc:
            QMessageBox.warning(self, "Конфигурация некорректна", str(exc)); return []
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            capabilities = QemuInspector().inspect(effective_binary(project["vm"]))
            if capabilities.cpu_models:
                self._populate_cpu_models(
                    capabilities.cpu_models, self.cpu_model.currentText().strip()
                )
            issues = validate_against_qemu(project, capabilities, self._context())
        finally:
            QApplication.restoreOverrideCursor()
        self._show_issues(issues)
        warnings = sum(issue.severity == "warning" for issue in issues); errors = sum(issue.severity == "error" for issue in issues)
        self.statusBar().showMessage(tr(f"Проверка завершена: ошибок {errors}, предупреждений {warnings}"), 8000)
        self.tabs.setCurrentWidget(self.validation_table.parentWidget())
        return issues

    def _show_issues(self, issues: list[ValidationIssue]) -> None:
        self.validation_table.setRowCount(0)
        symbols = {"ok": "✓", "warning": "⚠", "error": "✕"}
        for issue in issues:
            row = self.validation_table.rowCount(); self.validation_table.insertRow(row)
            self.validation_table.setItem(row, 0, _item(symbols.get(issue.severity, issue.severity)))
            self.validation_table.setItem(row, 1, _item(tr(issue.category))); self.validation_table.setItem(row, 2, _item(tr(issue.message)))

    def start_qemu(self) -> None:
        if self.process.state() != QProcess.NotRunning: return
        try:
            project = self.collect_project(); command = build_command(project, self._context())
        except (ProjectError, ValueError, TypeError) as exc:
            QMessageBox.critical(self, "Нельзя запустить", str(exc)); return
        issues = self.validate_qemu()
        if any(issue.severity == "error" for issue in issues):
            QMessageBox.critical(self, "QEMU недоступен", "Исправьте ошибки проверки перед запуском."); return
        warnings = [issue.message for issue in issues if issue.severity == "warning"]
        if warnings:
            answer = QMessageBox.warning(self, "Есть предупреждения", "\n".join(warnings[:8]) + "\n\nВсё равно запустить QEMU?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes: return
        sandbox_required = bool(project["vm"].get("security", {}).get("sandboxRequired"))
        sandbox_values = [
            command[index + 1]
            for index, token in enumerate(command[:-1])
            if token in {"-sandbox", "--sandbox"}
        ]
        expected_sandbox = "on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny"
        if sandbox_required and (not sandbox_values or sandbox_values[-1] != expected_sandbox):
            QMessageBox.critical(
                self,
                "Нельзя запустить",
                "Внутренняя проверка безопасности: обязательный -sandbox отсутствует или переопределён в команде.",
            )
            return
        self.console.appendPlainText(f"$ {command_text(command)}\n")
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        self._running_with_sandbox = "-sandbox" in command
        self.process.setProgram(command[0]); self.process.setArguments(command[1:]); self.process.setWorkingDirectory(str(self._context().base_dir)); self.process.start()

    def stop_qemu(self) -> None:
        if self.process.state() == QProcess.NotRunning: return
        self.console.appendPlainText(tr("\n[Workbench] Отправлен запрос на завершение QEMU…"))
        self.process.terminate()
        QTimer.singleShot(3000, self._kill_if_running)

    def _kill_if_running(self) -> None:
        if self.process.state() != QProcess.NotRunning:
            self.console.appendPlainText(tr("[Workbench] QEMU не завершился за 3 секунды; процесс принудительно остановлен."))
            self.process.kill()

    def _read_process_output(self) -> None:
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self.console.moveCursor(QTextCursor.End); self.console.insertPlainText(data); self.console.ensureCursorVisible()

    def _process_started(self) -> None:
        self.run_button.setEnabled(False); self.stop_button.setEnabled(True); self.statusBar().showMessage(tr(f"QEMU запущен, PID {self.process.processId()}"))
        try:
            if self.collect_project()["vm"]["tracing"]["enabled"]:
                self.trace_timer.start()
        except ProjectError:
            pass

    def _process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self.trace_timer.stop(); self.refresh_trace_log()
        self._running_with_sandbox = False
        self.console.appendPlainText(tr(f"\n[Workbench] QEMU завершён: код {exit_code}, статус {exit_status.name}."))
        self.run_button.setEnabled(True); self.stop_button.setEnabled(False); self.statusBar().showMessage(tr("QEMU остановлен"), 5000)

    # --- lifecycle -------------------------------------------------------
    def _changed(self, *_args: Any) -> None:
        if self.loading: return
        self.dirty = True; self.update_title(); self.update_command_preview()

    def update_title(self) -> None:
        name = self.current_file.name if self.current_file else tr("Новый проект")
        self.setWindowTitle(f"{'*' if self.dirty else ''}{name} — QEMU LLE Workbench")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.process.state() != QProcess.NotRunning:
            answer = QMessageBox.question(self, "QEMU запущен", "Остановить QEMU и выйти?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes: event.ignore(); return
            self.process.kill(); self.process.waitForFinished(1500)
        if self._confirm_discard(): event.accept()
        else: event.ignore()
