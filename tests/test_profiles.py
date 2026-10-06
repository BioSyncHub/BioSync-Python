import tempfile
import unittest
from pathlib import Path

from core.config import EngineConfig, load_profiles, save_profile


class ProfilePersistenceTests(unittest.TestCase):
    def test_saves_and_loads_multiple_named_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            default = EngineConfig(sens_x=4200.0, yy_active=True)
            precision = EngineConfig(sens_x=2800.0, friction=0.2)

            save_profile("Default", default, path)
            save_profile("Precision", precision, path)
            profiles = load_profiles(path)

        self.assertEqual(set(profiles), {"Default", "Precision"})
        self.assertEqual(profiles["Default"].sens_x, 4200.0)
        self.assertTrue(profiles["Default"].yy_active)
        self.assertEqual(profiles["Precision"].sens_x, 2800.0)
        self.assertEqual(profiles["Precision"].friction, 0.2)

    def test_saving_same_name_replaces_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            save_profile("Default", EngineConfig(sens_x=4200.0), path)
            save_profile("Default", EngineConfig(sens_x=3000.0), path)
            profiles = load_profiles(path)

        self.assertEqual(list(profiles), ["Default"])
        self.assertEqual(profiles["Default"].sens_x, 3000.0)

    def test_rejects_blank_profile_name(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            with self.assertRaises(ValueError):
                save_profile("  ", EngineConfig(), path)


if __name__ == "__main__":
    unittest.main()
