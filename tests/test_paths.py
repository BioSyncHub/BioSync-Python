import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from core.paths import auxilio_ai_environment_root, project_root, user_data_root


class ApplicationPathsTests(unittest.TestCase):
    def test_frozen_project_root_uses_extracted_resources(self):
        with patch.object(sys, "frozen", True, create=True), patch.object(
            sys, "_MEIPASS", r"C:\bundle\_internal", create=True
        ):
            self.assertEqual(project_root(), Path(r"C:\bundle\_internal"))

    def test_frozen_user_data_uses_local_app_data(self):
        with patch.object(sys, "frozen", True, create=True), patch.dict(
            os.environ, {"LOCALAPPDATA": r"C:\Users\Tester\AppData\Local"}
        ):
            self.assertEqual(
                user_data_root(),
                Path(r"C:\Users\Tester\AppData\Local\BioSync"),
            )

    def test_source_mode_keeps_user_data_with_project(self):
        with patch.object(sys, "frozen", False, create=True):
            self.assertEqual(user_data_root(), project_root())
            self.assertEqual(
                auxilio_ai_environment_root(),
                project_root() / ".venv-auxilio-ai",
            )

    def test_frozen_build_reuses_adjacent_auxilio_ai_environment(self):
        with patch.object(sys, "frozen", True, create=True), patch.object(
            sys,
            "executable",
            r"C:\BioSync\dist\BioSync\BioSync.exe",
        ), patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Users\Tester\AppData\Local"}):
            expected = Path(r"C:\BioSync\.venv-auxilio-ai")
            with patch("core.paths.Path.is_file", return_value=True):
                self.assertEqual(auxilio_ai_environment_root(), expected)


if __name__ == "__main__":
    unittest.main()
