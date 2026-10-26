from pathlib import Path
import PyInstaller.__main__
import platform
import plistlib
import subprocess


root = Path(__file__).resolve().parent
suffix = ".ico" if platform.system() == "Windows" else ".icns"
PyInstaller.__main__.run([
    str(root / "run.py"),
    "--name=FormFlow Coach",
    "--windowed",
    "--noconfirm",
    f"--icon={root / 'assets' / ('app-icon' + suffix)}",
    f"--add-data={root / 'assets'}{';' if platform.system() == 'Windows' else ':'}assets",
    f"--add-data={root / 'formflow' / 'style.qss'}{';' if platform.system() == 'Windows' else ':'}formflow",
    "--collect-all=mediapipe",
    "--osx-bundle-identifier=com.awaisdev.formflowcoach",
])

if platform.system() == "Darwin":
    app = root / "dist" / "FormFlow Coach.app"
    plist_path = app / "Contents" / "Info.plist"
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    plist.update({
        "CFBundleDisplayName": "FormFlow Coach",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1",
        "NSCameraUsageDescription": "FormFlow Coach uses the camera to analyze exercise posture locally on this Mac.",
        "NSHighResolutionCapable": True,
    })
    with plist_path.open("wb") as handle:
        plistlib.dump(plist, handle)
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
