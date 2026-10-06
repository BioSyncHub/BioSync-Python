import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from auxilio_ai.core.inference import InferenceEngine


class FakeSession:
    def __init__(self, input_shape, names, output, input_type="tensor(float)"):
        self.input_meta = SimpleNamespace(name="images", shape=input_shape, type=input_type)
        self.model_meta = SimpleNamespace(custom_metadata_map={"names": names})
        self.outputs = output if isinstance(output, list) else [output]
        self.output_metas = [
            SimpleNamespace(name=name)
            for name in (
                ["boxes", "scores", "class_ids"][:len(self.outputs)]
                if len(self.outputs) > 1 else ["output0"]
            )
        ]
        self.last_input = None

    def get_inputs(self):
        return [self.input_meta]

    def get_modelmeta(self):
        return self.model_meta

    def get_outputs(self):
        return self.output_metas

    def run(self, _outputs, inputs):
        self.last_input = inputs["images"]
        return self.outputs


class InferenceEngineTests(unittest.TestCase):
    def make_engine(
        self,
        metadata,
        target_classes=None,
        shape=(1, 3, "height", "width"),
        output=None,
        input_type="tensor(float)",
    ):
        if output is None:
            output = np.array([[[100], [50], [20], [30], [0.9]]], dtype=np.float32)
        session = FakeSession(shape, metadata, output, input_type)
        with patch("auxilio_ai.core.inference.ort.get_available_providers", return_value=[]), patch(
            "auxilio_ai.core.inference.ort.InferenceSession", return_value=session
        ):
            engine = InferenceEngine("fake.onnx", target_classes)
        engine.session = session
        return engine, session

    def test_single_class_model_is_automatically_selected(self):
        engine, _session = self.make_engine("{0: 'Drone'}", ["unrelated"])

        self.assertEqual(engine.target_class_ids, {0})
        self.assertIsNone(engine.head_class_id)

    def test_multiple_classes_use_case_insensitive_configured_targets(self):
        engine, _session = self.make_engine(
            "{0: 'Enemy', 1: 'civilian'}",
            ["enemy"],
            output=np.array([[[100], [50], [20], [30], [0.9], [0.1]]], dtype=np.float32),
        )

        self.assertEqual(engine.target_class_ids, {0})
        self.assertEqual(engine.class_names, {0: "Enemy", 1: "civilian"})

    def test_empty_target_list_uses_every_model_class(self):
        engine, _session = self.make_engine("{0: 'Drone', 1: 'Vehicle'}", [])

        self.assertEqual(engine.target_class_ids, {0, 1})

    def test_execution_providers_follow_priority_and_available_backends(self):
        session = FakeSession(
            (1, 3, 320, 320),
            "{0: 'Enemy'}",
            np.zeros((1, 5, 1), dtype=np.float32),
        )
        available = [
            "CPUExecutionProvider",
            "DmlExecutionProvider",
            "CUDAExecutionProvider",
            "TensorrtExecutionProvider",
        ]
        with patch(
            "auxilio_ai.core.inference.ort.get_available_providers",
            return_value=available,
        ), patch(
            "auxilio_ai.core.inference.ort.InferenceSession",
            return_value=session,
        ) as create_session:
            InferenceEngine("fake.onnx")

        self.assertEqual(
            create_session.call_args.kwargs["providers"],
            [
                "TensorrtExecutionProvider",
                "CUDAExecutionProvider",
                "DmlExecutionProvider",
                "CPUExecutionProvider",
            ],
        )

    def test_rgb_input_channels_are_preserved_for_onnx(self):
        engine, session = self.make_engine("{0: 'Enemy'}")
        frame = np.zeros((100, 200, 3), dtype=np.uint8)
        frame[0, 0] = (255, 0, 32)

        engine.processar_frame(frame)

        np.testing.assert_allclose(
            session.last_input[0, :, 0, 0],
            np.array((1.0, 0.0, 32 / 255), dtype=np.float32),
        )

    def test_unmatched_targets_do_not_raise_and_return_no_detection(self):
        engine, _session = self.make_engine(
            "{0: 'Drone', 1: 'Vehicle'}",
            ["Enemy"],
            output=np.array([[[100], [50], [20], [30], [0.9], [0.1]]], dtype=np.float32),
        )

        self.assertEqual(engine.target_class_ids, set())
        visible, x, y = engine.processar_frame(np.zeros((100, 200, 3), dtype=np.uint8))
        self.assertFalse(visible)
        self.assertEqual((x, y), (0, 0))

    def test_dynamic_model_shape_uses_frame_dimensions_without_forcing_320(self):
        engine, session = self.make_engine("{0: 'Enemy'}")

        visible, x, y = engine.processar_frame(np.zeros((100, 200, 3), dtype=np.uint8))

        self.assertTrue(visible)
        self.assertEqual(session.last_input.shape, (1, 3, 100, 200))
        self.assertEqual((x, y), (100, 46))
        self.assertEqual(engine.last_detections[0][:4], (90, 35, 20, 30))

    def test_static_model_shape_resizes_to_its_own_dimensions(self):
        output = np.array([[[40], [20], [8], [12], [0.9]]], dtype=np.float32)
        engine, session = self.make_engine(
            "{0: 'Enemy'}", shape=(1, 3, 40, 80), output=output
        )

        visible, x, y = engine.processar_frame(np.zeros((100, 200, 3), dtype=np.uint8))

        self.assertTrue(visible)
        self.assertEqual(session.last_input.shape, (1, 3, 40, 80))
        self.assertEqual(engine.last_detections[0][:4], (90, 35, 20, 30))
        self.assertEqual((x, y), (100, 45))

    def test_nhwc_uint8_model_uses_declared_layout_and_dtype(self):
        engine, session = self.make_engine(
            "{0: 'Enemy'}",
            shape=(1, 100, 200, 3),
            input_type="tensor(uint8)",
        )

        engine.processar_frame(np.zeros((100, 200, 3), dtype=np.uint8))

        self.assertEqual(engine.input_layout, "NHWC")
        self.assertEqual(session.last_input.shape, (1, 100, 200, 3))
        self.assertEqual(session.last_input.dtype, np.uint8)

    def test_head_metadata_is_case_insensitive_and_uses_native_head_detection(self):
        output = np.array([[[100], [50], [20], [30], [0.1], [0.95]]], dtype=np.float32)
        engine, _session = self.make_engine("{0: 'enemy', 1: 'HEAD'}", ["head"], output=output)

        visible, _x, y = engine.processar_frame(
            np.zeros((100, 200, 3), dtype=np.uint8), aim_point="head"
        )

        self.assertTrue(visible)
        self.assertEqual(engine.head_class_id, 1)
        self.assertEqual(y, 50)

    def test_objectness_output_uses_combined_class_confidence(self):
        output = np.array([[[100], [50], [20], [30], [0.5], [0.9]]], dtype=np.float32)
        engine, _session = self.make_engine("{0: 'Enemy'}", output=output)

        visible, _x, _y = engine.processar_frame(
            np.zeros((100, 200, 3), dtype=np.uint8), conf_threshold=0.4
        )

        self.assertTrue(visible)
        self.assertAlmostEqual(engine.last_detections[0][4], 0.45)

    def test_transposed_yolo_layout_is_not_misread_as_xyxy(self):
        output = np.array([[[20], [20], [50], [40], [0.1], [0.9]]], dtype=np.float32)
        engine, _session = self.make_engine(
            "{0: 'civilian', 1: 'Enemy'}", ["Enemy"], output=output,
        )

        visible, _x, _y = engine.processar_frame(np.zeros((100, 200, 3), dtype=np.uint8))

        self.assertTrue(visible)
        self.assertEqual(engine.last_detections[0][:4], (-5, 0, 50, 40))
        self.assertEqual(engine.last_detections[0][5], 1)

    def test_small_box_filter_uses_box_area_ratio(self):
        engine, _session = self.make_engine("{0: 'Enemy'}")

        visible, _x, _y = engine.processar_frame(
            np.zeros((100, 200, 3), dtype=np.uint8),
            ignore_small=True,
            min_box_area=0.04,
        )

        self.assertFalse(visible)
        self.assertEqual(engine.last_detections, [])

    def test_max_detections_caps_post_nms_results(self):
        output = np.array(
            [[[50, 150], [50, 50], [20, 20], [30, 30], [0.9, 0.8]]],
            dtype=np.float32,
        )
        engine, _session = self.make_engine("{0: 'Enemy'}", output=output)

        engine.processar_frame(np.zeros((100, 200, 3), dtype=np.uint8), max_det=1)

        self.assertEqual(len(engine.last_detections), 1)
        self.assertAlmostEqual(engine.last_detections[0][4], 0.9)

    def test_xyxy_end2end_rows_decode_and_return_xywh_detections(self):
        output = np.array([[[90, 35, 110, 65, 0.9, 0]]], dtype=np.float32)
        engine, _session = self.make_engine("{0: 'Enemy'}", output=output)

        visible, x, y = engine.processar_frame(np.zeros((100, 200, 3), dtype=np.uint8))

        self.assertTrue(visible)
        self.assertEqual(engine.last_detections[0][:4], (90, 35, 20, 30))
        self.assertEqual((x, y), (100, 46))

    def test_three_output_end2end_boxes_scores_classes_are_decoded(self):
        outputs = [
            np.array([[[90, 35, 110, 65]]], dtype=np.float32),
            np.array([[0.9]], dtype=np.float32),
            np.array([[0]], dtype=np.float32),
        ]
        engine, _session = self.make_engine("{0: 'Enemy'}", output=outputs)

        visible, x, y = engine.processar_frame(np.zeros((100, 200, 3), dtype=np.uint8))

        self.assertTrue(visible)
        self.assertEqual(engine.last_detections[0][:4], (90, 35, 20, 30))
        self.assertEqual((x, y), (100, 46))

    def test_unknown_output_shape_logs_and_returns_empty(self):
        engine, _session = self.make_engine(
            "{0: 'Enemy'}",
            output=np.zeros((1, 7, 11), dtype=np.float32),
        )

        with self.assertLogs("auxilio_ai.core.inference", level="WARNING") as logs:
            visible, x, y = engine.processar_frame(np.zeros((100, 200, 3), dtype=np.uint8))

        self.assertFalse(visible)
        self.assertEqual((x, y), (0, 0))
        self.assertEqual(engine.last_detections, [])
        self.assertIn("unsupported", logs.output[0])


if __name__ == "__main__":
    unittest.main()
