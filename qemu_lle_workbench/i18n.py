from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QLocale, QProcess, QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QTabWidget,
    QTableWidget,
    QWidget,
)


ORGANIZATION = "ChilledQEUM"
APPLICATION = "ChilledQEUM"
LANGUAGE_KEY = "ui/language"
SUPPORTED_LANGUAGES = {"system", "ru", "en"}


ENGLISH: dict[str, str] = {
    "Готово": "Ready",
    "Все файлы": "All files",
    "Обзор…": "Browse…",
    "Выбрать…": "Choose…",
    "Создать": "Create",
    "Создать новый диск": "Create a new disk",
    "Создать образ диска": "Create disk image",
    "Системный диск": "System disk",
    "Файл образа": "Image file",
    "Формат": "Format",
    "Виртуальный размер": "Virtual size",
    "Интерфейс": "Interface",
    "Описание": "Description",
    "QCOW2 рекомендуется: образ растёт по мере записи и не занимает весь виртуальный размер сразу.": "QCOW2 is recommended: the image grows as data is written and does not immediately occupy its full virtual size.",
    "Не указан файл": "No file selected",
    "Выберите путь для нового образа диска.": "Choose a path for the new disk image.",
    "Файл уже существует": "File already exists",
    "Выберите новое имя": "Choose a new name",
    "Папка не существует": "Folder does not exist",
    "Выберите существующую папку": "Choose an existing folder",
    "Выберите qemu-system-*": "Choose qemu-system-*",
    "Пусто = qemu-system-<architecture> из PATH": "Empty = qemu-system-<architecture> from PATH",
    "Конкретная модель из QEMU -cpu help; можно ввести значение вручную": "A model from QEMU -cpu help; you can also enter one manually",
    "Из QEMU…": "From QEMU…",
    "Загрузить точный список моделей из выбранного бинарника QEMU": "Load the exact model list from the selected QEMU binary",
    "Модель": "Model",
    "Ядра": "Cores",
    "Сокеты": "Sockets",
    "Потоки": "Threads",
    "Имя ВМ": "VM name",
    "Архитектура": "Architecture",
    "Ускоритель": "Accelerator",
    "На macOS обычно используется HVF. Доступность выбранной machine и устройств проверяется кнопкой «Проверить QEMU / LLE».": "HVF is normally used on macOS. Use “Validate QEMU / LLE” to verify the selected machine and devices.",
    "Основное": "General",
    "Установочный / загрузочный ISO": "Installation / boot ISO",
    "Выберите ISO": "Choose ISO",
    "ISO-образ": "ISO image",
    "Диски": "Disks",
    "Путь": "Path",
    "Только чтение": "Read only",
    "Добавить диск…": "Add disk…",
    "Создать диск…": "Create disk…",
    "Удалить выбранные": "Remove selected",
    "Накопители": "Storage",
    "Сеть": "Network",
    "необязательно": "optional",
    "Одна QEMU hostfwd-спецификация на строку": "One QEMU hostfwd specification per line",
    "Режим": "Mode",
    "Проброс портов": "Port forwarding",
    "Видео и звук": "Video and audio",
    "Видео": "Video",
    "Звуковое устройство": "Audio device",
    "HDA-кодек": "HDA codec",
    "virtio выбирает подходящий вариант автоматически; можно выбрать точное имя из QEMU -device help": "virtio selects an architecture-appropriate option automatically; an exact QEMU -device help name can be entered",
    "На macOS используйте hda-output: CoreAudio в QEMU не поддерживает захват микрофона": "On macOS use hda-output: QEMU CoreAudio does not support microphone capture",
    "Добавить USB-контроллер и устройства": "Add USB controller and devices",
    "Контроллер": "Controller",
    "Устройства": "Devices",
    "Загрузить модели устройств из установленного QEMU…": "Load device models from installed QEMU…",
    "Выберите BIOS/firmware": "Choose BIOS/firmware",
    "Выберите UEFI code (например, OVMF_CODE.fd)": "Choose UEFI code (for example OVMF_CODE.fd)",
    "Выберите UEFI vars (записываемая копия)": "Choose UEFI vars (writable copy)",
    "защитить UEFI code от записи": "protect UEFI code from writes",
    "открыть NVRAM только для чтения": "open NVRAM read-only",
    "проект требует Secure Boot firmware": "project requires Secure Boot firmware",
    "добавить smm=on к machine (обычно для q35 Secure Boot)": "add smm=on to machine (normally for q35 Secure Boot)",
    "Порядок загрузки": "Boot order",
    "Найти firmware установленного QEMU": "Find firmware from installed QEMU",
    "Создать копию UEFI NVRAM…": "Create UEFI NVRAM copy…",
    "BIOS без выбранного файла использует встроенный BIOS QEMU. Для UEFI нужен code image; vars/NVRAM должен быть отдельной записываемой копией, а не оригиналом из пакета QEMU/EDK2.": "BIOS mode without a selected file uses QEMU's built-in BIOS. UEFI requires a code image; vars/NVRAM must be a separate writable copy, not the original from QEMU/EDK2.",
    "Дополнительные аргументы QEMU — один готовый аргумент на строку. Команда запускается без shell.": "Additional QEMU arguments — one complete argument per line. The command runs without a shell.",
    "Дополнительно": "Advanced",
    "Включить безопасный запуск QEMU": "Enable hardened QEMU launch",
    "Профиль": "Profile",
    "Сбалансированный": "Balanced",
    "Строгая изоляция": "Strict isolation",
    "Пользовательский": "Custom",
    "Отключить сеть гостя": "Disable guest network",
    "Временные записи дисков (snapshot=on)": "Ephemeral disk writes (snapshot=on)",
    "Добавить QEMU -sandbox": "Add QEMU -sandbox",
    "Требовать -sandbox для запуска": "Require -sandbox for launch",
    "Запретить отключение sandbox на 10 минут": "Prevent disabling sandbox for 10 minutes",
    "Блокировка переключателя не активна.": "The switch lock is not active.",
    "Блокировка": "Lock",
    "Не читать пользовательскую конфигурацию QEMU": "Do not read QEMU user configuration",
    "Не создавать устройства QEMU по умолчанию": "Do not create default QEMU devices",
    "Отключить QEMU monitor / QMP": "Disable QEMU monitor / QMP",
    "Отключить serial console": "Disable serial console",
    "Полностью отключить сеть гостя": "Completely disable guest network",
    "Не сохранять изменения дисков (snapshot=on)": "Do not persist disk changes (snapshot=on)",
    "Проверить поддержку текущим QEMU": "Validate support with the current QEMU",
    "Этот режим уменьшает поверхность атаки и случайные каналы связи с хостом. Он не делает ВМ невидимой и не подменяет firmware, драйверы, CPU или GPU для обхода защит.": "This mode reduces attack surface and accidental host communication channels. It does not make the VM invisible or replace firmware, drivers, CPU, or GPU to bypass protections.",
    "На macOS используется HVF; KVM доступен только на Linux. Seccomp sandbox обычно отсутствует в Homebrew QEMU, поэтому обязательный режим блокирует запуск, если проверка не пройдена. 10-минутная блокировка — защита интерфейса, а не криптографическая защита файла проекта.": "macOS uses HVF; KVM is available only on Linux. The seccomp sandbox is normally unavailable in Homebrew QEMU, so required mode blocks launch when validation fails. The 10-minute lock protects the UI; it is not cryptographic protection for the project file.",
    "Безопасность": "Security",
    "Включить трассировку QEMU (замедляет ВМ)": "Enable QEMU tracing (slows down the VM)",
    "Включить трассировку QEMU / TCG": "Enable QEMU / TCG tracing",
    "Автоматически использовать TCG для перевода": "Automatically use TCG for translation",
    "Источники": "Sources",
    "Executed blocks (exec, много данных)": "Executed blocks (exec, high volume)",
    "CPU state (cpu, очень много данных)": "CPU state (cpu, very high volume)",
    "Выключено по умолчанию для скорости. out_asm показывает машинный код, сгенерированный TCG для процессора хоста; на этом ARM64 Mac это ARM64-код. Это трассировка инструкций, а не история shell-команд внутри гостевой ОС.": "Disabled by default for performance. out_asm shows machine code generated by TCG for the host CPU; on an ARM64 Mac this is ARM64 code. This traces instructions, not shell-command history inside the guest OS.",
    "Перевод Guest → TCG → Host": "Guest → TCG → Host translation",
    "Инструкции / блоки": "Instructions / blocks",
    "Диагностика устройств": "Device diagnostics",
    "Принудительно использовать TCG для полного перевода": "Force TCG for complete translation",
    "Показывать serial-вывод гостя в общей консоли": "Show guest serial output in the main console",
    "Пусто = <имя ВМ>.qemu-trace.log рядом с проектом": "Empty = <VM name>.qemu-trace.log next to the project",
    "Например": "For example",
    "Файл журнала": "Log file",
    "Фильтр адресов": "Address filter",
    "Просмотр журнала (последние 2 MiB)": "Log viewer (last 2 MiB)",
    "Обновить": "Refresh",
    "Копировать": "Copy",
    "Очистить окно": "Clear view",
    "Трассировка": "Tracing",
    "Включить LLE-секцию этого проекта": "Enable this project's LLE section",
    "LLE здесь — декларация конкретных ROM, модулей, моделей устройств и параметров времени. Оболочка не превращает произвольное устройство в LLE: совместимость определяется установленной сборкой QEMU и предоставленными моделями/firmware.": "LLE here declares specific ROMs, modules, device models, and timing parameters. The workbench does not turn arbitrary hardware into LLE; compatibility depends on the installed QEMU build and supplied models/firmware.",
    "Обязательные QEMU devices": "Required QEMU devices",
    "Обязательные модули QEMU": "Required QEMU modules",
    "Зависимости": "Dependencies",
    "Тип/роль": "Type/role",
    "QEMU args с {path}": "QEMU args with {path}",
    "Обязателен": "Required",
    "Добавить ROM…": "Add ROM…",
    "Имя": "Name",
    "Включён": "Enabled",
    "Добавить модель": "Add model",
    "Модели устройств": "Device models",
    "Доп. аргументы": "Extra arguments",
    "Дополнительные timing/clock аргументы, один токен на строку": "Additional timing/clock arguments, one token per line",
    "Заметки": "Notes",
    "Инструкции": "Instructions",
    "Проверить QEMU / LLE": "Validate QEMU / LLE",
    "Собираемая командная строка": "Generated command line",
    "Статус": "Status",
    "Категория": "Category",
    "Результат": "Result",
    "Запустить QEMU": "Start QEMU",
    "Запустить": "Start",
    "Остановить": "Stop",
    "Очистить вывод": "Clear output",
    "Запуск и проверка": "Run and validation",
    "Файл": "File",
    "Новый": "New",
    "Открыть / импортировать…": "Open / import…",
    "Сохранить": "Save",
    "Сохранить / экспортировать как…": "Save / export as…",
    "Выход": "Quit",
    "Заготовки": "Templates",
    "LLE — каркас проекта": "LLE — project scaffold",
    "Безопасность — изолированная лаборатория": "Security — isolated lab",
    "Основные действия": "Main actions",
    "Настройки": "Settings",
    "Язык": "Language",
    "Системный язык": "Use system language",
    "Русский": "Russian",
    "Перезапустить сейчас": "Restart now",
    "Язык изменён": "Language changed",
    "Новый язык будет применён после перезапуска программы. Перезапустить сейчас?": "The new language will be applied after restarting the application. Restart now?",
    "Справка": "Help",
    "Профиль автора в Steam": "Author's Steam profile",
    "О программе": "About",
    "Рабочая оболочка QEMU с форматом .lleproject.": "A QEMU workbench with the .lleproject format.",
    "Автор": "Author",
    "Не удалось создать диск": "Could not create disk",
    "Диск создан": "Disk created",
    "Образ создан и подключён к ВМ": "The image was created and attached to the VM",
    "Виртуальный размер": "Virtual size",
    "QEMU запущен": "QEMU is running",
    "Остановите QEMU перед применением заготовки.": "Stop QEMU before applying a template.",
    "Ошибка заготовки": "Template error",
    "Заготовка применена — укажите образы и сохраните новый проект.": "Template applied — select images and save the new project.",
    "Конфигурация некорректна": "Invalid configuration",
    "QEMU не найден": "QEMU not found",
    "Не найден": "Not found",
    "Модели CPU не найдены": "CPU models not found",
    "Выбранный QEMU не вернул список для -cpu help.": "The selected QEMU did not return a -cpu help list.",
    "Модели CPU загружены": "CPU models loaded",
    "Модели устройств загружены": "Device models loaded",
    "Бинарник": "Binary",
    "Найдено моделей": "Models found",
    "Выберите конкретную модель в поле CPU.": "Select a specific model in the CPU field.",
    "Списки дополнены только моделями, объявленными выбранным QEMU.": "The lists were extended only with models declared by the selected QEMU.",
    "Firmware установленного QEMU": "Installed QEMU firmware",
    "Шаблон NVRAM не найден": "NVRAM template not found",
    "Нельзя перезаписать шаблон": "Cannot overwrite template",
    "Не удалось создать NVRAM": "Could not create NVRAM",
    "Открыть .lleproject": "Open .lleproject",
    "Экспортировать .lleproject": "Export .lleproject",
    "Ошибка импорта": "Import error",
    "Ошибка сохранения": "Save error",
    "Несохранённые изменения": "Unsaved changes",
    "Сохранить изменения текущего проекта?": "Save changes to the current project?",
    "Ошибка конфигурации": "Configuration error",
    "Проверка завершена": "Validation complete",
    "ошибок": "errors",
    "предупреждений": "warnings",
    "Нельзя запустить": "Cannot start",
    "QEMU недоступен": "QEMU unavailable",
    "Исправьте ошибки проверки перед запуском.": "Fix validation errors before starting.",
    "Есть предупреждения": "Warnings found",
    "Всё равно запустить QEMU?": "Start QEMU anyway?",
    "Отключить QEMU sandbox?": "Disable QEMU sandbox?",
    "Sandbox заблокирован": "Sandbox is locked",
    "Отключение запрещено ещё": "Disabling is locked for another",
    "Новый проект": "New project",
    "Остановить QEMU и выйти?": "Stop QEMU and quit?",
    "QEMU остановлен": "QEMU stopped",
    "Журнал ещё не создан": "The log has not been created yet",
    "Не удалось прочитать журнал": "Could not read the log",
    "Показаны последние": "Showing the last",
    "из": "of",
    "байт": "bytes",
    "Доступен": "Available",
    "Устройство доступно": "Device available",
    "Выбранное устройство": "Selected device",
    "отсутствует в": "is missing from",
    "Используется firmware по умолчанию выбранной machine.": "Using the selected machine's default firmware.",
    "Секция LLE отключена; проверены только базовые параметры.": "The LLE section is disabled; only base settings were validated.",
    "Модель CPU доступна": "CPU model available",
    "CoreAudio в QEMU поддерживает только воспроизведение": "QEMU CoreAudio supports playback only",
    "Выберите hda-output или отключите звук.": "Choose hda-output or disable audio.",
}


