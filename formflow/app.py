from __future__ import annotations

import sys
import threading
from pathlib import Path

import cv2
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QIcon, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
    QProgressBar, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from .core import PROFILES, ExerciseTracker, FrameResult


ROOT = Path(__file__).resolve().parent.parent


class MetricStat(QWidget):
    def __init__(self, label: str, value: str, suffix: str = "") -> None:
        super().__init__()
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
        title = QLabel(label.upper())
        title.setObjectName("eyebrow")
        row = QHBoxLayout()
        row.setSpacing(4)
        self.value = QLabel(value)
        self.value.setObjectName("metricValue")
        suffix_label = QLabel(suffix)
        suffix_label.setObjectName("metricSuffix")
        suffix_label.setAlignment(Qt.AlignmentFlag.AlignBottom)
        row.addWidget(self.value)
        row.addWidget(suffix_label)
        row.addStretch()
        box.addWidget(title)
        box.addLayout(row)


class FormFlowWindow(QMainWindow):
    camera_ready = Signal(object, object, int)
    camera_failed = Signal(str, int)

    def __init__(self, auto_start_camera: bool = True) -> None:
        super().__init__()
        self.setWindowTitle("FormFlow Coach")
        self.resize(1320, 840)
        self.setMinimumSize(980, 680)
        icon = ROOT / "assets" / "app-icon.png"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.capture = None
        self.engine = None
        self.tracker = ExerciseTracker(PROFILES["squat"])
        self.camera_running = False
        self.camera_requesting = False
        self.camera_generation = 0
        self.set_paused = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._next_frame)
        self.camera_ready.connect(self._camera_started)
        self.camera_failed.connect(self._camera_start_failed)
        self._build_ui()
        self._shortcuts()
        if auto_start_camera:
            QTimer.singleShot(450, self._request_camera)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(26, 20, 26, 24)
        page.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(14)
        logo = QLabel()
        pixmap = QPixmap(str(ROOT / "assets" / "app-icon.png"))
        logo.setPixmap(pixmap.scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo.setFixedSize(40, 40)
        identity = QVBoxLayout()
        identity.setSpacing(0)
        name = QLabel("FormFlow")
        name.setObjectName("brand")
        tagline = QLabel("MOVEMENT, MEASURED")
        tagline.setObjectName("eyebrow")
        identity.addWidget(name)
        identity.addWidget(tagline)
        header.addWidget(logo)
        header.addLayout(identity)
        header.addStretch()
        exercise_label = QLabel("EXERCISE")
        exercise_label.setObjectName("eyebrow")
        self.exercise = QComboBox()
        for key, profile in PROFILES.items():
            self.exercise.addItem(profile.name, key)
        self.exercise.setAccessibleName("Exercise type")
        self.exercise.currentIndexChanged.connect(self._change_exercise)
        self.camera_button = QPushButton("Turn camera on")
        self.camera_button.setObjectName("cameraButton")
        self.camera_button.setAccessibleName("Turn camera on or off")
        self.camera_button.clicked.connect(self._toggle_camera)
        header.addWidget(exercise_label)
        header.addWidget(self.exercise)
        header.addWidget(self.camera_button)
        page.addLayout(header)

        stage = QFrame()
        stage.setObjectName("cameraStage")
        stage_grid = QGridLayout(stage)
        stage_grid.setContentsMargins(0, 0, 0, 0)
        self.camera_stack = QStackedWidget()
        self.camera_stack.setObjectName("cameraStack")

        permission = QWidget()
        permission.setObjectName("permissionView")
        permission_box = QVBoxLayout(permission)
        permission_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        permission_box.setSpacing(10)
        permission_kicker = QLabel("CAMERA ACCESS")
        permission_kicker.setObjectName("eyebrowOrange")
        permission_kicker.setAlignment(Qt.AlignmentFlag.AlignCenter)
        permission_title = QLabel("Your workout stays on this device")
        permission_title.setObjectName("permissionTitle")
        permission_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        permission_copy = QLabel("FormFlow uses your camera only for live pose analysis.\nFrames are never recorded, uploaded, or saved.")
        permission_copy.setObjectName("muted")
        permission_copy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.permission_action = QPushButton("Allow camera")
        self.permission_action.setObjectName("primaryButton")
        self.permission_action.setFixedWidth(180)
        self.permission_action.clicked.connect(self._request_camera)
        permission_box.addStretch()
        permission_box.addWidget(permission_kicker)
        permission_box.addWidget(permission_title)
        permission_box.addWidget(permission_copy)
        permission_box.addSpacing(10)
        permission_box.addWidget(self.permission_action, alignment=Qt.AlignmentFlag.AlignCenter)
        permission_box.addStretch()

        live = QWidget()
        live_box = QVBoxLayout(live)
        live_box.setContentsMargins(0, 0, 0, 0)
        self.video = QLabel()
        self.video.setObjectName("video")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video.setMinimumSize(720, 470)
        live_box.addWidget(self.video)
        self.camera_stack.addWidget(permission)
        self.camera_stack.addWidget(live)
        stage_grid.addWidget(self.camera_stack, 0, 0)

        self.hud = QWidget()
        self.hud.setObjectName("hud")
        self.hud.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hud.setVisible(False)
        hud_box = QVBoxLayout(self.hud)
        hud_box.setContentsMargins(20, 18, 20, 18)
        top_hud = QHBoxLayout()
        self.camera_state = QLabel("●  CAMERA CHECKING")
        self.camera_state.setObjectName("cameraState")
        self.status_pill = QLabel("READY")
        self.status_pill.setObjectName("statusPill")
        top_hud.addWidget(self.camera_state)
        top_hud.addStretch()
        top_hud.addWidget(self.status_pill)
        hud_box.addLayout(top_hud)
        hud_box.addStretch()
        self.rep_hero = QLabel("0")
        self.rep_hero.setObjectName("repHero")
        self.rep_hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rep_caption = QLabel("REPS")
        rep_caption.setObjectName("heroCaption")
        rep_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hud_box.addWidget(self.rep_hero)
        hud_box.addWidget(rep_caption)
        hud_box.addStretch()
        self.feedback = QLabel("Preparing camera…")
        self.feedback.setObjectName("coachCue")
        self.feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback.setWordWrap(True)
        hud_box.addWidget(self.feedback, alignment=Qt.AlignmentFlag.AlignCenter)
        stage_grid.addWidget(self.hud, 0, 0)
        page.addWidget(stage, 1)

        performance = QFrame()
        performance.setObjectName("performanceStrip")
        strip = QHBoxLayout(performance)
        strip.setContentsMargins(20, 12, 20, 12)
        strip.setSpacing(26)
        self.reps = MetricStat("Repetitions", "0")
        self.joint_angle = MetricStat("Joint angle", "—", "°")
        self.tempo = MetricStat("Rep tempo", "—", "sec")
        for metric in (self.reps, self.joint_angle, self.tempo):
            strip.addWidget(metric, 1)
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.Shape.VLine)
        strip.addWidget(divider)
        score_block = QVBoxLayout()
        score_title = QLabel("FORM")
        score_title.setObjectName("eyebrow")
        self.score = QLabel("—")
        self.score.setObjectName("scoreCompact")
        score_block.addWidget(score_title)
        score_block.addWidget(self.score)
        strip.addLayout(score_block)
        self.range_bar = QProgressBar()
        self.range_bar.setRange(0, 100)
        self.range_bar.setValue(0)
        self.range_bar.setFormat("RANGE  %p%")
        self.range_bar.setFixedWidth(210)
        strip.addWidget(self.range_bar)
        self.set_button = QPushButton("Pause set")
        self.set_button.setObjectName("quietButton")
        self.set_button.clicked.connect(self._toggle_set)
        strip.addWidget(self.set_button)
        reset = QPushButton("Reset set")
        reset.setObjectName("quietButton")
        reset.clicked.connect(self._reset)
        strip.addWidget(reset)
        page.addWidget(performance)

    def _shortcuts(self) -> None:
        camera_action = QAction(self)
        camera_action.setShortcut(QKeySequence("Space"))
        camera_action.triggered.connect(self._toggle_camera)
        self.addAction(camera_action)
        reset_action = QAction(self)
        reset_action.setShortcut(QKeySequence("Ctrl+R"))
        reset_action.triggered.connect(self._reset)
        self.addAction(reset_action)

    def _change_exercise(self) -> None:
        self.tracker = ExerciseTracker(PROFILES[self.exercise.currentData()])
        self._render_result(FrameResult(feedback=f"Ready for {self.tracker.profile.name.lower()}s"))

    def _request_camera(self) -> None:
        if self.camera_running or self.camera_requesting:
            return
        self.camera_requesting = True
        self.camera_generation += 1
        generation = self.camera_generation
        self.camera_state.setText("●  REQUESTING CAMERA")
        self.permission_action.setEnabled(False)
        self.permission_action.setText("Checking…")
        self.camera_button.setEnabled(False)
        self.camera_button.setText("Starting…")
        self.feedback.setText("Opening the camera and loading pose intelligence…")
        threading.Thread(target=self._camera_worker, args=(generation,), daemon=True).start()

    def _camera_worker(self, generation: int) -> None:
        try:
            from .vision import PoseEngine

            capture = cv2.VideoCapture(0)
            if not capture.isOpened():
                capture.release()
                raise RuntimeError("Camera access was not granted or no camera is available.")
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            engine = PoseEngine()
            self.camera_ready.emit(capture, engine, generation)
        except Exception as exc:
            self.camera_failed.emit(str(exc), generation)

    def _camera_started(self, capture, engine, generation: int) -> None:
        if generation != self.camera_generation:
            capture.release()
            engine.close()
            return
        self.capture = capture
        self.engine = engine
        self.camera_requesting = False
        self.camera_running = True
        self.camera_button.setEnabled(True)
        self.camera_button.setText("Camera on")
        self.camera_button.setProperty("active", True)
        self.camera_state.setText("●  CAMERA ON · LOCAL ONLY")
        self.camera_state.setProperty("active", True)
        self.camera_stack.setCurrentIndex(1)
        self.hud.setVisible(True)
        self.feedback.setText("Step into the marked zone and hold your starting pose")
        self.timer.start(30)
        for widget in (self.camera_button, self.camera_state):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _camera_start_failed(self, message: str, generation: int) -> None:
        if generation != self.camera_generation:
            return
        self.camera_requesting = False
        self.capture = self.engine = None
        self.camera_running = False
        self.camera_stack.setCurrentIndex(0)
        self.hud.setVisible(False)
        self.camera_state.setText("●  CAMERA NEEDS ACCESS")
        self.permission_action.setEnabled(True)
        self.permission_action.setText("Retry camera")
        self.feedback.setText(message)
        self.camera_button.setEnabled(True)
        self.camera_button.setText("Retry camera")
        self.camera_button.setProperty("active", False)

    def _toggle_camera(self) -> None:
        self._stop_camera() if self.camera_running else self._request_camera()

    def _stop_camera(self) -> None:
        self.camera_generation += 1
        self.camera_requesting = False
        self.timer.stop()
        if self.capture:
            self.capture.release()
        if self.engine:
            self.engine.close()
        self.capture = self.engine = None
        self.camera_running = False
        self.camera_button.setText("Turn camera on")
        self.camera_button.setEnabled(True)
        self.camera_button.setProperty("active", False)
        self.camera_state.setText("●  CAMERA OFF")
        self.camera_state.setProperty("active", False)
        self.permission_action.setEnabled(True)
        self.permission_action.setText("Turn camera on")
        self.camera_stack.setCurrentIndex(0)
        self.hud.setVisible(False)
        for widget in (self.camera_button, self.camera_state):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _next_frame(self) -> None:
        ok, frame = self.capture.read()
        if not ok:
            self.camera_state.setText("●  CAMERA INTERRUPTED")
            return
        frame = cv2.flip(frame, 1)
        processed = self.engine.process(frame, self.tracker, counting_enabled=not self.set_paused)
        rgb = cv2.cvtColor(processed.image, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(rgb.data, width, height, channels * width, QImage.Format.Format_RGB888).copy()
        self.video.setPixmap(QPixmap.fromImage(image).scaled(
            self.video.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
        ))
        self._render_result(processed.result)

    def _render_result(self, result: FrameResult) -> None:
        self.reps.value.setText(str(result.reps))
        self.rep_hero.setText(str(result.reps))
        self.joint_angle.value.setText(f"{result.angle:.0f}" if result.angle else "—")
        self.tempo.value.setText(f"{result.tempo_seconds:.1f}" if result.tempo_seconds else "—")
        self.range_bar.setValue(round(result.range_percent))
        self.score.setText(str(result.form_score) if result.form_score else "—")
        self.feedback.setText(result.feedback)
        self.status_pill.setText(result.stage)
        self.status_pill.setProperty("good", result.good_form)
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)

    def _reset(self) -> None:
        self.tracker.reset()
        self.set_paused = False
        self.set_button.setText("Pause set")
        if self.engine and self.engine.session:
            self.engine.session.reset()
        self._render_result(FrameResult(feedback="Set reset · take your starting position"))

    def _toggle_set(self) -> None:
        self.set_paused = not self.set_paused
        self.set_button.setText("Resume set" if self.set_paused else "Pause set")
        if self.set_paused:
            self.tracker.cancel_cycle()
            self._render_result(FrameResult(
                reps=self.tracker.reps, stage="SET PAUSED",
                tempo_seconds=self.tracker.last_tempo,
                feedback="Set paused · completed reps are protected",
            ))
        elif self.engine and self.engine.session:
            self.engine.session.reset(keep_reps=True)
            self._render_result(FrameResult(
                reps=self.tracker.reps, stage="CALIBRATING",
                tempo_seconds=self.tracker.last_tempo,
                feedback="Hold the starting pose to resume",
            ))

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop_camera()
        event.accept()


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("FormFlow Coach")
    app.setStyle("Fusion")
    app.setFont(QFont("Avenir Next", 10))
    app.setStyleSheet((ROOT / "formflow" / "style.qss").read_text())
    window = FormFlowWindow()
    window.show()
    return app.exec()
