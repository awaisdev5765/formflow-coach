# FormFlow Coach

FormFlow Coach is a privacy-first desktop exercise coach built with Python, MediaPipe, OpenCV, and PySide6. It tracks body landmarks locally, counts repetitions, measures joint angles and range of motion, estimates rep tempo, and gives real-time technique cues.

![FormFlow Coach desktop interface](docs/app-screenshot.png)

## Highlights

- Live pose skeleton and joint tracking
- Squat, push-up, lunge, and bicep-curl profiles
- Rep counting with movement-stage detection
- Athlete continuity lock so passers-by cannot inherit an active set
- Stable starting-pose calibration before counting begins
- Visible workout zone, landmark-confidence checks, and automatic pause on tracking loss
- Full `UP → DOWN → UP` validation with impossible-speed rejection
- Non-blocking camera and pose-model startup
- Joint angle, range-of-motion, tempo, and form-score calculations
- Clear live coaching cues with a full-body setup guide
- Keyboard controls: `Space` starts/stops the camera and `Ctrl+R` resets the session
- No account, uploads, analytics, or cloud processing
- Native packaging for Windows and macOS

> FormFlow is a fitness feedback tool, not a medical device. Stop exercising if you feel pain and consult a qualified professional when needed.

## Run from source

Python 3.10 or 3.11 is recommended for the broadest MediaPipe compatibility.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python run.py
```

Allow camera access when macOS or Windows asks. Place your full body inside the marked zone, preferably from the side, and hold the starting pose while FormFlow calibrates. Counting starts only after the athlete lock is established. Leaving the frame pauses the set and requires recalibration without changing completed reps.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Build a desktop application

PyInstaller builds for the operating system on which it runs; build once on macOS and once on Windows.

```bash
python build.py
```

The packaged app is written to `dist/` and uses the included native app icon.

## How repetition detection works

Each exercise profile defines a primary three-point joint angle and top/bottom thresholds. FormFlow moves through `UP` and `DOWN` stages only after those thresholds are crossed, which prevents a held pose from adding repetitions. A secondary alignment angle contributes to the form score for exercises where trunk position matters.

## Privacy

Video frames stay in memory and are processed on the device. FormFlow does not record video or send camera data over the network.

## License

MIT
