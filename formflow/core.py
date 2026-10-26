from __future__ import annotations

from dataclasses import dataclass, field
from math import acos, degrees, sqrt
from typing import ClassVar, Mapping, Sequence


Point = tuple[float, float]


def angle(a: Point, b: Point, c: Point) -> float:
    """Return the smaller angle ABC in degrees."""
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    mag = sqrt(ba[0] ** 2 + ba[1] ** 2) * sqrt(bc[0] ** 2 + bc[1] ** 2)
    if mag == 0:
        return 0.0
    cosine = max(-1.0, min(1.0, (ba[0] * bc[0] + ba[1] * bc[1]) / mag))
    return degrees(acos(cosine))


@dataclass(frozen=True)
class ExerciseProfile:
    key: str
    name: str
    joint: tuple[str, str, str]
    top_angle: float
    bottom_angle: float
    cue: str
    secondary_joint: tuple[str, str, str] | None = None
    secondary_range: tuple[float, float] | None = None


PROFILES: dict[str, ExerciseProfile] = {
    "squat": ExerciseProfile(
        "squat", "Squat", ("left_hip", "left_knee", "left_ankle"), 160, 92,
        "Keep your knees tracking over your feet.",
        ("left_shoulder", "left_hip", "left_knee"), (38, 180),
    ),
    "pushup": ExerciseProfile(
        "pushup", "Push-up", ("left_shoulder", "left_elbow", "left_wrist"), 155, 100,
        "Keep your body long and lower with control.",
        ("left_shoulder", "left_hip", "left_ankle"), (155, 180),
    ),
    "lunge": ExerciseProfile(
        "lunge", "Lunge", ("left_hip", "left_knee", "left_ankle"), 158, 92,
        "Keep your front knee stacked over the ankle.",
        ("left_shoulder", "left_hip", "left_knee"), (45, 180),
    ),
    "curl": ExerciseProfile(
        "curl", "Bicep curl", ("left_shoulder", "left_elbow", "left_wrist"), 152, 48,
        "Keep your elbow close to your side.",
    ),
}


@dataclass
class FrameResult:
    angle: float = 0.0
    range_percent: float = 0.0
    reps: int = 0
    stage: str = "READY"
    form_score: int = 0
    tempo_seconds: float = 0.0
    feedback: str = "Step into frame to begin"
    good_form: bool = False


@dataclass
class ExerciseTracker:
    profile: ExerciseProfile
    reps: int = 0
    stage: str = "READY"
    last_transition: float | None = None
    rep_started: float | None = None
    last_tempo: float = 0.0
    _scores: list[float] = field(default_factory=list)

    MIN_REP_SECONDS: ClassVar[float] = 0.45
    MAX_REP_SECONDS: ClassVar[float] = 15.0

    def reset(self) -> None:
        self.reps = 0
        self.stage = "READY"
        self.last_transition = None
        self.rep_started = None
        self.last_tempo = 0.0
        self._scores.clear()

    def cancel_cycle(self) -> None:
        """Discard partial motion without changing the completed rep total."""
        self.stage = "READY"
        self.last_transition = None
        self.rep_started = None
        self._scores.clear()

    def update(self, landmarks: Mapping[str, Point], timestamp: float) -> FrameResult:
        try:
            primary = angle(*(landmarks[name] for name in self.profile.joint))
        except KeyError:
            return FrameResult(reps=self.reps, stage=self.stage)

        span = max(1.0, self.profile.top_angle - self.profile.bottom_angle)
        progress = max(0.0, min(100.0, (self.profile.top_angle - primary) / span * 100))
        depth_score = 100.0 - min(100.0, abs(primary - self.profile.bottom_angle) / span * 100)
        good_form = True
        secondary_score = 100.0

        if self.profile.secondary_joint and self.profile.secondary_range:
            secondary = angle(*(landmarks[name] for name in self.profile.secondary_joint))
            low, high = self.profile.secondary_range
            good_form = low <= secondary <= high
            secondary_score = 100.0 if good_form else max(0.0, 100 - min(abs(secondary - low), abs(secondary - high)) * 3)

        old_stage = self.stage
        if primary >= self.profile.top_angle:
            if self.stage == "DOWN":
                if self.rep_started is not None:
                    duration = timestamp - self.rep_started
                    if self.MIN_REP_SECONDS <= duration <= self.MAX_REP_SECONDS:
                        self.reps += 1
                        self.last_tempo = duration
            self.stage = "UP"
            self.rep_started = None
        elif primary <= self.profile.bottom_angle:
            # A rep is armed only after a confirmed top position. Entering the
            # frame already crouched must never create a repetition.
            if self.stage == "UP":
                self.rep_started = self.last_transition or timestamp
                self.stage = "DOWN"
        if self.last_transition is None or self.stage != old_stage:
            self.last_transition = timestamp

        # Alignment is the live safety signal; depth adds credit without making a
        # correct starting position look like poor form.
        score = 0.70 * secondary_score + 15.0 + 0.15 * depth_score
        self._scores.append(score)
        self._scores = self._scores[-45:]
        smooth_score = int(round(sum(self._scores) / len(self._scores)))
        if self.profile.key == "pushup" and good_form:
            feedback = (
                "Press up until your arms are straight" if self.stage == "DOWN"
                else "Lower until your elbows reach about 90°" if progress < 70
                else "Depth reached · press up with control"
            )
        else:
            feedback = (
            "Excellent alignment — keep that rhythm"
            if good_form and progress > 70
            else self.profile.cue
            if not good_form
            else "Move through your full range"
            if progress < 55 and self.stage == "DOWN"
            else "Controlled movement — keep going"
            )
        return FrameResult(primary, progress, self.reps, self.stage, smooth_score, self.last_tempo, feedback, good_form)


