from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import cv2

from .core import ExerciseTracker, FrameResult, SmartSession, normalized_landmarks


LANDMARK_NAMES = {
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13, "right_elbow": 14,
    "left_wrist": 15, "right_wrist": 16,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
}


@dataclass
class ProcessedFrame:
    image: Any
    result: FrameResult
    person_visible: bool


class PoseEngine:
    def __init__(self) -> None:
        import mediapipe as mp

        self.mp = mp
        self.pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            min_detection_confidence=0.55,
            min_tracking_confidence=0.55,
        )
        self.drawer = mp.solutions.drawing_utils
        self.session: SmartSession | None = None
        self.tracker_id: int | None = None

    @staticmethod
    def _inside_workout_zone(points: dict[str, tuple[float, float]]) -> bool:
        key_points = [points[name] for name in ("left_shoulder", "right_shoulder", "left_hip", "right_hip")]
        center_x = sum(point[0] for point in key_points) / len(key_points)
        center_y = sum(point[1] for point in key_points) / len(key_points)
        return 0.16 <= center_x <= 0.84 and 0.08 <= center_y <= 0.86

    @staticmethod
    def _best_side(raw: list[Any], threshold: float = 0.52) -> str | None:
        """Choose the body side the camera can actually see.

        Side-on push-ups commonly hide one arm. Requiring the left side made
        tracking appear frozen whenever the athlete faced the other direction.
        """
        indices = {
            "left": (11, 13, 15, 23, 25, 27),
            "right": (12, 14, 16, 24, 26, 28),
        }
        scores = {
            side: sum(float(getattr(raw[index], "visibility", 1.0)) for index in group) / len(group)
            for side, group in indices.items()
        }
        side = max(scores, key=scores.get)
        return side if scores[side] >= threshold else None

    @staticmethod
    def _use_side(points: dict[str, tuple[float, float]], side: str) -> dict[str, tuple[float, float]]:
        if side == "left":
            return points
        selected = dict(points)
        for joint in ("shoulder", "elbow", "wrist", "hip", "knee", "ankle"):
            selected[f"left_{joint}"] = points[f"right_{joint}"]
        return selected

    def process(self, frame: Any, tracker: ExerciseTracker, counting_enabled: bool = True) -> ProcessedFrame:
        if self.session is None or self.tracker_id != id(tracker):
            self.session = SmartSession(tracker)
            self.tracker_id = id(tracker)
        height, width = frame.shape[:2]
        zone_a, zone_b = (int(width * 0.16), int(height * 0.08)), (int(width * 0.84), int(height * 0.94))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        output = self.pose.process(rgb)
        result = FrameResult(reps=tracker.reps, stage="NO PERSON")
        visible = bool(output.pose_landmarks)
        if output.pose_landmarks:
            raw = output.pose_landmarks.landmark
            points = normalized_landmarks(raw, LANDMARK_NAMES)
            side = self._best_side(raw)
            if side is None:
                result = self.session.missing("Key joints are hidden · show one full side of your body")
            elif not self._inside_workout_zone(points):
                result = self.session.missing("Move into the marked workout zone")
            else:
                points = self._use_side(points, side)
                result = self.session.observe(points, time.monotonic(), counting_enabled)
                self.drawer.draw_landmarks(
                    frame, output.pose_landmarks, self.mp.solutions.pose.POSE_CONNECTIONS,
                    self.drawer.DrawingSpec(color=(54, 131, 255), thickness=2, circle_radius=3),
                    self.drawer.DrawingSpec(color=(89, 219, 124), thickness=3, circle_radius=2),
                )
        else:
            result = self.session.missing()

        zone_color = (89, 219, 124) if result.stage not in {"NO PERSON", "REPOSITION"} else (54, 131, 255)
        corner = 34
        thickness = 2
        for x, y, sx, sy in (
            (zone_a[0], zone_a[1], 1, 1), (zone_b[0], zone_a[1], -1, 1),
            (zone_a[0], zone_b[1], 1, -1), (zone_b[0], zone_b[1], -1, -1),
        ):
            cv2.line(frame, (x, y), (x + sx * corner, y), zone_color, thickness)
            cv2.line(frame, (x, y), (x, y + sy * corner), zone_color, thickness)
        return ProcessedFrame(frame, result, visible)

    def close(self) -> None:
        self.pose.close()
