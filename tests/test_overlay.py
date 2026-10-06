import unittest
from typing import Any
import tkinter as tk
from unittest.mock import Mock, patch

from auxilio_ai.gui.overlay import GameOverlay


class FakeRoot:
    def __getattr__(self, name: str) -> Any:
        return Mock(name=name)


class FakeCanvas(tk.Canvas):
    def __init__(self) -> None:
        self.items: dict[int, dict[str, Any]] = {}
        self.next_id: int = 1

    def _create(
        self,
        item_type: str,
        coordinates: tuple[int, ...],
        **options: Any,
    ) -> int:
        item_id = self.next_id
        self.next_id += 1
        self.items[item_id] = {
            "type": item_type,
            "coordinates": coordinates,
            "options": options,
        }
        return item_id

    def create_rectangle_record(self, *coordinates: int, **options: Any) -> int:
        return self._create("rectangle", coordinates, **options)

    def create_line_record(self, *coordinates: int, **options: Any) -> int:
        return self._create("line", coordinates, **options)

    def create_oval_record(self, *coordinates: int, **options: Any) -> int:
        return self._create("oval", coordinates, **options)

    def coords_record(self, item_id: int, *coordinates: int) -> None:
        self.items[item_id]["coordinates"] = coordinates

    def itemconfigure_record(self, item_id: int, **options: Any) -> None:
        self.items[item_id]["options"].update(options)


class GameOverlayTests(unittest.TestCase):
    def make_overlay(self) -> tuple[GameOverlay, FakeCanvas]:
        canvas = FakeCanvas()
        for patcher in (
            patch.object(canvas, "pack"),
            patch.object(canvas, "create_rectangle", side_effect=canvas.create_rectangle_record),
            patch.object(canvas, "create_line", side_effect=canvas.create_line_record),
            patch.object(canvas, "create_oval", side_effect=canvas.create_oval_record),
            patch.object(canvas, "coords", side_effect=canvas.coords_record),
            patch.object(canvas, "itemconfigure", side_effect=canvas.itemconfigure_record),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

        with (
            patch(
                "auxilio_ai.gui.overlay.ctypes.windll.user32",
            ) as user32,
            patch("auxilio_ai.gui.overlay.tk.Tk", return_value=FakeRoot()),
            patch("auxilio_ai.gui.overlay.tk.Canvas", return_value=canvas),
            patch("auxilio_ai.gui.overlay.win32gui.FindWindow", return_value=1),
            patch("auxilio_ai.gui.overlay.win32gui.GetWindowLong", return_value=0),
            patch("auxilio_ai.gui.overlay.win32gui.SetWindowLong"),
        ):
            user32.GetSystemMetrics.side_effect = [1920, 1080]
            overlay = GameOverlay()
        return overlay, canvas

    def test_target_marker_reuses_canvas_item(self) -> None:
        overlay, canvas = self.make_overlay()

        overlay.desenhar_alvo_hud(160, 160)
        first_item_id = overlay.elementos_alvo[0]
        first_coordinates = canvas.items[first_item_id]["coordinates"]

        overlay.desenhar_alvo_hud(170, 150)

        self.assertEqual(len(canvas.items), 2)
        self.assertEqual(overlay.elementos_alvo, [first_item_id])
        self.assertNotEqual(
            canvas.items[first_item_id]["coordinates"],
            first_coordinates,
        )
        self.assertEqual(
            canvas.items[first_item_id]["options"]["state"],
            "normal",
        )

    def test_unused_detection_items_are_hidden_and_reused(self) -> None:
        overlay, canvas = self.make_overlay()
        overlay.view_settings = {
            "esp_enabled": True,
            "esp_opacity": 100,
            "show_body_zones": True,
            "snap_line": True,
            "show_aim_marker": True,
        }
        detections: list[tuple[int, int, int, int, float, int]] = [
            (10, 20, 30, 40, 0.9, 0),
        ]

        overlay.desenhar_deteccoes_hud(detections, 20, 30)
        item_ids = set(canvas.items)
        self.assertGreater(len(item_ids), 1)

        overlay.desenhar_deteccoes_hud(detections, 20, 30)
        self.assertEqual(set(canvas.items), item_ids)

        overlay.desenhar_deteccoes_hud([])
        self.assertTrue(all(
            item["options"].get("state") == "hidden"
            for item_id, item in canvas.items.items()
            if item_id != overlay.id_circulo_fov
        ))

        overlay.desenhar_deteccoes_hud(detections, 20, 30)
        self.assertEqual(set(canvas.items), item_ids)

    def test_switching_from_filled_to_outline_clears_fill_options(self) -> None:
        overlay, canvas = self.make_overlay()
        overlay.view_settings = {
            "esp_enabled": True,
            "esp_opacity": 50,
            "esp_style": "Filled",
        }
        detections: list[tuple[int, int, int, int, float, int]] = [
            (10, 20, 30, 40, 0.9, 0),
        ]

        overlay.desenhar_deteccoes_hud(detections)
        overlay.view_settings["esp_style"] = "Normal"
        overlay.desenhar_deteccoes_hud(detections)

        self.assertEqual(len(canvas.items), 2)
        item_id = overlay.elementos_alvo[0]
        options = canvas.items[item_id]["options"]
        self.assertEqual(options["fill"], "")
        self.assertEqual(options["stipple"], "")


if __name__ == "__main__":
    unittest.main()
