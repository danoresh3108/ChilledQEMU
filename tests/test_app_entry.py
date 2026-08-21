import os
import unittest
from unittest.mock import patch

import main


class AppEntryTests(unittest.TestCase):
    def test_macos_finder_path_adds_package_manager_locations(self):
        with patch.object(main.sys, "platform", "darwin"), patch.dict(
            os.environ, {"PATH": "/custom/bin"}
        ):
            main.configure_macos_path()
            paths = os.environ["PATH"].split(os.pathsep)
        self.assertIn("/usr/local/bin", paths)
        self.assertIn("/custom/bin", paths)
        if os.path.isdir("/opt/homebrew/bin"):
            self.assertIn("/opt/homebrew/bin", paths)


if __name__ == "__main__":
    unittest.main()
