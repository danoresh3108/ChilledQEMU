from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from qemu_lle_workbench.i18n import ask_first_run_language, resource_path
from qemu_lle_workbench.main_window import MainWindow


def configure_macos_path() -> None:
    """Make Homebrew/MacPorts QEMU visible when Finder launches the .app."""
    if sys.platform != "darwin":
        return
    current = os.environ.get("PATH", "").split(os.pathsep)
    common = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/opt/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
    os.environ["PATH"] = os.pathsep.join(
        [path for path in common if Path(path).is_dir()]
        + [path for path in current if path and path not in common]
    )


def main() -> int:
    configure_macos_path()
    app = QApplication(sys.argv)
    app.setApplicationName("ChilledQEUM")
    app.setOrganizationName("ChilledQEUM")
    icon_path = resource_path("assets/ChilledQEUM.png")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    ask_first_run_language()
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
