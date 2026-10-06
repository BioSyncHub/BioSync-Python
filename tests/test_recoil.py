import time
import unittest

from core.config import EngineConfig
from core.engine import InputEngine
from core.recoil import get_profile, interpolate_pattern, sample_recoil


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


class RecoilPatternTests(unittest.TestCase):
    def test_voyak_profile_is_loaded_from_json(self):
        profile = get_profile("voyak_kt3")
        self.assertEqual(profile.name, "VOYAK KT-3")
        self.assertEqual(profile.rpm, 652)
        self.assertEqual(profile.mag, 40)
        self.assertGreater(len(profile.keypoints), 20)

    def test_unknown_profile_falls_back_to_constant(self):
        profile = get_profile("arma-que-nao-existe")
        self.assertEqual(profile.id, "constant")
        x, y = sample_recoil("arma-que-nao-existe", 500, 3.0, 2.0)
        self.assertEqual(x, 3.0)
        self.assertEqual(y, 2.0)

    def test_voyak_starts_vertical_before_the_right_hook(self):
        # First shots: almost no horizontal, strong downward pull.
        early_x, early_y = sample_recoil("voyak_kt3", 200, 0.0, 4000.0)
        self.assertLess(abs(early_x), 250)
        self.assertGreater(early_y, 3000)

        # Mid mag (~shot 18): hard right recoil → strong left compensation.
        hook_x, hook_y = sample_recoil("voyak_kt3", 1564, 0.0, 4000.0)
        self.assertLess(hook_x, -2500)
        self.assertGreater(hook_y, 2500)
        self.assertLess(abs(hook_x), abs(early_x) + 4000)

        # Late mag: vertical eases, horizontal flips toward the left wiggle.
        late_x, late_y = sample_recoil("voyak_kt3", 2700, 0.0, 4000.0)
        self.assertGreater(late_x, hook_x)
        self.assertLess(late_y, early_y)

    def test_horizontal_trim_adds_on_top_of_pattern(self):
        base_x, base_y = sample_recoil("voyak_kt3", 1564, 0.0, 4000.0)
        trim_x, trim_y = sample_recoil("voyak_kt3", 1564, 400.0, 4000.0)
        self.assertAlmostEqual(trim_x - base_x, 400.0, places=3)
        self.assertAlmostEqual(trim_y, base_y, places=3)

    def test_interpolation_holds_last_keypoint(self):
        x, y = interpolate_pattern(((0.0, 0.1, 0.2), (100.0, 0.5, 0.8)), 500)
        self.assertEqual((x, y), (0.5, 0.8))

    def test_engine_applies_voyak_hook_while_firing(self):
        cfg = EngineConfig(
            no_recoil_active=True,
            recoil_profile="voyak_kt3",
            no_recoil_force_y=4000.0,
            no_recoil_force_x=0.0,
        )
        engine = InputEngine(cfg)
        engine._pad = FakePad()
        engine.set_key(0x01, True)
        engine._fire_started_at = time.perf_counter() - 1.564

        engine._process_frame(0.001)

        self.assertIsNotNone(engine._pad.right_stick)
        self.assertLess(engine._pad.right_stick["x_value"], -2500)
        self.assertLess(engine._pad.right_stick["y_value"], -2500)

    def test_engine_resets_voyak_pattern_when_trigger_releases(self):
        cfg = EngineConfig(
            no_recoil_active=True,
            recoil_profile="voyak_kt3",
            no_recoil_force_y=4000.0,
        )
        engine = InputEngine(cfg)
        engine._pad = FakePad()
        engine.set_key(0x01, True)
        engine._fire_started_at = time.perf_counter() - 1.564
        engine._process_frame(0.001)
        hooked = engine._pad.right_stick["x_value"]
        self.assertLess(hooked, -2500)

        engine.set_key(0x01, False)
        engine._process_frame(0.001)
        self.assertIsNone(engine._fire_started_at)
        self.assertEqual(engine._pad.right_stick, {"x_value": 0, "y_value": 0})


if __name__ == "__main__":
    unittest.main()
