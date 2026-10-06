import unittest
from pathlib import Path
from unittest.mock import patch

from ui.app import AUX_AI_FOCUS_COLORS, BioSyncApp


class FakeCanvas:
    def __init__(self):
        self.ovals = []
        self.images = []
        self.lines = []
        self.texts = []

    def delete(self, _tag):
        self.ovals.clear()
        self.images.clear()
        self.lines.clear()
        self.texts.clear()

    def winfo_exists(self):
        return True

    def winfo_width(self):
        return 330

    def winfo_height(self):
        return 340

    def create_polygon(self, *_args, **_kwargs):
        pass

    def create_line(self, *_args, **_kwargs):
        self.lines.append((_args, _kwargs))

    def create_image(self, *_args, **_kwargs):
        self.images.append((_args, _kwargs))

    def create_oval(self, *coordinates, **options):
        self.ovals.append((coordinates, options))

    def create_text(self, *_args, **_kwargs):
        self.texts.append((_args, _kwargs))


class AuxAiPreviewTests(unittest.TestCase):
    def test_model_selects_its_image_and_calibrated_focus_points(self):
        root = Path(__file__).resolve().parent.parent
        expected_profiles = {
            "BioSync-Warzone": {
                "image": "target-wz-onnx.png",
                "focus": {"head": (0.50, 0.13), "chest": (0.51, 0.30), "belly": (0.50, 0.46)},
            },
            "BioSync-Fortnite": {
                "image": "target-wfortnite-onnx.png",
                "focus": {"head": (0.52, 0.12), "chest": (0.50, 0.30), "belly": (0.50, 0.42)},
            },
        }
        for profile, expected in expected_profiles.items():
            for focus, (focus_x, focus_y) in expected["focus"].items():
                with self.subTest(profile=profile, focus=focus):
                    app = BioSyncApp.__new__(BioSyncApp)
                    app._aux_ai_preview = FakeCanvas()
                    app._aux_ai_target_images_dir = root / "assets" / "target"
                    app._auxilio_ai_settings = {
                        "model_path": f"models/{profile}.onnx",
                        "aim_point": focus,
                    }
                    app._aux_ai_colors = {
                        "cyan": "#00D9EE",
                        "panel": "#191B27",
                        "muted": "#9196A8",
                    }
                    app._aux_ai_aim_label = lambda value: value

                    with patch("ui.app.ImageTk.PhotoImage", return_value="photo") as photo:
                        app._draw_aux_ai_preview()

                    self.assertEqual(len(app._aux_ai_preview.images), 1)
                    source_path = root / "assets" / "target" / expected["image"]
                    from PIL import Image
                    with Image.open(source_path) as source_image:
                        alpha_bounds = source_image.convert("RGBA").getchannel("A").getbbox()
                        source_size = source_image.size
                    crop_left, crop_top, crop_right, crop_bottom = alpha_bounds
                    crop_width = crop_right - crop_left
                    crop_height = crop_bottom - crop_top
                    image_scale = min(
                        int(330 * 0.78) / crop_width,
                        int(340 * 1.48) / crop_height,
                    )
                    image_width = round(crop_width * image_scale)
                    image_height = round(crop_height * image_scale)
                    self.assertEqual(
                        photo.call_args.args[0].size,
                        (image_width, image_height),
                    )
                    self.assertGreater(image_height, 340)
                    self.assertEqual(app._aux_ai_preview.ovals, [])
                    self.assertEqual(len(app._aux_ai_preview.lines), 1)
                    line_args, line_options = app._aux_ai_preview.lines[0]
                    self.assertEqual(line_options["fill"], AUX_AI_FOCUS_COLORS[focus])
                    image_x = 330 * 0.34 - image_width / 2
                    image_y = 0
                    expected_x = image_x + image_width * (
                        focus_x * source_size[0] - crop_left
                    ) / crop_width
                    expected_y = image_y + image_height * (
                        focus_y * source_size[1] - crop_top
                    ) / crop_height
                    self.assertAlmostEqual(line_args[0], expected_x)
                    self.assertAlmostEqual(line_args[1], expected_y)
                    self.assertIn(
                        "FOCO ATUAL",
                        [options["text"] for _args, options in app._aux_ai_preview.texts],
                    )
                    self.assertIn(
                        focus.upper(),
                        [options["text"] for _args, options in app._aux_ai_preview.texts],
                    )
                    self.assertIn(
                        AUX_AI_FOCUS_COLORS[focus],
                        [options["fill"] for _args, options in app._aux_ai_preview.texts],
                    )


if __name__ == "__main__":
    unittest.main()
