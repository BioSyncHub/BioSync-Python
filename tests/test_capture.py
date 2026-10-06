import unittest
from unittest.mock import Mock, patch

import numpy as np

from auxilio_ai.core.capture import ScreenCapture


class ScreenCaptureTests(unittest.TestCase):
    @patch("auxilio_ai.core.capture.bettercam.create")
    @patch("auxilio_ai.core.capture.ctypes.windll.user32")
    def test_initializes_bettercam_with_centered_region(
        self,
        user32: Mock,
        create_camera: Mock,
    ) -> None:
        user32.GetSystemMetrics.side_effect = [1920, 1080]
        frame = np.zeros((320, 320, 3), dtype=np.uint8)
        camera = Mock()
        camera.grab.return_value = frame
        create_camera.return_value = camera

        capture = ScreenCapture()

        self.assertEqual(capture.regiao, (800, 380, 1120, 700))
        create_camera.assert_called_once_with(
            region=(800, 380, 1120, 700),
            output_color="RGB",
        )
        self.assertIs(capture.capturar_frame(), frame)
        camera.grab.assert_called_once_with()

    @patch("auxilio_ai.core.capture.bettercam.create")
    @patch("auxilio_ai.core.capture.ctypes.windll.user32")
    def test_fov_change_updates_region_used_by_bettercam(
        self,
        user32: Mock,
        create_camera: Mock,
    ) -> None:
        user32.GetSystemMetrics.side_effect = [1920, 1080]
        camera = Mock()
        resized_camera = Mock()
        create_camera.side_effect = [camera, resized_camera]
        capture = ScreenCapture()

        capture.definir_fov(640)
        capture.capturar_frame()

        self.assertEqual(capture.regiao, (640, 220, 1280, 860))
        camera.release.assert_called_once_with()
        self.assertEqual(
            create_camera.call_args_list,
            [
                unittest.mock.call(
                    region=(800, 380, 1120, 700),
                    output_color="RGB",
                ),
                unittest.mock.call(
                    region=(640, 220, 1280, 860),
                    output_color="RGB",
                ),
            ],
        )
        self.assertIs(capture.camera, resized_camera)
        resized_camera.grab.assert_called_once_with()
