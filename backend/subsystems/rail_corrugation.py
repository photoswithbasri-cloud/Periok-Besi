"""Rail Corrugation subsystem — PLACEHOLDER ONLY, not the real model.

Real task (see docs/Info_kits/Rail_Corrugation/Rail_Corrugation_Info_Kit.md):
classify a 1-second axle-box vibration/shock recording as Normal, Side I, or
Side II corrugation. Positions 1/3/5/7 (across all 8 cars) are Side I;
positions 2/4/6/8 are Side II.

Placeholder approach used here: compare the RMS vibration energy of Side I
columns against Side II columns; whichever side is well above the file's own
side-to-side baseline is flagged, else Normal. This is exactly the kind of
raw-amplitude threshold the info kit says is unreliable on its own
(Section 1.2) — it exists only to exercise the pipeline end to end.
"""

import re

import pandas as pd

META = {
    "label": "Rail Corrugation",
    "allowed_extensions": [".csv"],
    "input_hint": "1s axle-box vibration/shock recording (.csv), 64 axle boxes x vibration+shock",
}

OUTPUT_COLUMNS = ["file_id", "prediction"]

SIDE_I_POSITIONS = {1, 3, 5, 7}
SIDE_II_POSITIONS = {2, 4, 6, 8}
POSITION_RE = re.compile(r"position (\d+) of car")
SIDE_RATIO_THRESHOLD = 1.15


def _side_rms(df, positions):
    columns = [
        col
        for col in df.columns
        if col.startswith("Vibration of bearing")
        and (match := POSITION_RE.search(col))
        and int(match.group(1)) in positions
    ]
    if not columns:
        return 0.0
    values = df[columns].to_numpy()
    return float((values**2).mean() ** 0.5)


def predict(file_storage):
    df = pd.read_csv(file_storage)

    side1_rms = _side_rms(df, SIDE_I_POSITIONS)
    side2_rms = _side_rms(df, SIDE_II_POSITIONS)
    baseline = (side1_rms + side2_rms) / 2 or 1.0

    ratio1 = side1_rms / baseline
    ratio2 = side2_rms / baseline

    if ratio1 > SIDE_RATIO_THRESHOLD and ratio1 >= ratio2:
        label = "Side I"
        severity = min(ratio1 - 1.0, 1.0)
    elif ratio2 > SIDE_RATIO_THRESHOLD:
        label = "Side II"
        severity = min(ratio2 - 1.0, 1.0)
    else:
        label = "Normal"
        severity = 0.0

    health_score = round(100 * (1 - severity))
    return {
        "health_score": health_score,
        "alert": health_score < 80,
        "results": [{"file_id": file_storage.filename, "prediction": label}],
    }
