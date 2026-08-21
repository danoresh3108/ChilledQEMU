import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QPushButton

from qemu_lle_workbench.i18n import resource_path, tr
from qemu_lle_workbench.main_window import MainWindow, STEAM_PROFILE_URL


class InternationalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_english_translation_is_selected_globally(self):
        with patch("qemu_lle_workbench.i18n.language_preference", return_value="en"):
            self.assertEqual(tr("Накопители"), "Storage")
            self.assertEqual(tr("Проверка завершена: ошибок 2, предупреждений 1"), "Validation complete: errors 2, warnings 1")

    def test_main_window_static_controls_are_localized(self):
        with patch("qemu_lle_workbench.i18n.language_preference", return_value="en"):
            window = MainWindow()
        try:
            self.assertEqual(window.tabs.tabText(0), "General")
            self.assertTrue(any(button.text() == "Start QEMU" for button in window.findChildren(QPushButton)))
            self.assertTrue(any(action.text() == "Settings" for action in window.menuBar().actions()))
        finally:
            window.dirty = False
            window.close()

    def test_custom_icon_and_exact_steam_profile_are_configured(self):
        self.assertEqual(STEAM_PROFILE_URL, "https://steamcommunity.com/id/SarovOffical/")
        self.assertTrue(Path(resource_path("assets/ChilledQEUM.png")).is_file())

    def test_author_display_name_is_present_in_steam_action(self):
        with patch("qemu_lle_workbench.i18n.language_preference", return_value="en"):
            window = MainWindow()
        try:
            self.assertTrue(
                any(
                    "danya_3108 (danya_31082)" in action.text()
                    for action in window.findChildren(QAction)
                )
            )
        finally:
            window.dirty = False
            window.close()


if __name__ == "__main__":
    unittest.main()
