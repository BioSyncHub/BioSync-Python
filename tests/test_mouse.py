import unittest
from unittest.mock import patch

from auxilio_ai.core.mouse import MouseController


class MouseControllerTests(unittest.TestCase):
    def test_humanizer_speed_caps_motion_by_elapsed_time(self):
        with patch(
            "auxilio_ai.core.mouse.time.perf_counter",
            side_effect=(1.0, 1.01),
        ):
            mouse = MouseController(smoothing=1.0, humanizer_speed=1000)
            with patch.object(mouse, "mover_relativo") as move:
                mouse.mirar_no_alvo(200, 160, tamanho_fov=320)

        move.assert_called_once()
        self.assertEqual(move.call_args.args, (10, 0))

    def test_smoothing_strength_still_affects_motion_with_a_high_speed_cap(self):
        with patch(
            "auxilio_ai.core.mouse.time.perf_counter",
            side_effect=(1.0, 1.01),
        ):
            mouse = MouseController(smoothing=0.5, humanizer_speed=4000)
            with patch.object(mouse, "mover_relativo") as move:
                mouse.mirar_no_alvo(200, 160, tamanho_fov=320)

        move.assert_called_once()
        self.assertEqual(move.call_args.args, (20, 0))

    def test_fractional_steps_accumulate_instead_of_stalling(self):
        with patch(
            "auxilio_ai.core.mouse.time.perf_counter",
            side_effect=(1.0, 1.004, 1.008, 1.012),
        ):
            mouse = MouseController(smoothing=1.0, humanizer_speed=200)
            with patch.object(mouse, "mover_relativo") as move:
                for _ in range(3):
                    mouse.mirar_no_alvo(200, 160, tamanho_fov=320)

        self.assertEqual(move.call_count, 2)
        self.assertEqual(
            [call.args for call in move.call_args_list],
            [(1, 0), (1, 0)],
        )


if __name__ == "__main__":
    unittest.main()