@dataclass(frozen=True)
class PersonSignature:
    center: Point
    scale: float


def person_signature(landmarks: Mapping[str, Point]) -> PersonSignature:
    shoulders = (landmarks["left_shoulder"], landmarks["right_shoulder"])
    hips = (landmarks["left_hip"], landmarks["right_hip"])
    shoulder_mid = ((shoulders[0][0] + shoulders[1][0]) / 2, (shoulders[0][1] + shoulders[1][1]) / 2)
    hip_mid = ((hips[0][0] + hips[1][0]) / 2, (hips[0][1] + hips[1][1]) / 2)
    center = ((shoulder_mid[0] + hip_mid[0]) / 2, (shoulder_mid[1] + hip_mid[1]) / 2)
    scale = max(0.01, sqrt((shoulder_mid[0] - hip_mid[0]) ** 2 + (shoulder_mid[1] - hip_mid[1]) ** 2))
    return PersonSignature(center, scale)


@dataclass
class SmartSession:
    """Protect rep counting from passers-by, dropouts, and pose jitter."""

    tracker: ExerciseTracker
    calibration_frames: int = 30
    loss_frames: int = 8
    calibrated: bool = False
    stable_frames: int = 0
    missing_frames: int = 0
    signature: PersonSignature | None = None
    _previous_signature: PersonSignature | None = None

    def reset(self, keep_reps: bool = False) -> None:
        reps = self.tracker.reps if keep_reps else 0
        self.tracker.reset()
        self.tracker.reps = reps
        self.calibrated = False
        self.stable_frames = 0
        self.missing_frames = 0
        self.signature = None
        self._previous_signature = None

    def missing(self, reason: str = "No person in the workout zone") -> FrameResult:
        self.missing_frames += 1
        if self.missing_frames >= self.loss_frames:
            self.calibrated = False
            self.stable_frames = 0
            self.signature = None
            self._previous_signature = None
            self.tracker.cancel_cycle()
        return FrameResult(
            reps=self.tracker.reps,
            stage="PAUSED" if self.calibrated else "NO PERSON",
            tempo_seconds=self.tracker.last_tempo,
            feedback=reason,
        )

    def observe(self, landmarks: Mapping[str, Point], timestamp: float, counting_enabled: bool = True) -> FrameResult:
        try:
            current = person_signature(landmarks)
            primary = angle(*(landmarks[name] for name in self.tracker.profile.joint))
        except KeyError:
            return self.missing("Move your full body into the workout zone")

        self.missing_frames = 0
        if self.signature and self._different_person(current, self.signature):
            self.reset(keep_reps=True)
            self.signature = current
            return FrameResult(
                reps=self.tracker.reps, stage="REPOSITION",
                feedback="Person changed · hold the starting pose to relock",
            )

        motion = 0.0
        if self._previous_signature:
            motion = self._distance(current.center, self._previous_signature.center) / max(current.scale, 0.01)
        self._previous_signature = current

        if not self.calibrated:
            at_start = primary >= self.tracker.profile.top_angle - 8
            self.stable_frames = self.stable_frames + 1 if at_start and motion < 0.10 else 0
            progress = min(100, round(self.stable_frames / self.calibration_frames * 100))
            if self.stable_frames < self.calibration_frames:
                return FrameResult(
                    angle=primary, reps=self.tracker.reps, stage="CALIBRATING",
                    range_percent=progress,
                    tempo_seconds=self.tracker.last_tempo,
                    feedback=f"Hold the starting pose · {progress}% locked",
                )
            self.calibrated = True
            self.signature = current
            self.tracker.cancel_cycle()

        # Slowly adapt the lock to natural movement without allowing a passer-by
        # to replace the active athlete in one frame.
        if self.signature:
            self.signature = PersonSignature(
                center=(self.signature.center[0] * 0.96 + current.center[0] * 0.04,
                        self.signature.center[1] * 0.96 + current.center[1] * 0.04),
                scale=self.signature.scale * 0.96 + current.scale * 0.04,
            )
        if not counting_enabled:
            self.tracker.cancel_cycle()
            return FrameResult(
                angle=primary, reps=self.tracker.reps, stage="SET PAUSED",
                tempo_seconds=self.tracker.last_tempo,
                feedback="Set paused · camera tracking remains local and active",
            )
        result = self.tracker.update(landmarks, timestamp)
        if result.stage == "READY":
            result.feedback = "Return to the starting position to arm counting"
        return result

    @staticmethod
    def _distance(a: Point, b: Point) -> float:
        return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    @classmethod
    def _different_person(cls, current: PersonSignature, locked: PersonSignature) -> bool:
        position_jump = cls._distance(current.center, locked.center) / max(locked.scale, 0.01)
        scale_ratio = current.scale / max(locked.scale, 0.01)
        return position_jump > 1.15 or not 0.58 <= scale_ratio <= 1.72


def normalized_landmarks(raw: Sequence[object], names: Mapping[str, int]) -> dict[str, Point]:
    return {name: (float(raw[index].x), float(raw[index].y)) for name, index in names.items()}
