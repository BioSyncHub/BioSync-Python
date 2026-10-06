import unittest

from startup import (
    STARTUP_VISUAL_DURATION_SECONDS,
    STARTUP_VISUAL_MESSAGES,
    startup_visual_message,
)


class StartupVisualMessageTests(unittest.TestCase):
    def test_message_advances_through_five_second_loading_window(self):
        duration = STARTUP_VISUAL_DURATION_SECONDS / len(STARTUP_VISUAL_MESSAGES)

        self.assertEqual(startup_visual_message(0), STARTUP_VISUAL_MESSAGES[0])
        self.assertEqual(startup_visual_message(duration), STARTUP_VISUAL_MESSAGES[1])
        self.assertEqual(
            startup_visual_message(STARTUP_VISUAL_DURATION_SECONDS - 0.01),
            STARTUP_VISUAL_MESSAGES[-1],
        )

    def test_elapsed_time_after_five_seconds_stays_on_final_message(self):
        self.assertEqual(
            startup_visual_message(STARTUP_VISUAL_DURATION_SECONDS + 10),
            STARTUP_VISUAL_MESSAGES[-1],
        )
        self.assertIn("preservados", STARTUP_VISUAL_MESSAGES[3])
        self.assertIn("nenhuma alteração", STARTUP_VISUAL_MESSAGES[4])


if __name__ == "__main__":
    unittest.main()
