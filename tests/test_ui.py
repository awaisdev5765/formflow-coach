from pathlib import Path

from PySide6.QtWidgets import QApplication

from formflow.app import FormFlowWindow, ROOT


def app_instance():
    return QApplication.instance() or QApplication([])


def test_ui_loads_assets_and_all_exercises():
    app_instance()
    window = FormFlowWindow(auto_start_camera=False)
    try:
        assert window.windowTitle() == "FormFlow Coach"
        assert window.exercise.count() == 4
        assert (ROOT / "assets" / "app-icon.png").exists()
        assert (ROOT / "formflow" / "style.qss").exists()
        assert window.camera_stack.currentIndex() == 0
    finally:
        window.close()


def test_exercise_switch_and_reset_update_state():
    app_instance()
    window = FormFlowWindow(auto_start_camera=False)
    try:
        window.exercise.setCurrentIndex(1)
        assert window.tracker.profile.key == "pushup"
        window.tracker.reps = 3
        window._reset()
        assert window.tracker.reps == 0
        assert window.reps.value.text() == "0"
        assert "reset" in window.feedback.text().lower()
    finally:
        window.close()


def test_native_icon_files_exist():
    assets = Path(ROOT) / "assets"
    for name in ("app-icon.png", "app-icon.ico", "app-icon.icns"):
        assert (assets / name).stat().st_size > 0


def test_camera_permission_view_is_clear_and_retryable():
    app_instance()
    window = FormFlowWindow(auto_start_camera=False)
    try:
        assert window.camera_stack.currentIndex() == 0
        assert "camera" in window.permission_action.text().lower()
        assert "camera" in window.camera_button.accessibleName().lower()
    finally:
        window.close()
