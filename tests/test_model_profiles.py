import tempfile
import unittest
from pathlib import Path

from auxilio_ai.core.model_profiles import (
    discover_model_profiles,
    normalize_model_profile_path,
)


class ModelProfileTests(unittest.TestCase):
    def test_discovers_profiles_and_prioritizes_biosync_models(self):
        with tempfile.TemporaryDirectory() as directory:
            models_dir = Path(directory)
            warzone = models_dir / "BioSync-Warzone.onnx"
            fortnite = models_dir / "BioSync-Fortnite.onnx"
            additional = models_dir / "Custom.onnx"
            for model_path in (additional, fortnite, warzone):
                model_path.touch()

            profiles = discover_model_profiles(models_dir)

        self.assertEqual(
            list(profiles),
            ["BioSync-Warzone", "BioSync-Fortnite", "Custom"],
        )
        self.assertEqual(profiles["BioSync-Warzone"], warzone)
        self.assertEqual(profiles["BioSync-Fortnite"], fortnite)

    def test_normalizes_legacy_model_filenames(self):
        self.assertEqual(
            normalize_model_profile_path("models/GGMWarzone.onnx"),
            str(Path("models") / "BioSync-Warzone.onnx"),
        )
        self.assertEqual(
            normalize_model_profile_path("models/BioSync-AI.onnx"),
            str(Path("models") / "BioSync-Fortnite.onnx"),
        )

    def test_keeps_unknown_model_paths_unchanged(self):
        path = "custom/Experimental.onnx"
        self.assertEqual(normalize_model_profile_path(path), path)


if __name__ == "__main__":
    unittest.main()
