import unittest

import vgamepad as vg

from core.config import EngineConfig
from core.engine import InputEngine


class FakePad:
    def __init__(self):
        self.buttons = set()
        self.right_stick = None

    def right_joystick(self, **values):
        self.right_stick = values

    def left_joystick(self, **values):
        pass

    def left_trigger(self, **values):
        pass

    def right_trigger(self, **values):
        pass

    def press_button(self, button):
        self.buttons.add(button)

    def release_button(self, button):
        self.buttons.discard(button)

    def update(self):
        pass


class InputEngineTests(unittest.TestCase):
    def test_no_recoil_applies_while_firing_without_ads(self):
        cfg = EngineConfig(
            no_recoil_active=True,
            no_recoil_force_y=2.0,
            no_recoil_force_x=3.0,
            recoil_profile="constant",
        )
        engine = InputEngine(cfg)
        engine._pad = FakePad()
        engine.set_key(0x01, True)

        engine._process_frame(0.001)

        self.assertEqual(engine._pad.right_stick, {"x_value": 3, "y_value": -2})

    def test_no_recoil_clamps_positive_and_negative_offsets_to_5000(self):
        for force_x, force_y, expected_x, expected_y in (
            (9000.0, 9000.0, 5000, -5000),
            (-9000.0, -9000.0, -5000, 5000),
        ):
            with self.subTest(force_x=force_x, force_y=force_y):
                cfg = EngineConfig(
                    no_recoil_active=True,
                    no_recoil_force_x=force_x,
                    no_recoil_force_y=force_y,
                    recoil_profile="constant",
                )
                engine = InputEngine(cfg)
                engine._pad = FakePad()
                engine.set_key(0x01, True)

                engine._process_frame(0.001)

                self.assertEqual(
                    engine._pad.right_stick,
                    {"x_value": expected_x, "y_value": expected_y},
                )

    def test_no_recoil_does_not_apply_when_not_firing(self):
        cfg = EngineConfig(
            no_recoil_active=True,
            no_recoil_force_y=2.0,
            no_recoil_force_x=3.0,
            recoil_profile="constant",
        )
        engine = InputEngine(cfg)
        engine._pad = FakePad()
        engine.set_key(0x02, True)

        engine._process_frame(0.001)

        self.assertEqual(engine._pad.right_stick, {"x_value": 0, "y_value": 0})

    def test_small_mouse_delta_does_not_saturate_stick(self):
        cfg = EngineConfig(
            sens_x=4453.0,
            sens_y=7250.0,
            filter_x=2.1,
            filter_y=2.1,
            curve_x=0.7,
            curve_y=0.7,
            acceleration=0.8,
            hardware_gain=4.5,
        )
        engine = InputEngine(cfg)

        engine.inject_raw_delta(1, 0)
        engine._process_frame(0.001)

        self.assertGreater(engine._target_x, 0)
        self.assertLess(engine._target_x, 32767)
        self.assertGreater(engine._smoothed_x, 0)
        self.assertLess(engine._smoothed_x, 32767)
        self.assertEqual(engine._target_y, 0)

    def test_small_mouse_delta_preserves_direction(self):
        engine = InputEngine(EngineConfig(hardware_gain=4.5))

        engine.inject_raw_delta(-1, 0)
        engine._process_frame(0.001)

        self.assertLess(engine._target_x, 0)

    def test_mouse_delta_uses_reference_millisecond_timing_and_gain(self):
        cfg = EngineConfig(hardware_gain=4.5)
        engine = InputEngine(cfg)

        engine.inject_raw_delta(1, 0)
        engine._process_frame(0.001)

        norm = cfg.hardware_gain * cfg.filter_x * cfg.sens_x * cfg.curve_x
        factor = (norm / 500_000.0) ** cfg.acceleration
        self.assertAlmostEqual(engine._target_x, factor * 32767.0)
        self.assertLess(engine._target_x, 32767)

    def test_mouse_stopping_returns_right_stick_to_center(self):
        engine = InputEngine(EngineConfig(friction=1.0))
        engine._pad = FakePad()

        engine.inject_raw_delta(1, 0)
        engine._process_frame(0.001)
        self.assertNotEqual(engine._pad.right_stick["x_value"], 0)

        for _ in range(200):
            engine._process_frame(0.001)

        self.assertEqual(engine._pad.right_stick, {"x_value": 0, "y_value": 0})

    def test_yy_macro_pulses_using_configured_interval(self):
        cfg = EngineConfig(yy_active=True, yy_interval_ms=80.0)
        engine = InputEngine(cfg)
        engine.set_key(cfg.vk_yy, True)

        self.assertTrue(engine._process_macros(cfg, 1.0, False)[0])
        self.assertTrue(engine._process_macros(cfg, 1.02, False)[0])
        self.assertFalse(engine._process_macros(cfg, 1.03, False)[0])
        self.assertTrue(engine._process_macros(cfg, 1.081, False)[0])

    def test_slide_cancel_generates_configured_button_sequence(self):
        cfg = EngineConfig(slide_cancel_active=True)
        engine = InputEngine(cfg)
        engine.set_key(cfg.vk_slide_cancel, True)

        start = 1.0
        self.assertTrue(engine._process_macros(cfg, start, False)[2])
        self.assertFalse(engine._process_macros(cfg, start + 0.02, False)[1])
        self.assertTrue(engine._process_macros(cfg, start + 0.09, False)[1])
        self.assertTrue(engine._process_macros(cfg, start + 0.11, False)[3])
        self.assertFalse(engine._process_macros(cfg, start + 0.13, False)[1])

    def test_auto_ping_pulses_while_firing(self):
        cfg = EngineConfig(auto_ping_active=True, auto_ping_interval_ms=500.0)
        engine = InputEngine(cfg)
        engine.set_key(0x01, True)

        self.assertTrue(engine._process_macros(cfg, 1.0, True)[4])
        self.assertFalse(engine._process_macros(cfg, 1.03, True)[4])
        self.assertTrue(engine._process_macros(cfg, 1.501, True)[4])

    def test_macro_output_reaches_virtual_controller_report(self):
        engine = InputEngine(EngineConfig())
        engine._pad = FakePad()

        engine._apply_report(
            0, 0, 0, 0,
            macro_y=True,
            macro_b=True,
            auto_ping=True,
        )

        self.assertIn(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y, engine._pad.buttons)
        self.assertIn(vg.XUSB_BUTTON.XUSB_GAMEPAD_B, engine._pad.buttons)
        self.assertIn(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, engine._pad.buttons)


if __name__ == "__main__":
    unittest.main()
