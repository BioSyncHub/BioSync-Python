import tkinter as tk
import unittest
import os
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from auxilio_ai.gui.view_settings import DEFAULT_VIEW_SETTINGS
from ui.app import BioSyncApp, auxilio_ai_child_environment


class AuxAiSettingsTests(unittest.TestCase):
    def test_child_environment_does_not_inherit_parent_pyinstaller_tcl_libraries(self):
        with patch.dict(os.environ, {
            "TCL_LIBRARY": r"C:\BioSync\_internal\_tcl_data",
            "TK_LIBRARY": r"C:\BioSync\_internal\_tk_data",
            "BIOSYNC_TEST_PRESERVED": "yes",
        }):
            environment = auxilio_ai_child_environment(
                Path(r"C:\BioSync\data"),
                Path(r"C:\BioSync\_internal\auxilio_ai"),
            )

        self.assertNotIn("TCL_LIBRARY", environment)
        self.assertNotIn("TK_LIBRARY", environment)
        self.assertEqual(environment["BIOSYNC_TEST_PRESERVED"], "yes")
        self.assertEqual(environment["BIOSYNC_AUX_DATA_DIR"], r"C:\BioSync\data")
        self.assertEqual(
            environment["BIOSYNC_AUX_RESOURCE_DIR"],
            r"C:\BioSync\_internal\auxilio_ai",
        )

    def test_view_string_options_are_not_converted_to_numbers(self):
        interpreter = tk.Tcl()
        app = BioSyncApp.__new__(BioSyncApp)
        app.cfg = SimpleNamespace(vk_toggle=0)
        app._auxilio_ai_settings = {
            "aim_key": "Right mouse",
            "menu_key": "F8",
            "fov": 320,
            "smoothing": 0.5,
        }
        app._auxilio_ai_settings.update(DEFAULT_VIEW_SETTINGS)
        app._auxilio_ai_settings["target_classes"] = "Enemy,player"
        app._aux_ai_model_classes = []
        app._aux_ai_view_vars = {}

        for key, value in app._auxilio_ai_settings.items():
            if isinstance(value, bool):
                variable = tk.BooleanVar(master=interpreter, value=value)
            elif isinstance(value, str):
                variable = tk.StringVar(master=interpreter, value=value)
            else:
                variable = tk.DoubleVar(master=interpreter, value=value)
            app._aux_ai_view_vars[key] = variable

        values = app._aux_ai_values()

        self.assertEqual(values["esp_style"], "Normal")
        self.assertEqual(values["target_classes"], "Enemy,player")


if __name__ == "__main__":
    unittest.main()
