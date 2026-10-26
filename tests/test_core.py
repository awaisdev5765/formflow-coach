from types import SimpleNamespace

from formflow.core import PROFILES, ExerciseTracker, SmartSession, angle, normalized_landmarks


def pose(knee_x=0.0, ankle_x=0.0, center_x=0.5):
    return {
        "left_shoulder": (center_x - 0.08, 0.25), "right_shoulder": (center_x + 0.08, 0.25),
        "left_elbow": (center_x - 0.1, 0.42), "right_elbow": (center_x + 0.1, 0.42),
        "left_wrist": (center_x - 0.1, 0.58), "right_wrist": (center_x + 0.1, 0.58),
        "left_hip": (center_x - 0.06, 0.5), "right_hip": (center_x + 0.06, 0.5),
        "left_knee": (center_x + knee_x, 0.7), "right_knee": (center_x + knee_x + 0.08, 0.7),
        "left_ankle": (center_x + ankle_x, 0.9), "right_ankle": (center_x + ankle_x + 0.08, 0.9),
    }


def test_angle_is_ninety_degrees():
    assert round(angle((1, 0), (0, 0), (0, 1))) == 90


def test_zero_length_angle_is_safe():
    assert angle((0, 0), (0, 0), (1, 1)) == 0


def test_squat_rep_counts_after_down_then_up():
    tracker = ExerciseTracker(PROFILES["squat"])
    down = {
        "left_hip": (0, 0), "left_knee": (0, 1), "left_ankle": (1, 1),
        "left_shoulder": (0, -1),
    }
    up = {
        "left_hip": (0, 0), "left_knee": (0, 1), "left_ankle": (0, 2),
        "left_shoulder": (0, -1),
    }
    tracker.update(up, 0.0)
    tracker.update(down, 1.0)
    result = tracker.update(up, 3.0)
    assert result.reps == 1
    assert result.tempo_seconds == 2.0


def test_entering_frame_in_down_pose_cannot_create_rep():
    tracker = ExerciseTracker(PROFILES["squat"])
    down = {
        "left_hip": (0, 0), "left_knee": (0, 1), "left_ankle": (1, 1),
        "left_shoulder": (0, -1),
    }
    up = {
        "left_hip": (0, 0), "left_knee": (0, 1), "left_ankle": (0, 2),
        "left_shoulder": (0, -1),
    }
    tracker.update(down, 1.0)
    assert tracker.update(up, 2.0).reps == 0


def test_impossibly_fast_motion_is_rejected():
    tracker = ExerciseTracker(PROFILES["squat"])
    up = {"left_hip": (0, 0), "left_knee": (0, 1), "left_ankle": (0, 2), "left_shoulder": (0, -1)}
    down = {"left_hip": (0, 0), "left_knee": (0, 1), "left_ankle": (1, 1), "left_shoulder": (0, -1)}
    tracker.update(up, 0.0)
    tracker.update(down, 0.1)
    assert tracker.update(up, 0.2).reps == 0


def test_correct_starting_position_does_not_show_bad_form():
    tracker = ExerciseTracker(PROFILES["pushup"])
    points = {
        "left_shoulder": (0, 0), "left_elbow": (1, 0), "left_wrist": (2, 0),
        "left_hip": (1, 0), "left_ankle": (2, 0),
    }
    result = tracker.update(points, 1.0)
    assert result.form_score >= 85


def test_upright_squat_is_valid_starting_form():
    tracker = ExerciseTracker(PROFILES["squat"])
    points = {
        "left_shoulder": (0, -1), "left_hip": (0, 0),
        "left_knee": (0, 1), "left_ankle": (0, 2),
    }
    result = tracker.update(points, 1.0)
    assert result.good_form
    assert result.form_score >= 85


def test_all_exercise_profiles_have_valid_thresholds_and_joints():
    assert set(PROFILES) == {"squat", "pushup", "lunge", "curl"}
    for key, profile in PROFILES.items():
        assert profile.key == key
        assert profile.bottom_angle < profile.top_angle
        assert len(profile.joint) == 3
        assert profile.cue.endswith(".")


def test_reset_clears_entire_session_state():
    tracker = ExerciseTracker(PROFILES["curl"])
    tracker.reps = 4
    tracker.stage = "DOWN"
    tracker.last_tempo = 2.4
    tracker.last_transition = 5.0
    tracker.rep_started = 4.0
    tracker._scores.extend([75, 90])
    tracker.reset()
    assert tracker.reps == 0
    assert tracker.stage == "READY"
    assert tracker.last_tempo == 0
    assert tracker.last_transition is None
    assert tracker.rep_started is None
    assert tracker._scores == []


def test_missing_landmarks_fails_safely():
    result = ExerciseTracker(PROFILES["squat"]).update({}, 1.0)
    assert result.reps == 0
    assert result.feedback == "Step into frame to begin"


def test_normalized_landmark_conversion():
    raw = [SimpleNamespace(x=0.25, y=0.75), SimpleNamespace(x=0.5, y=0.1)]
    assert normalized_landmarks(raw, {"a": 0, "b": 1}) == {"a": (0.25, 0.75), "b": (0.5, 0.1)}


def test_smart_session_requires_stable_calibration():
    session = SmartSession(ExerciseTracker(PROFILES["squat"]), calibration_frames=3)
    standing = pose()
    assert session.observe(standing, 0.0).stage == "CALIBRATING"
    assert session.observe(standing, 0.1).stage == "CALIBRATING"
    result = session.observe(standing, 0.2)
    assert session.calibrated
    assert result.stage == "UP"


def test_absence_cancels_partial_rep_but_preserves_total():
    tracker = ExerciseTracker(PROFILES["squat"])
    tracker.reps = 5
    tracker.stage = "DOWN"
    session = SmartSession(tracker, loss_frames=2, calibrated=True)
    session.missing()
    result = session.missing()
    assert result.reps == 5
    assert not session.calibrated
    assert tracker.stage == "READY"


def test_new_person_requires_recalibration_without_adding_rep():
    tracker = ExerciseTracker(PROFILES["squat"])
    session = SmartSession(tracker, calibration_frames=1)
    session.observe(pose(center_x=0.35), 0.0)
    tracker.reps = 2
    result = session.observe(pose(center_x=0.78), 1.0)
    assert result.stage == "REPOSITION"
    assert result.reps == 2
    assert not session.calibrated


def test_paused_set_cannot_count_and_keeps_camera_session_ready():
    tracker = ExerciseTracker(PROFILES["squat"])
    session = SmartSession(tracker, calibration_frames=1)
    session.observe(pose(), 0.0)
    result = session.observe(pose(knee_x=0.2, ankle_x=0.35), 1.0, counting_enabled=False)
    assert result.stage == "SET PAUSED"
    assert result.reps == 0


def test_pushup_counts_one_complete_controlled_cycle():
    tracker = ExerciseTracker(PROFILES["pushup"])
    straight = {
        "left_shoulder": (0, 0), "left_elbow": (1, 0), "left_wrist": (2, 0),
        "left_hip": (1, 0), "left_ankle": (2, 0),
    }
    bottom = {
        "left_shoulder": (0, 0), "left_elbow": (1, 0), "left_wrist": (1, 1),
        "left_hip": (1, 0), "left_ankle": (2, 0),
    }
    assert tracker.update(straight, 0.0).stage == "UP"
    assert tracker.update(bottom, 0.8).stage == "DOWN"
    result = tracker.update(straight, 1.8)
    assert result.reps == 1
    assert result.stage == "UP"
    assert result.tempo_seconds == 1.0
