# ChilledQEUM — QEMU LLE Workbench (English)

> **If you speak Russian, scroll down until you reach the [Russian version](#russian-version).**

Hello! ChilledQEUM is more than an easy-to-use QEMU front end: it also exposes advanced emulation controls for demanding projects. Unlike front ends focused only on ordinary high-level device configuration, ChilledQEUM can describe both conventional QEMU models and LLE-oriented requirements such as ROMs, firmware, modules, exact device models, and timing options. With compatible emulation and legally obtained firmware or software, this may help boot closed or proprietary systems. Emulate almost everything—well, not literally everything 😄

Use it freely and responsibly. ChilledQEUM is powerful, and VM escapes may exist as vulnerabilities in QEMU, firmware, guest drivers, or the host stack. They are not a feature or a guaranteed outcome. If you find one, stop testing against third-party systems, preserve the technical details, and report it privately through the affected project's official security process or an authorized bug-bounty program. Security research through HackerOne or another platform is welcome only when the target is in scope and all program rules are followed.

The project owner intends ChilledQEUM to be free for personal and commercial use. However, this repository currently has no explicit `LICENSE` file; one should be added before public redistribution so that the legal permissions are unambiguous.

ChilledQEUM is a desktop QEMU project editor built with Python and PySide6. It creates and edits VM configurations, imports and exports JSON-based `.lleproject` files, previews the exact QEMU command, and starts or stops the QEMU process.

> **LLE capability boundary.** The workbench does not turn arbitrary physical hardware or an ordinary QEMU model into low-level emulation. The LLE section records the requirements of a specific project: ROM/firmware files, devices, modules, and timing settings. Validation compares those requirements with the installed QEMU build and warns about unavailable components. Actual emulation accuracy depends on the selected models implemented by that QEMU build and on valid ROM/firmware files.

## Features

- Architecture, machine, accelerator, exact CPU model, CPU topology, and RAM configuration.
- New disk creation through `qemu-img`, plus existing disk and ISO attachment.
- Built-in or external BIOS and complete UEFI/pflash configuration with separate code and vars/NVRAM images.
- Automatic BIOS/EDK2/OVMF/AAVMF discovery, safe NVRAM copying, and Secure Boot/SMM flags.
- Templates for x86_64 BIOS, regular/Secure Boot UEFI, AArch64 UEFI, WinPE ARM64, and LLE projects.
- Hardened QEMU launch profiles, optional mandatory `-sandbox`, and a ten-minute UI lock that prevents disabling it.
- Optional Guest assembly → TCG → ARM64 host assembly tracing with a live log viewer; disabled by default for speed.
- User/tap/bridge networking, NIC and MAC selection, and host forwarding.
- Extended video selection (`virtio-gpu-pci`, `ramfb`, VGA, and others), display and audio backends, a separate HDA codec, USB controllers, and USB devices.
- Loading the real video/network/audio/USB models and backends advertised by the selected QEMU binary.
- Extra arguments passed directly without a shell.
- A dedicated **LLE Project** tab for ROMs, device models, timing/clock settings, required QEMU devices/modules, notes, and instructions.
- Validation of the executable, version, machine, `-device help`, ROM files, and known module directories.
- Previewing and copying the generated command line.
- Starting and stopping QEMU with combined stdout/stderr output.
- Relative project paths resolved from the `.lleproject` file location.
- A global System/Russian/English language setting selected on first launch.
- A custom application icon and an author link: **danya_3108 (danya_31082)** on [Steam](https://steamcommunity.com/id/SarovOffical/).

## Quick start on macOS

### Ready-to-use DMG

Version 0.7.0 and later provide a universal2 build for Intel and Apple Silicon Macs running macOS 13 or newer. Drag `ChilledQEUM.app` into Applications. Python, pip, PySide6, and Qt are already bundled. QEMU remains an external dependency (`brew install qemu`), but the application adds common Homebrew and MacPorts paths even when launched from Finder. Version 0.8.0 adds the global language selector, the new icon, and the Steam profile link.

On first launch, choose System, Russian, or English. The choice is stored globally and applies to every `.lleproject`. Change it later through **Settings → Language**; the application will offer to restart so the entire UI is updated.

The local build is signed ad hoc and cannot be notarized without an Apple Developer ID. If Gatekeeper blocks it, run this once for that application bundle only:

```bash
xattr -dr com.apple.quarantine /Applications/ChilledQEUM.app
```

### Run from source

Python 3.10+ and QEMU are required. Install QEMU if necessary:

```bash
brew install qemu
```

From the project folder in Terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

For the normal macOS source launch, open the portable `run_macos.command` file. If the folder arrived through Telegram, a browser, or AirDrop and macOS reports that it “is damaged and can't be opened,” remove quarantine from that extracted project folder only:

```bash
cd "/path/to/ChilledQEUM"
xattr -dr com.apple.quarantine .
/bin/zsh "./run_macos.command"
```

To avoid typing the path, type `cd ` with a trailing space, drag the ChilledQEUM folder into Terminal, and press Return. A separate `chmod` command is not required because the launcher repairs its permissions. The `xattr` command above affects only the current extracted folder.

The launcher checks installed Python versions and selects a compatible Python 3.10+. An old interpreter from an active Conda environment will not take over the launch. An incompatible `.venv` is moved to `.venv-incompatible-*`, a fresh environment is created, and pip is upgraded inside it. To force a specific interpreter, use, for example:

```bash
CHILLEDQEUM_PYTHON=/usr/local/bin/python3.12 /bin/zsh "./run_macos.command"
```

PySide6 is installed only when needed. First-launch diagnostics are saved to `launcher.log`; send that file when the window does not appear. The same instructions are available in `ПЕРВЫЙ_ЗАПУСК_MACOS.txt`. You can select QEMU explicitly on the General tab; an empty value uses `qemu-system-<architecture>` from `PATH`.

### Linux and Windows

The code is cross-platform. Create a virtual environment, install `requirements.txt`, and run `python main.py`. Choose a platform-appropriate accelerator/display/audio backend, such as KVM/GTK/ALSA on Linux or WHPX/SDL on Windows. Editable combo boxes also accept values not present in the presets.

## Typical workflow

1. Choose a template from the **Templates** menu or fill in the basic VM settings.
2. Select the architecture and CPU model. **From QEMU…** loads the exact list returned by the selected binary's `-cpu help`.
3. On the Devices tab, click **Load device models from installed QEMU…** to add only models advertised by that build.
4. On Storage, click **Create disk…**, then choose a path, format, virtual size, and interface. Use **Add disk…** for an existing image.
5. For BIOS, leave the image empty to use QEMU's built-in BIOS, or select an external file.
6. For UEFI, click **Find firmware from installed QEMU**, then **Create UEFI NVRAM copy…**. The code image remains read-only while the separate vars image stores guest NVRAM.
7. List every real dependency on the LLE tab. ROM entries may contain QEMU arguments with a `{path}` marker, such as `-option-rom {path}`.
8. Save the project. Relative paths will then be resolved from the `.lleproject` location.
9. Click **Validate QEMU / LLE**. Warnings require review but do not automatically mean incompatibility; a missing binary, CPU, device, or mandatory UEFI code image is a blocking error.
10. Review the generated command and start QEMU.

### CPU selection

**CPU → Model** is an editable combo box. Built-in choices depend on the architecture: Cortex/Neoverse/A64FX models for AArch64, for example, and Intel/AMD generations for x86_64. **From QEMU…** runs `qemu-system-… -cpu help` and replaces the presets with the models actually declared by that binary. Normal QEMU validation also updates the list and reports an unknown selected model as a blocking error.

`host` exposes host CPU capabilities and generally works only when guest and host architectures match and hardware acceleration is available. `max` enables the emulator's broadest feature set and is useful with TCG. A named model such as `cortex-a72`, `Broadwell`, or `EPYC-Milan` is stored in `vm.cpu.model` and emitted as `-cpu <model>`.

### Disk creation

The **Create disk…** dialog invokes `qemu-img` directly without a shell, refuses to overwrite an existing file, and attaches the image to the VM after successful creation. QCOW2, RAW, VMDK, and VDI are supported, with GiB/MiB sizing and virtio/NVMe/SCSI/IDE/SD/USB interfaces. QCOW2 + virtio is the recommended general-purpose choice: the sparse image grows as data is written.

## Templates

Seven templates are available from **Templates**. Importable versions also live in [`examples/templates`](examples/templates):

- `x86_64-bios` — Q35 with QEMU's built-in SeaBIOS/BIOS.
- `x86_64-uefi` — Q35 with regular EDK2/OVMF.
- `x86_64-secure-boot` — Q35 with Secure Boot firmware and SMM.
- `aarch64-uefi` — `virt` machine with AArch64 EDK2.
- `aarch64-winpe` — WinPE/Windows ARM64 using `virt`, UEFI, and `ramfb`; audio and networking remain off until guest drivers are installed.
- `lle-scaffold` — an explicit minimal LLE dependency scaffold.
- `isolated-lab` — a strictly isolated VM with no network and ephemeral disk writes.

Templates intentionally contain no ROM, disk, or firmware images. After applying a UEFI template, run firmware discovery and create your own writable NVRAM copy.

### WinPE ARM64 on macOS

Choose **AArch64 — WinPE/Windows UEFI**, then select the ISO. Run firmware discovery on the Firmware tab. A Homebrew QEMU installation should provide `edk2-aarch64-code.fd` and a template for a writable `edk2-arm-vars.fd` copy. `share/qemu/bios.bin` is x86 SeaBIOS and is rejected for ARM64 Windows.

Leave audio set to `none` for the first boot. For output-only audio, choose an HDA controller, the `hda-output` codec, and the `coreaudio` backend. `hda-duplex` and `hda-micro` request an `adc` input, while QEMU's CoreAudio backend supports playback only; the workbench blocks that invalid combination before launch. Start with `ramfb` for video. `virtio-gpu-pci` is available explicitly, but Windows requires a suitable guest driver.

Changing architecture synchronizes common machine and `qemu-system-*` choices: ARM64 selects `virt`, while x86_64 selects `q35`. Known invalid pairs such as `aarch64 + pc` in older projects are repaired on load and marked as modified. Unknown custom machines are not silently rewritten; they are checked against the real `QEMU -machine help` output.

## Hardened QEMU launch

The Security tab provides one main switch and three profiles:

- **Balanced** — ignores user QEMU configuration and disables monitor/QMP.
- **Strict isolation** — also enables `-nodefaults`, disables serial and networking, and adds `snapshot=on` so guest disk changes are not saved.
- **Custom** — lets you control every restriction separately.

The real QEMU option is `-sandbox`, not `-sandboxing`. Separate controls can add it to any profile and require it for launch. The mandatory policy overrides even `security.enabled=false`: the workbench blocks launch when the final command lacks `-sandbox`, when later arguments override it, or when the selected QEMU binary has no seccomp sandbox support.

Disabling an active sandbox requires confirmation. If QEMU is already running with `-sandbox`, the workbench requests VM shutdown before removing the option from future launches. **Prevent disabling sandbox for 10 minutes** immediately enables hardened launch, `-sandbox`, and the mandatory policy. Disable controls remain locked while the UI shows a countdown. The deadline is stored in `sandboxLockUntil`, so a saved project restores the remaining time after restart.

Sandbox support is checked against the selected binary. Homebrew QEMU on macOS is usually built without the Linux seccomp sandbox, so an unsupported mandatory option blocks launch. Mandatory sandbox mode is therefore primarily useful with a Linux QEMU build that includes seccomp. macOS uses HVF; KVM is available only on Linux. See QEMU's [`-sandbox`, `-nodefaults`, `-no-user-config`, `-monitor`, and `-serial` documentation](https://www.qemu.org/docs/master/system/qemu-manpage.html).

`-sandbox` applies seccomp filtering to the QEMU process and reduces the Linux kernel attack surface. It is one defense layer, not a guarantee that a malicious guest can never attack the host. QEMU also recommends running without root and applying additional host isolation; see [QEMU Security](https://www.qemu.org/docs/master/system/security.html). The ten-minute lock prevents accidental UI changes but cannot protect JSON from manual editing by another program running with the user's permissions.

This mode intentionally does not patch UEFI/BIOS, hide virtual drivers, or misrepresent emulated CPU/GPU models as physical hardware. A physical GPU name is accurate only with real device passthrough on a supported Linux/KVM host; macOS HVF offers no equivalent universal PCI passthrough facility.

## Instruction and ARM64 translation tracing

Tracing is completely disabled by default and adds nothing to normal fast launches. Available profiles include:

- **Guest → TCG → ARM64 translation** — `in_asm`, `out_asm`, optimized TCG operations, and guest errors.
- **Executed guest blocks** — guest assembly plus `exec,nochain`.
- **Diagnostics** — interrupts, CPU reset, unimplemented functionality, and guest errors.
- **Custom** — independent `in_asm`, `out_asm`, `op`, `op_opt`, `exec`, `cpu`, `int`, and other QEMU log items.

With automatic TCG enabled, only the generated command changes: the accelerator becomes `tcg`, and an incompatible `CPU=host` is temporarily replaced with `CPU=max`. On an ARM64 Mac, `out_asm` contains the ARM64 host code actually generated by TCG. QEMU documents `-d`, `-D`, and `-dfilter` in its [invocation guide](https://www.qemu.org/docs/master/system/invocation.html) and dynamic translation in the [TCG documentation](https://www.qemu.org/docs/master/devel/tcg.html).

The viewer refreshes once per second and displays only the final 2 MiB. `exec`, and especially `cpu`, can create gigabyte-sized logs and slow the VM dramatically. `-dfilter` limits the address range. Serial capture displays guest kernel/console output only when the guest is configured for serial; it does not intercept shell-command history inside the guest OS.

## `.lleproject` format, version 1

The file is UTF-8 JSON with this top-level shape:

```json
{
  "format": "qemu-lle-project",
  "version": 1,
  "name": "My VM",
  "vm": {},
  "lle": {}
}
```

Unknown fields survive core-loader normalization, although the current GUI edits only the fields documented below. Newer schema versions are intentionally rejected rather than interpreted incorrectly.

### `vm` section

| Field | Type | Purpose |
|---|---:|---|
| `qemuBinary` | string | Explicit binary path/name; empty selects from architecture |
| `architecture`, `machine`, `accelerator` | string | Guest architecture, QEMU machine, and accelerator |
| `cpu` | object | `model`, `cores`, `sockets`, `threads` |
| `memoryMiB` | integer | RAM in MiB |
| `storage` | object | `iso` and the `disks` array |
| `network` | object | mode/model/MAC/interface/bridge/`hostForwards` |
| `video`, `sound`, `usb` | object | Video, audio (`model`, `codec`, `backend`), and USB configuration |
| `firmware` | object | `default`, `bios`, or `uefi`; BIOS/code/vars, pflash, Secure Boot/SMM, boot order |
| `security` | object | Hardening profile, monitor/network/disk restrictions, and sandbox policy |
| `tracing` | object | TCG/instruction logging, serial capture, address filter, and log path |
| `extraArgs` | string[] | Complete arguments; one array item equals one argv token |

A disk contains `path`, `format`, `interface`, `readOnly`, `snapshot`, and an optional `description`. The generator supports normal QEMU drive interfaces plus special `nvme` and `usb` values that produce a backend and device pair.

`vm.security` contains `enabled`, `profile`, profile restrictions, and three sandbox fields: `sandbox` adds `-sandbox`, `sandboxRequired` forbids launching without it, and `sandboxLockUntil` stores the end of the UI lock as a Unix timestamp (`0` means unlocked). Recommended restrictions are passed as one argv value: `on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny`.

### BIOS and UEFI

The `vm.firmware` object supports:

| Field | Type | Purpose |
|---|---:|---|
| `mode` | string | `default`, `bios`, or `uefi` |
| `bios` | string | External `-bios` image; empty x86 BIOS mode uses QEMU's built-in BIOS |
| `uefiCode` | string | UEFI/EDK2 code image, pflash unit 0 |
| `uefiVars` | string | Separate NVRAM vars image, pflash unit 1 |
| `pflashFormat` | string | `raw` or `qcow2` |
| `uefiCodeReadOnly` | boolean | Adds `readonly=on` to the code image; `true` is recommended |
| `uefiVarsReadOnly` | boolean | Read-only NVRAM; normally `false` for persistent settings |
| `secureBoot` | boolean | Project requirement and extra Secure Boot image diagnostics |
| `smm` | boolean | Adds `smm=on` to `-machine`, normally required by Q35 Secure Boot |
| `bootOrder` | string | QEMU boot order, for example `cdn` |

Discovery checks the real QEMU binary's data directory and common Homebrew/system paths, then filters firmware by architecture and Secure Boot requirements. A vars template is never used as the writable file directly; the NVRAM action copies it to a user-selected location.

### `lle` section

| Field | Type | Purpose |
|---|---:|---|
| `enabled` | boolean | Enables the declared LLE-related command additions |
| `firmware.roms` | object[] | ROM/firmware dependencies |
| `deviceModels` | object[] | Models added with `-device` |
| `timingClockOptions` | object | `rtc`, `icount`, and an `extraArgs` array |
| `requiredQemuDevices` | string[] | Names that must appear in `qemu -device help` |
| `requiredModules` | string[] | Module names or explicit paths |
| `notes`, `instructions` | string | Human-readable project information |

ROM entry:

```json
{
  "path": "roms/card.rom",
  "kind": "option-rom",
  "required": true,
  "enabled": true,
  "qemuArgs": ["-option-rom", "{path}"],
  "description": "ROM supplied separately"
}
```

`qemuArgs` are added only when explicitly declared, and `{path}` is replaced with the resolved absolute path. The workbench does not guess what a ROM is for.

Device-model entry:

```json
{
  "name": "Debug console",
  "qemuDevice": "isa-debugcon",
  "properties": {"iobase": "0x402"},
  "enabled": true,
  "description": "Debug port"
}
```

This becomes `-device isa-debugcon,iobase=0x402`. `qemuDevice` is automatically added to the validation set.

See [`examples/minimal-x86_64.lleproject`](examples/minimal-x86_64.lleproject) for a complete example. Disk/ROM images are intentionally excluded. The example should produce validation warnings until users supply their own legally obtained files.

## LLE dependency validation

Validation runs QEMU `--version`, `-machine help`, and `-device help`, then:

- checks the selected machine;
- checks selected base video/network/audio/USB models against real `-device help`, even when LLE is disabled;
- checks an external BIOS image or confirms use of the built-in x86 BIOS;
- rejects the known x86 `bios.bin` in ARM/AArch64 configurations;
- requires a readable UEFI code image and checks separate vars/NVRAM, write permissions, duplicate paths, Secure Boot build, and SMM;
- checks `requiredQemuDevices` and every enabled `deviceModel`;
- resolves ROMs relative to the project and checks existence/readability;
- searches explicit module paths, `QEMU_MODULE_DIR`, and common `lib/qemu` directories near the binary and Homebrew/system prefixes;
- displays `✓`, `⚠`, or `✕` in the results table.

QEMU does not expose one stable list of every dynamic module across all builds, so module validation is a conservative file search. A statically linked component may produce a false warning; check the actual build rather than treating the warning as proof that the feature is absent.

## Tests

Core tests do not require PySide6 or an installed QEMU:

```bash
python -m unittest discover -s tests -v
python -m compileall -q main.py qemu_lle_workbench tests
```

With QEMU installed, firmware configurations and real guest/host assembly log creation can also be checked. Smoke tests run QEMU headlessly for a short time and clean up temporary NVRAM and log files automatically:

```bash
python -m tests.smoke_firmware
python -m tests.smoke_tracing
```

## Prototype limitations

- The UI does not ship ROMs, UEFI images, or operating systems; disk creation requires `qemu-img` from an installed QEMU.
- USB host-device forwarding and tap/bridge networking may require privileges and manual host configuration.
- Safe hardening is not anti-detection and does not guarantee compatibility with software that forbids VM execution.
- TCG tracing is much slower than HVF/KVM and can fill free storage very quickly.
- Commands are safely assembled as argv without a shell, but users remain responsible for extra QEMU options.
- Stop first sends a normal terminate request, then kills a hung process after three seconds.
- This is an editor/launcher, not a QEMU installer or a substitute for device-specific documentation.

---

<a id="russian-version"></a>

# QEMU LLE Workbench — Russian version

Привет! ChilledQEUM — это не просто простая в использовании оболочка QEMU: она также предоставляет расширенные настройки эмуляции для сложных проектов. В отличие от оболочек, ориентированных только на обычную высокоуровневую настройку устройств, ChilledQEUM позволяет описывать как стандартные модели QEMU, так и LLE-зависимости: ROM, firmware, модули, точные модели устройств и параметры времени. При наличии совместимой реализации и законно полученных firmware или программного обеспечения это может помочь запустить закрытые и проприетарные системы. Эмулируйте почти всё — но всё-таки не буквально всё 😄

Используйте программу свободно и ответственно. ChilledQEUM обладает широкими возможностями, а VM escape может существовать как уязвимость в QEMU, firmware, гостевых драйверах или компонентах хоста. Это не функция и не гарантированный результат. Если вы обнаружили такую ошибку, прекратите проверку на чужих системах, сохраните технические сведения и конфиденциально сообщите о ней через официальный процесс безопасности затронутого проекта или разрешённую bug-bounty программу. Исследования через HackerOne и другие платформы допустимы только для целей, входящих в scope, и при соблюдении всех правил программы.

Владелец проекта намерен разрешить бесплатное личное и коммерческое использование ChilledQEUM. Однако сейчас в репозитории нет отдельного файла `LICENSE`; перед публичным распространением его следует добавить, чтобы юридические разрешения были сформулированы однозначно.

Рабочий настольный прототип редактора проектов QEMU на Python + PySide6. Приложение позволяет создавать и менять конфигурацию ВМ, импортировать/экспортировать её как JSON-файл `.lleproject`, видеть точную команду QEMU и запускать/останавливать процесс.

> **Граница возможностей LLE.** Workbench не превращает произвольное реальное устройство или обычную модель QEMU в low-level emulation. Секция LLE хранит требования конкретного проекта: ROM/firmware, устройства, модули и параметры времени. Кнопка проверки сопоставляет их с установленным QEMU и предупреждает о недостающих компонентах. Фактическая точность эмуляции зависит от реализации выбранных моделей в конкретной сборке QEMU и от корректных ROM/firmware.

## Возможности

- архитектура, machine, accelerator, выбор конкретной модели CPU, топология CPU и RAM;
- создание новых дисков через `qemu-img` и подключение существующих дисков/ISO;
- встроенный/внешний BIOS и полный UEFI/pflash с отдельными code + vars/NVRAM;
- автопоиск BIOS/EDK2/OVMF/AAVMF в установленном QEMU, безопасное копирование NVRAM, Secure Boot/SMM-флаги;
- встроенное меню заготовок для x86_64 BIOS, обычного/Secure Boot UEFI, AArch64 UEFI, WinPE ARM64 и LLE-каркаса;
- профили безопасного запуска QEMU, обязательный `-sandbox` и 10-минутная блокировка его отключения;
- выключенная по умолчанию трассировка Guest assembly → TCG → ARM64 host assembly с живым просмотром журнала;
- user/tap/bridge networking, модель NIC, MAC и host forwarding;
- расширенный выбор видео (`virtio-gpu-pci`, `ramfb`, VGA и другие), display, звук с отдельным HDA-кодеком, USB-контроллер и USB-устройства;
- загрузка фактических моделей видео/сети/звука/USB и backend из установленного QEMU;
- дополнительные аргументы без запуска через shell;
- отдельная вкладка **LLE Project**: ROM, device models, timing/clock, обязательные QEMU devices/modules, заметки и инструкции;
- проверка бинарника, версии, machine, `-device help`, ROM-файлов и известных каталогов модулей;
- предпросмотр и копирование собираемой командной строки;
- запуск/остановка QEMU и объединённый stdout/stderr в консоли;
- относительные пути внутри проекта разрешаются относительно файла `.lleproject`.
- глобальный язык интерфейса: системный, русский или English, с выбором при первом запуске;
- собственная иконка приложения и ссылка на профиль автора в Steam — **danya_3108 (danya_31082)**.

## Быстрый запуск на macOS

### Готовое приложение из DMG

Начиная с версии 0.7.0 доступен universal2‑образ для Intel и Apple Silicon с macOS 13+. Перетащите `ChilledQEUM.app` в Applications — Python, pip, PySide6 и Qt уже включены внутрь. QEMU остаётся внешним компонентом (`brew install qemu`), но приложение автоматически добавляет пути Homebrew/MacPorts даже при запуске через Finder. Версия 0.8.0 добавляет глобальный выбор системного/русского/английского языка, новую иконку и ссылку на [Steam-профиль автора](https://steamcommunity.com/id/SarovOffical/).

При первом запуске откроется двуязычный выбор языка. Значение сохраняется как глобальная настройка приложения и действует для всех `.lleproject`. Позже его можно изменить через **Настройки → Язык**; приложение предложит перезапуск, чтобы обновить весь интерфейс.

Локальная сборка подписана ad-hoc и без Apple Developer ID не может быть нотарифицирована. Если Gatekeeper блокирует скачанное приложение, один раз выполните `xattr -dr com.apple.quarantine /Applications/ChilledQEUM.app`; это действует только на данный bundle.

### Запуск из исходников

Нужны Python 3.10+ и QEMU. Если QEMU ещё не установлен:

```bash
brew install qemu
```

В Terminal из папки проекта:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Для обычного запуска откройте настоящий переносимый файл `run_macos.command`. Если архив получен через Telegram, браузер или AirDrop и macOS пишет **“is damaged and can’t be opened”**, сначала снимите карантин только с распакованной папки проекта:

```bash
cd "/путь/к/ChilledQEUM"
xattr -dr com.apple.quarantine .
/bin/zsh "./run_macos.command"
```

Удобный способ не печатать путь: введите в Terminal `cd ` с пробелом, перетащите туда папку ChilledQEUM и нажмите Enter. Затем выполните последние две команды. `chmod` отдельно вводить не требуется: новый запускатель выставляет права сам. Команда `xattr` здесь действует только на текущую распакованную папку, а не на весь Mac.

Скрипт перебирает установленные версии и выбирает совместимый Python 3.10+; старый Python из активированного Conda больше не перехватывает запуск. Несовместимый `.venv` переносится в резервную папку `.venv-incompatible-*`, затем pip обновляется внутри нового окружения. Если нужно принудительно указать конкретную версию, выполните, например, `CHILLEDQEUM_PYTHON=/usr/local/bin/python3.12 /bin/zsh "./run_macos.command"`.

После этого скрипт устанавливает PySide6 только при необходимости и запускает приложение. Весь вывод первого запуска сохраняется в `launcher.log`: если окно не появилось, пришлите этот файл. Та же инструкция лежит в `ПЕРВЫЙ_ЗАПУСК_MACOS.txt`. QEMU можно указать явно на вкладке «Основное»; при пустом поле используется `qemu-system-<architecture>` из `PATH`.

### Linux и Windows

Код кроссплатформенный. На Linux/Windows создайте venv, установите `requirements.txt` и выполните `python main.py`. Выберите подходящие accelerator/display/audio backend: например KVM/GTK/ALSA или WHPX/SDL. Значения в списках редактируемые.

## Типичный сценарий

1. Выберите **Заготовки** в меню либо заполните основные параметры ВМ.
2. Выберите архитектуру и модель CPU. Кнопка **«Из QEMU…»** загружает точный список из текущего бинарника через `-cpu help`.
3. На вкладке «Устройства» нажмите **«Загрузить модели устройств из установленного QEMU…»**, чтобы дополнить списки только моделями выбранной сборки.
4. На вкладке «Накопители» нажмите «Создать диск…», выберите путь, формат, виртуальный размер и интерфейс. Для уже существующего образа используйте «Добавить диск…».
5. Для BIOS оставьте image пустым, чтобы QEMU использовал встроенный BIOS, либо выберите внешний файл.
6. Для UEFI нажмите «Найти firmware установленного QEMU», затем «Создать копию UEFI NVRAM…». Code image остаётся read-only, а отдельный vars image хранит NVRAM гостя.
7. На вкладке LLE перечислите все фактические зависимости. У записей ROM можно задать аргументы QEMU с маркером `{path}`, например `-option-rom {path}`.
8. Сохраните проект — относительные пути затем будут считаться от расположения `.lleproject`.
9. Нажмите «Проверить QEMU / LLE». Предупреждения не означают автоматическую несовместимость, но требуют проверки; ошибки отсутствующего бинарника, CPU, устройства или обязательного UEFI code блокируют запуск.
10. Просмотрите итоговую команду и запустите QEMU.

### Выбор процессора

Поле **CPU → Модель** является редактируемым списком. Встроенные варианты зависят от architecture: например Cortex/Neoverse/A64FX для AArch64 и Intel/AMD поколения для x86_64. Кнопка **«Из QEMU…»** выполняет `qemu-system-… -cpu help` и заменяет заготовки списком, который действительно объявляет выбранный бинарник. Обычная проверка QEMU также обновляет этот список и показывает блокирующую ошибку для неизвестной модели.

`host` передаёт возможности процессора хоста и обычно подходит только для совпадающей архитектуры с аппаратным ускорением. `max` включает максимальный набор возможностей эмулятора и удобен для TCG. Именованная модель, например `cortex-a72`, `Broadwell` или `EPYC-Milan`, сохраняется в `vm.cpu.model` и передаётся как `-cpu <model>`.

### Создание диска

Диалог «Создать диск…» вызывает `qemu-img` напрямую без shell, не перезаписывает существующие файлы и после успеха автоматически добавляет образ в таблицу. Доступны QCOW2, RAW, VMDK и VDI, размер в GiB/MiB и интерфейсы virtio/NVMe/SCSI/IDE/SD/USB. Рекомендуемый вариант для обычной ВМ — QCOW2 + virtio: файл разреженный и растёт по мере записи данных.

## Заготовки

Семь заготовок доступны прямо в меню **Заготовки**; основные варианты также представлены импортируемыми файлами в [`examples/templates`](examples/templates):

- `x86_64-bios` — Q35 с встроенным SeaBIOS/BIOS QEMU;
- `x86_64-uefi` — Q35 + обычный EDK2/OVMF;
- `x86_64-secure-boot` — Q35 + Secure Boot firmware + SMM;
- `aarch64-uefi` — machine `virt` + AArch64 EDK2;
- `aarch64-winpe` — WinPE/Windows ARM64: `virt`, UEFI, `ramfb`, звук и сеть выключены до установки гостевых драйверов;
- `lle-scaffold` — явный минимальный каркас LLE-зависимостей.
- `isolated-lab` — строгая изолированная VM без сети и с временными записями дисков.

Заготовки намеренно не содержат ROM, диски или firmware-файлы. После применения UEFI-заготовки выполните автопоиск firmware и создайте собственную копию NVRAM.

### WinPE ARM64 на macOS

Выберите заготовку **AArch64 — WinPE/Windows UEFI**, затем ISO. На вкладке firmware нажмите автопоиск: для Homebrew QEMU должны быть выбраны `edk2-aarch64-code.fd` и записываемая копия `edk2-arm-vars.fd`. Файл `share/qemu/bios.bin` является x86 SeaBIOS и для ARM64 Windows блокируется проверкой.

Для первого запуска оставьте звук `none`. Если нужен только вывод звука, выберите HDA-контроллер, кодек `hda-output` и backend `coreaudio`. `hda-duplex`/`hda-micro` запрашивают вход `adc`, но CoreAudio backend QEMU поддерживает только воспроизведение, поэтому Workbench блокирует эту комбинацию до запуска. Для видео безопаснее начать с `ramfb`; `virtio-gpu-pci` теперь доступен явно, но Windows потребуется соответствующий гостевой драйвер.

При смене architecture интерфейс синхронизирует типичные machine и `qemu-system-*`: ARM64 получает `virt`, x86_64 — `q35`. Старые проекты с известной несовместимой парой вроде `aarch64 + pc` исправляются при открытии и помечаются как изменённые. Неизвестные пользовательские machine не переписываются молча, но проверяются по фактическому `QEMU -machine help`.

## Безопасный запуск QEMU

Вкладка **Безопасность** содержит один основной переключатель и три профиля:

- **Сбалансированный** — запрещает пользовательскую конфигурацию QEMU и отключает monitor/QMP;
- **Строгая изоляция** — дополнительно включает `-nodefaults`, отключает serial и сеть, запускает диски с `snapshot=on`, поэтому изменения гостя не сохраняются;
- **Пользовательский** — позволяет независимо выбрать каждое ограничение.

Реальная опция QEMU называется `-sandbox` (не `-sandboxing`). Отдельные переключатели позволяют добавить её к любому профилю и сделать обязательной для запуска. Обязательная политика имеет приоритет даже над `security.enabled=false`: если итоговая команда почему-либо не содержит `-sandbox` или выбранный бинарник не поддерживает seccomp, Workbench блокирует запуск.

При попытке отключить активный sandbox приложение спрашивает подтверждение. Если QEMU уже запущен с `-sandbox`, после подтверждения сначала отправляется запрос на остановку ВМ. Галочка **«Запретить отключение sandbox на 10 минут»** сразу включает безопасный запуск, `-sandbox` и обязательную политику; переключатели отключения становятся недоступны, а интерфейс показывает обратный отсчёт. Момент окончания хранится в `sandboxLockUntil`, поэтому сохранённый проект восстанавливает оставшееся время после перезапуска.

Поддержка sandbox проверяется самим выбранным бинарником. Homebrew QEMU на macOS обычно собран без Linux seccomp sandbox; включение неподдерживаемой опции считается ошибкой и блокирует запуск. Поэтому обязательный sandbox практически предназначен для Linux-сборки QEMU с seccomp; на macOS ускорителем является HVF, KVM доступен только на Linux. Параметры `-sandbox`, `-nodefaults`, `-no-user-config`, `-monitor` и `-serial` описаны в [руководстве запуска QEMU](https://www.qemu.org/docs/master/system/qemu-manpage.html).

`-sandbox` включает seccomp-фильтрацию системных вызовов процесса QEMU и уменьшает поверхность атаки ядра Linux; это один слой защиты, а не гарантия, что вредоносный гость никогда не сможет атаковать хост. QEMU также рекомендует запуск без root и дополнительные механизмы изоляции хоста — см. [Security в документации QEMU](https://www.qemu.org/docs/master/system/security.html). 10-минутная блокировка является защитой интерфейса от случайного отключения, но не защищает JSON от ручного редактирования внешней программой с правами пользователя.

Этот режим намеренно не патчит UEFI/BIOS, не скрывает виртуальные драйверы и не выдаёт эмулируемые CPU/GPU за физическое оборудование. Реальное имя GPU корректно появляется только при настоящем device passthrough на поддерживаемом Linux/KVM-хосте; macOS HVF не предоставляет аналогичного универсального PCI passthrough.

## Трассировка инструкций и перевода ARM64

Вкладка **Трассировка** полностью выключена по умолчанию и не добавляет параметров к обычному быстрому запуску. Доступны профили:

- **Перевод Guest → TCG → ARM64** — `in_asm`, `out_asm`, оптимизированные TCG operations и ошибки гостя;
- **Выполненные гостевые блоки** — guest assembly + `exec,nochain`;
- **Диагностика** — interrupts, CPU reset, unimplemented functionality и guest errors;
- **Пользовательский** — независимый выбор `in_asm`, `out_asm`, `op`, `op_opt`, `exec`, `cpu`, `int` и других QEMU log items.

При включённом автоматическом TCG приложение меняет только собираемую команду: accelerator становится `tcg`, а несовместимый `CPU=host` временно заменяется на `CPU=max`. На ARM64 Mac `out_asm` содержит реально сгенерированный ARM64-код хоста. QEMU описывает `-d`, `-D` и `-dfilter` в [руководстве запуска](https://www.qemu.org/docs/master/system/invocation.html), а сам механизм динамического перевода — в [документации TCG](https://www.qemu.org/docs/master/devel/tcg.html).

Журнал автоматически перечитывается раз в секунду, но в окне показываются только последние 2 MiB. `exec` и особенно `cpu` могут создавать гигабайтные журналы и сильно замедлять ВМ. Фильтр `-dfilter` позволяет ограничить диапазон адресов. Опция serial capture показывает kernel/console output гостя в общей консоли, если гостевая ОС сама настроена на serial; это не перехват истории shell-команд внутри ОС.

## Формат `.lleproject`, версия 1

Файл — UTF-8 JSON. Верхний уровень:

```json
{
  "format": "qemu-lle-project",
  "version": 1,
  "name": "My VM",
  "vm": {},
  "lle": {}
}
```

Неизвестные поля сохраняются загрузчиком ядра при нормализации, однако текущий GUI редактирует только описанные ниже поля. Более новые версии схемы намеренно отклоняются, чтобы не интерпретировать их молча неверно.

### Секция `vm`

| Поле | Тип | Назначение |
|---|---:|---|
| `qemuBinary` | string | Явный путь/имя бинарника; пусто — выбрать по architecture |
| `architecture`, `machine`, `accelerator` | string | Архитектура гостя, QEMU machine и accelerator |
| `cpu` | object | `model`, `cores`, `sockets`, `threads` |
| `memoryMiB` | integer | RAM в MiB |
| `storage` | object | `iso` и массив `disks` |
| `network` | object | mode/model/MAC/interface/bridge/`hostForwards` |
| `video`, `sound`, `usb` | object | Видеовывод, аудио (`model`, `codec`, `backend`) и USB |
| `firmware` | object | mode: `default`, `bios` или `uefi`; BIOS/code/vars, pflash, Secure Boot/SMM, boot order |
| `security` | object | Safe-hardening profile, monitor/network/disks и политика sandbox |
| `tracing` | object | TCG/instruction logging, serial capture, address filter и путь журнала |
| `extraArgs` | string[] | Готовые аргументы; один элемент массива — один argv-токен |

Диск использует `path`, `format`, `interface`, `readOnly`, `snapshot` и необязательное `description`. Поддержанный генератором `interface`: обычные QEMU drive interfaces и специальные `nvme`/`usb`, для которых создаются backend + device.

`vm.security` содержит `enabled`, `profile`, ограничения профиля и три поля sandbox: `sandbox` добавляет `-sandbox`, `sandboxRequired` запрещает запуск без него, а `sandboxLockUntil` хранит время окончания UI-блокировки как Unix timestamp (0 — блокировки нет). Рекомендуемые ограничения передаются одним argv-значением: `on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny`.

### BIOS и UEFI

Объект `vm.firmware` поддерживает:

| Поле | Тип | Назначение |
|---|---:|---|
| `mode` | string | `default`, `bios` или `uefi` |
| `bios` | string | Внешний BIOS для `-bios`; пусто в x86 BIOS-режиме означает встроенный BIOS QEMU |
| `uefiCode` | string | UEFI/EDK2 code image, pflash unit 0 |
| `uefiVars` | string | Отдельный NVRAM vars image, pflash unit 1 |
| `pflashFormat` | string | `raw` или `qcow2` |
| `uefiCodeReadOnly` | boolean | Добавляет `readonly=on` для code image; рекомендуется `true` |
| `uefiVarsReadOnly` | boolean | Read-only NVRAM; для постоянных настроек обычно `false` |
| `secureBoot` | boolean | Требование проекта и дополнительная диагностика Secure Boot image |
| `smm` | boolean | Добавляет `smm=on` к `-machine`, обычно нужно Q35 Secure Boot |
| `bootOrder` | string | QEMU boot order, например `cdn` |

Автопоиск просматривает data directory реального бинарника QEMU и типичные Homebrew/system paths. Он выбирает firmware по архитектуре и Secure Boot-флагу. Шаблон vars никогда не назначается как записываемый файл напрямую: кнопка создания NVRAM копирует его в выбранное пользователем место.

### Секция `lle`

| Поле | Тип | Назначение |
|---|---:|---|
| `enabled` | boolean | Включает добавление описанных LLE-параметров в команду |
| `firmware.roms` | object[] | ROM/firmware dependencies |
| `deviceModels` | object[] | Модели, добавляемые через `-device` |
| `timingClockOptions` | object | Строки `rtc`, `icount` и массив `extraArgs` |
| `requiredQemuDevices` | string[] | Имена, которые должны присутствовать в `qemu -device help` |
| `requiredModules` | string[] | Имена модулей или явные пути к ним |
| `notes`, `instructions` | string | Человекочитаемые пояснения проекта |

Запись ROM:

```json
{
  "path": "roms/card.rom",
  "kind": "option-rom",
  "required": true,
  "enabled": true,
  "qemuArgs": ["-option-rom", "{path}"],
  "description": "ROM supplied separately"
}
```

`qemuArgs` добавляются только явно; `{path}` заменяется абсолютным разрешённым путём. Это не позволяет оболочке угадывать назначение ROM.

Запись device model:

```json
{
  "name": "Debug console",
  "qemuDevice": "isa-debugcon",
  "properties": {"iobase": "0x402"},
  "enabled": true,
  "description": "Debug port"
}
```

Она становится `-device isa-debugcon,iobase=0x402`. Имя `qemuDevice` также автоматически попадает в проверяемый набор.

Полный пример: [`examples/minimal-x86_64.lleproject`](examples/minimal-x86_64.lleproject). Файлы образов/ROM намеренно не входят в репозиторий — пример должен показать предупреждения проверки, пока пользователь не предоставит собственные законно полученные файлы.

## Проверка LLE-зависимостей

Проверка выполняет QEMU `--version`, `-machine help` и `-device help`, затем:

- проверяет выбранную machine;
- проверяет все выбранные базовые модели video/network/audio/USB по фактическому `-device help` даже при выключенной LLE;
- для BIOS проверяет внешний image или подтверждает использование встроенного x86 BIOS;
- блокирует известный x86 `bios.bin` в ARM/AArch64-конфигурации;
- для UEFI требует читаемый code image, проверяет отдельный vars/NVRAM, права записи, одинаковые пути, Secure Boot build и SMM;
- проверяет `requiredQemuDevices` и все активные `deviceModels`;
- разрешает ROM относительно проекта и проверяет существование/чтение;
- ищет модули по явному пути, `QEMU_MODULE_DIR` и типичным `lib/qemu` рядом с бинарником/Homebrew/system prefix;
- показывает `✓`, `⚠` или `✕` в таблице.

QEMU не предоставляет единый стабильный список всех динамических модулей во всех сборках, поэтому проверка модулей является консервативным поиском файлов. Ложное предупреждение возможно для статически встроенного компонента; это повод свериться со сборкой, а не доказательство отсутствия функции.

## Тесты

Тесты ядра не требуют PySide6 или установленного QEMU:

```bash
python -m unittest discover -s tests -v
python -m compileall -q main.py qemu_lle_workbench tests
```

При установленном QEMU можно дополнительно проверить firmware-конфигурации и реальное создание guest/host assembly журнала. Smoke-тесты запускают QEMU без display на короткое время; временные NVRAM и логи удаляются автоматически:

```bash
python -m tests.smoke_firmware
python -m tests.smoke_tracing
```

## Ограничения прототипа

- UI не поставляет ROM/UEFI/ОС; создание дисков требует `qemu-img` из установленного QEMU.
- Проброс USB host-device и сетевые tap/bridge могут требовать прав и ручной настройки ОС.
- Safe-hardening не является anti-detection и не гарантирует совместимость ПО, которое запрещает запуск в ВМ.
- Трассировка TCG существенно медленнее HVF/KVM и может очень быстро заполнить свободное место логами.
- Команда собирается безопасно как argv без shell, но любые дополнительные QEMU options остаются ответственностью пользователя.
- Остановка сначала отправляет обычный terminate, затем через 3 секунды завершает зависший процесс принудительно.
- Это редактор/launcher, а не менеджер установки QEMU и не замена документации конкретной модели устройства.