def settings() -> QSettings:
    return QSettings(ORGANIZATION, APPLICATION)


def environment_language() -> str | None:
    value = os.environ.get("CHILLEDQEUM_UI_LANGUAGE", "").strip().lower()
    return value if value in SUPPORTED_LANGUAGES else None


def language_preference() -> str:
    environment = environment_language()
    if environment is not None:
        return environment
    value = str(settings().value(LANGUAGE_KEY, "system"))
    return value if value in SUPPORTED_LANGUAGES else "system"


def set_language_preference(value: str) -> None:
    if value not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported UI language: {value}")
    instance = settings()
    instance.setValue(LANGUAGE_KEY, value)
    instance.sync()


def has_language_preference() -> bool:
    return environment_language() is not None or settings().contains(LANGUAGE_KEY)


def effective_language(preference: str | None = None) -> str:
    value = preference or language_preference()
    if value != "system":
        return value
    return "ru" if QLocale.system().language() == QLocale.Language.Russian else "en"


def tr(value: object) -> str:
    text = str(value)
    if effective_language() != "en":
        return text
    if text in ENGLISH:
        return ENGLISH[text]
    for source in sorted(ENGLISH, key=len, reverse=True):
        if len(source) < 6:
            continue
        if source in text:
            text = text.replace(source, ENGLISH[source])
    return text


