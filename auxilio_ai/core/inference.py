import ast
import json
import logging
from collections.abc import Sequence
from os import PathLike
from typing import Literal

import cv2
import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class InferenceEngine:
    def __init__(
        self,
        model_path: str | PathLike[str],
        target_classes: str | Sequence[str] | None = None,
    ) -> None:
        providers = ort.get_available_providers()
        provider_priority = (
            "TensorrtExecutionProvider",
            "CUDAExecutionProvider",
            "DmlExecutionProvider",
            "CPUExecutionProvider",
        )
        selected_providers = [
            provider for provider in provider_priority if provider in providers
        ]

        self.session = ort.InferenceSession(model_path, providers=selected_providers)
        self.output_metas = self.session.get_outputs()
        input_meta = self.session.get_inputs()[0]
        self.input_name = input_meta.name
        input_shape = input_meta.shape
        self.input_layout = self._input_layout(input_shape)
        channel_index = 3 if self.input_layout == "NHWC" else 1
        height_index, width_index = (1, 2) if self.input_layout == "NHWC" else (2, 3)
        self.input_channels = self._static_dimension(input_shape, channel_index)
        self.input_height = self._static_dimension(input_shape, height_index)
        self.input_width = self._static_dimension(input_shape, width_index)
        supported_dtypes = {
            "tensor(float16)": np.float16,
            "tensor(float)": np.float32,
            "tensor(double)": np.float64,
            "tensor(uint8)": np.uint8,
        }
        self.input_dtype = supported_dtypes.get(input_meta.type)
        if self.input_dtype is None:
            raise TypeError(f"Tipo de entrada ONNX nao suportado: {input_meta.type}")

        metadata = self.session.get_modelmeta().custom_metadata_map
        self.class_names = self._parse_class_names(metadata.get("names", ""))
        normalized_names = {class_id: name.casefold() for class_id, name in self.class_names.items()}
        self.head_class_id = next(
            (class_id for class_id, name in normalized_names.items() if name == "head"),
            None,
        )

        if isinstance(target_classes, str):
            target_classes = target_classes.split(",")
        configured_targets = {
            name.strip().casefold()
            for name in (target_classes or ())
            if isinstance(name, str) and name.strip()
        }
        if len(self.class_names) == 1:
            self.target_class_ids = set(self.class_names)
        elif not configured_targets:
            self.target_class_ids = set(self.class_names)
        else:
            self.target_class_ids = {
                class_id for class_id, name in normalized_names.items()
                if name in configured_targets
            }
        self._locked_box = None
        self.last_detections = []
        self._unknown_output_logged = False

    @staticmethod
    def _static_dimension(
        shape: Sequence[int | str | None],
        index: int,
    ) -> int | None:
        if len(shape) <= index:
            return None
        dimension = shape[index]
        return int(dimension) if isinstance(dimension, (int, np.integer)) else None

    @staticmethod
    def _input_layout(shape: Sequence[int | str | None]) -> Literal["NHWC", "NCHW"]:
        if len(shape) == 4:
            channels_first = shape[1] in (1, 3, 4)
            channels_last = shape[3] in (1, 3, 4)
            if channels_last and not channels_first:
                return "NHWC"
        return "NCHW"

    @staticmethod
    def _parse_class_names(raw_names: str) -> dict[int, str]:
        if not raw_names:
            return {}
        try:
            parsed = ast.literal_eval(raw_names)
        except (ValueError, SyntaxError):
            try:
                parsed = json.loads(raw_names)
            except (TypeError, ValueError):
                return {}

        if isinstance(parsed, dict):
            entries = parsed.items()
        elif isinstance(parsed, (list, tuple)):
            entries = enumerate(parsed)
        else:
            return {}

        names = {}
        for class_id, name in entries:
            try:
                numeric_id = int(class_id)
            except (TypeError, ValueError):
                continue
            if isinstance(name, str) and name.strip():
                names[numeric_id] = name.strip()
        return names

    @staticmethod
    def _box_iou(
        box_a: Sequence[float],
        box_b: Sequence[float],
    ) -> float:
        ax, ay, aw, ah = box_a
        bx, by, bw, bh = box_b
        left = max(ax, bx)
        top = max(ay, by)
        right = min(ax + aw, bx + bw)
        bottom = min(ay + ah, by + bh)
        intersection = max(0, right - left) * max(0, bottom - top)
        union = aw * ah + bw * bh - intersection
        return intersection / union if union else 0.0

    def set_target_classes(self, target_classes: str | Sequence[str] | None) -> None:
        if isinstance(target_classes, str):
            target_classes = target_classes.split(",")
        requested = {
            name.strip().casefold()
            for name in (target_classes or ())
            if isinstance(name, str) and name.strip()
        }
        if len(self.class_names) == 1 or not requested:
            self.target_class_ids = set(self.class_names)
        else:
            normalized_names = {
                class_id: name.casefold() for class_id, name in self.class_names.items()
            }
            self.target_class_ids = {
                class_id for class_id, name in normalized_names.items()
                if name in requested
            }

    def _unknown_output(
        self,
        shapes: Sequence[tuple[int, ...]],
        reason: str,
    ) -> list[tuple[float, float, float, float, float, int]]:
        if not self._unknown_output_logged:
            logger.warning(
                "ONNX output format is unsupported (%s; shapes=%s). Returning no detections.",
                reason,
                shapes,
            )
            self._unknown_output_logged = True
        return []

    def _decode_end2end(
        self,
        outputs: Sequence[NDArray[np.generic]],
    ) -> list[tuple[float, float, float, float, float, int]] | None:
        arrays = [np.squeeze(np.asarray(output)) for output in outputs]
        arrays = [
            array.reshape(1) if array.ndim == 0 else array
            for array in arrays
        ]
        if any(array.ndim not in (1, 2) for array in arrays):
            return None

        boxes_index = next(
            (i for i, meta in enumerate(self.output_metas) if any(
                token in meta.name.casefold() for token in ("box", "bbox")
            )),
            None,
        )
        scores_index = next(
            (i for i, meta in enumerate(self.output_metas) if "score" in meta.name.casefold()),
            None,
        )
        classes_index = next(
            (i for i, meta in enumerate(self.output_metas) if any(
                token in meta.name.casefold() for token in ("class", "label")
            )),
            None,
        )
        if boxes_index is None:
            boxes_index = next(
                (
                    i for i, array in enumerate(arrays)
                    if (array.ndim == 2 and array.shape[-1] == 4)
                    or (array.ndim == 1 and array.size == 4)
                ),
                None,
            )
        if boxes_index is None:
            return None
        if scores_index is None:
            scores_index = next(
                (i for i, array in enumerate(arrays) if i != boxes_index and array.ndim == 1),
                None,
            )
        if scores_index is None:
            scores_index = next(
                (i for i, array in enumerate(arrays) if i != boxes_index and array.ndim == 2),
                None,
            )
        if classes_index is None:
            classes_index = next(
                (
                    i for i, array in enumerate(arrays)
                    if i not in (boxes_index, scores_index)
                    and array.ndim == 1
                ),
                None,
            )
        if scores_index is None:
            return None

        boxes = arrays[boxes_index].reshape(-1, 4)
        score_values = arrays[scores_index]
        if score_values.ndim == 2:
            scores = np.max(score_values, axis=1)
            inferred_classes = np.argmax(score_values, axis=1)
        else:
            scores = score_values.reshape(-1)
            inferred_classes = np.zeros(len(scores), dtype=np.int64)
        class_ids = (
            arrays[classes_index].reshape(-1)
            if classes_index is not None
            else inferred_classes
        )
        count = min(len(boxes), len(scores), len(class_ids))
        results = []
        for box, score, class_id in zip(boxes[:count], scores[:count], class_ids[:count]):
            x1, y1, x2, y2 = map(float, box)
            if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 2.0:
                x1, x2 = x1 * (self.input_width or 1), x2 * (self.input_width or 1)
                y1, y2 = y1 * (self.input_height or 1), y2 * (self.input_height or 1)
            results.append((
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                x2 - x1,
                y2 - y1,
                float(score),
                int(class_id),
            ))
        return results

    def _decode_single_output(
        self,
        raw_output: NDArray[np.generic],
    ) -> list[tuple[float, float, float, float, float, int]] | None:
        output = np.asarray(raw_output)
        if output.ndim == 3 and output.shape[0] == 1:
            output = output[0]
        if output.ndim == 1:
            output = output[None, :]
        if output.ndim != 2:
            return None

        feature_counts = (4 + len(self.class_names), 5 + len(self.class_names))
        if output.shape[0] in feature_counts and output.shape[1] not in feature_counts:
            rows = output.T
            format_name = "xywh"
        elif output.shape[1] == 6:
            rows = output
            format_name = "xyxy"
        elif output.shape[0] == 6:
            rows = output.T
            format_name = "xyxy"
        elif output.shape[1] in feature_counts:
            rows = output
            format_name = "xywh"
        else:
            return None

        results = []
        if format_name == "xyxy":
            for row in rows:
                if row.size < 6:
                    continue
                if not np.all(np.isfinite(row[:6])):
                    continue
                x1, y1, x2, y2, confidence, class_id = map(float, row[:6])
                if x2 <= x1 or y2 <= y1:
                    continue
                if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 2.0:
                    x1, x2 = x1 * (self.input_width or 1), x2 * (self.input_width or 1)
                    y1, y2 = y1 * (self.input_height or 1), y2 * (self.input_height or 1)
                results.append((
                    (x1 + x2) / 2,
                    (y1 + y2) / 2,
                    x2 - x1,
                    y2 - y1,
                    confidence,
                    int(class_id),
                ))
            if results:
                return results
            if rows.shape[1] not in feature_counts:
                return []
            format_name = "xywh"

        if format_name == "xywh":
            if rows.shape[1] not in feature_counts:
                rows = output.T
            if rows.shape[1] not in feature_counts:
                return None
        for row in rows:
            if not np.all(np.isfinite(row)):
                continue
            has_objectness = row.size == 5 + len(self.class_names)
            score_offset = 5 if has_objectness else 4
            scores = row[score_offset:]
            if not scores.size:
                continue
            class_id = int(np.argmax(scores))
            confidence = float(scores[class_id])
            if has_objectness:
                confidence *= float(row[4])
            results.append((
                float(row[0]), float(row[1]), float(row[2]), float(row[3]),
                confidence, class_id,
            ))
        return results

    def _decode_outputs(
        self,
        raw_outputs: Sequence[NDArray[np.generic]],
    ) -> list[tuple[float, float, float, float, float, int]]:
        shapes = [tuple(np.asarray(output).shape) for output in raw_outputs]
        if len(raw_outputs) >= 3:
            decoded = self._decode_end2end(raw_outputs)
            if decoded is not None:
                return decoded
            return self._unknown_output(shapes, "could not identify boxes/scores/class_ids")
        if len(raw_outputs) == 1:
            decoded = self._decode_single_output(raw_outputs[0])
            if decoded is not None:
                return decoded
            return self._unknown_output(shapes, "single output shape is not a supported YOLO or xyxy layout")
        return self._unknown_output(shapes, "expected one YOLO output or three end2end outputs")

    def processar_frame(
        self,
        frame: NDArray[np.uint8] | None,
        img_size: int = 320,
        conf_threshold: float = 0.55,
        lock_target: bool = False,
        aim_point: str = "chest",
        iou_threshold: float = 0.45,
        max_det: int = 5,
        filter_distance: bool = False,
        min_distance: float = 0.0,
        max_distance: float = 1.0,
        ignore_small: bool = False,
        min_box_area: float = 0.0,
        ignore_large: bool = False,
        max_box_area: float = 1.0,
    ) -> tuple[bool, int, int]:
        if frame is None:
            self.last_detections = []
            return False, 0, 0
        if not lock_target:
            self._locked_box = None

        frame_height, frame_width = frame.shape[:2]
        if self.input_channels == 1 and frame.ndim == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)[:, :, None]
        elif self.input_channels == 4 and frame.ndim == 3 and frame.shape[2] == 3:
            alpha = np.full((*frame.shape[:2], 1), 255, dtype=frame.dtype)
            frame = np.concatenate((frame, alpha), axis=2)
        target_width = self.input_width or frame_width
        target_height = self.input_height or frame_height
        if (frame_width, frame_height) != (target_width, target_height):
            frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_LINEAR)
            if self.input_channels == 1 and frame.ndim == 2:
                frame = frame[:, :, None]

        image = frame if self.input_layout == "NHWC" else np.transpose(frame, (2, 0, 1))
        image = np.expand_dims(image, axis=0)
        if self.input_dtype != np.uint8:
            image = image.astype(np.float32) / 255.0
        image = image.astype(self.input_dtype, copy=False)

        raw_output = self.session.run(None, {self.input_name: image})
        predictions = self._decode_outputs(raw_output)
        if not predictions:
            self.last_detections = []
            return False, 0, 0

        boxes = []
        confidences = []
        class_ids = []
        image_area = float(target_width * target_height)

        for x_center, y_center, width, height, confidence, class_id in predictions:
            class_id = int(class_id)
            if class_id not in self.target_class_ids:
                continue
            confidence = float(confidence)
            if confidence <= conf_threshold:
                continue
            box_area_ratio = max(0.0, float(width) * float(height)) / image_area
            if filter_distance:
                proxy_distance = 1.0 - min(1.0, box_area_ratio)
                if not min_distance <= proxy_distance <= max_distance:
                    continue
            if ignore_small and box_area_ratio < min_box_area:
                continue
            if ignore_large and box_area_ratio > max_box_area:
                continue

            x_min = int(x_center - width / 2)
            y_min = int(y_center - height / 2)
            boxes.append([x_min, y_min, int(width), int(height)])
            confidences.append(confidence)
            class_ids.append(class_id)

        kept_indices = []
        for class_id in self.target_class_ids:
            class_indices = [i for i, detected_class in enumerate(class_ids) if detected_class == class_id]
            if not class_indices:
                continue
            nms_indices = cv2.dnn.NMSBoxes(
                [boxes[i] for i in class_indices],
                [confidences[i] for i in class_indices],
                conf_threshold,
                iou_threshold,
            )
            if len(nms_indices) > 0:
                kept_indices.extend(class_indices[i] for i in np.asarray(nms_indices).flatten())

        kept_indices.sort(key=confidences.__getitem__, reverse=True)
        kept_indices = kept_indices[:max(0, int(max_det))]
        scale_x = frame_width / target_width
        scale_y = frame_height / target_height
        self.last_detections = [
            (
                int(boxes[i][0] * scale_x),
                int(boxes[i][1] * scale_y),
                int(boxes[i][2] * scale_x),
                int(boxes[i][3] * scale_y),
                confidences[i],
                class_ids[i],
            )
            for i in kept_indices
        ]
        if not kept_indices:
            return False, 0, 0

        center_x = target_width // 2
        center_y = target_height // 2
        candidates = []
        for i in kept_indices:
            x, y, width, height = boxes[i]
            aim_x = x + width // 2
            if class_ids[i] == self.head_class_id and aim_point == "head":
                aim_y = y + height // 2
            else:
                offsets = {"head": 0.18, "chest": 0.38, "belly": 0.62}
                aim_y = y + int(height * offsets.get(aim_point, 0.38))
            candidates.append((boxes[i], aim_x, aim_y, class_ids[i]))

        head_candidates = [item for item in candidates if item[3] == self.head_class_id]
        if aim_point == "head" and head_candidates:
            candidates = head_candidates
        elif aim_point != "head" and self.head_class_id is not None:
            candidates = [item for item in candidates if item[3] != self.head_class_id]
            if not candidates:
                return False, 0, 0

        if self._locked_box is not None and lock_target:
            locked_x = self._locked_box[0] + self._locked_box[2] / 2
            locked_y = self._locked_box[1] + self._locked_box[3] / 2
            max_shift = max(24, int(target_width * 0.10))
            matches = []
            for candidate in candidates:
                box = candidate[0]
                box_x = box[0] + box[2] / 2
                box_y = box[1] + box[3] / 2
                distance = np.hypot(box_x - locked_x, box_y - locked_y)
                overlap = self._box_iou(self._locked_box, box)
                if overlap >= 0.1 or distance <= max_shift:
                    matches.append((overlap, -distance, candidate))
            if not matches:
                return False, 0, 0
            selected = max(matches, key=lambda item: (item[0], item[1]))[2]
        else:
            selected = min(
                candidates,
                key=lambda item: np.hypot(item[1] - center_x, item[2] - center_y),
            )

        if lock_target:
            self._locked_box = selected[0].copy()
        return True, int(selected[1] * scale_x), int(selected[2] * scale_y)