def ask_first_run_language() -> str:
    if has_language_preference():
        return language_preference()
    box = QMessageBox()
    box.setWindowTitle("Language / Язык")
    box.setText("Choose the application language\nВыберите язык программы")
    system_button = box.addButton("Use system / Системный", QMessageBox.ButtonRole.AcceptRole)
    russian_button = box.addButton("Русский", QMessageBox.ButtonRole.ActionRole)
    english_button = box.addButton("English", QMessageBox.ButtonRole.ActionRole)
    box.exec()
    clicked = box.clickedButton()
    selected = "ru" if clicked is russian_button else "en" if clicked is english_button else "system"
    set_language_preference(selected)
    return selected


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


def localize_widget_tree(root: QWidget) -> None:
    if effective_language() != "en":
        return
    root.setWindowTitle(tr(root.windowTitle()))
    for widget in [root, *root.findChildren(QWidget)]:
        if isinstance(widget, QAbstractButton):
            widget.setText(tr(widget.text()))
        if isinstance(widget, QLabel):
            widget.setText(tr(widget.text()))
        if isinstance(widget, QGroupBox):
            widget.setTitle(tr(widget.title()))
        if isinstance(widget, QLineEdit):
            widget.setPlaceholderText(tr(widget.placeholderText()))
        if isinstance(widget, QPlainTextEdit):
            widget.setPlaceholderText(tr(widget.placeholderText()))
        if widget.toolTip():
            widget.setToolTip(tr(widget.toolTip()))
        if isinstance(widget, QTabWidget):
            for index in range(widget.count()):
                widget.setTabText(index, tr(widget.tabText(index)))
        if isinstance(widget, QTableWidget):
            for column in range(widget.columnCount()):
                item = widget.horizontalHeaderItem(column)
                if item:
                    item.setText(tr(item.text()))
        if isinstance(widget, QMenu):
            widget.setTitle(tr(widget.title()))
    for action in root.findChildren(QAction):
        action.setText(tr(action.text()))


def restart_application() -> bool:
    arguments = list(sys.argv)
    if QApplication.instance() is None:
        return False
    result = QProcess.startDetached(sys.executable, arguments)
    started = result[0] if isinstance(result, tuple) else bool(result)
    if started:
        QApplication.quit()
    return bool(started)
