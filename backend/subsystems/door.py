"""Door subsystem — PLACEHOLDER ONLY, not the real model.

Real task (see docs/Info_kits/Door/Door_Subsystem_Info_Kit.md): find each
door-open/close cycle in a continuous stream and classify it Normal vs.
Abnormal resistance.

Placeholder approach used here:
- Segmentation: the info kit explicitly warns against assuming the
  opening/closing flag columns are a reliable boundary signal — and indeed
  `Door is opening`/`Door is closing` turn out to be perfect complements
  (one is always 1), so their OR is true for 100% of every file and yields
  a single giant "segment". Instead, this uses the stream's own timing: rows
  are sampled on a steady ~20ms cadence while a cycle is running, and the
  info kit notes cycles are separated by "irregular gaps" — confirmed on
  `data/Door/Test.csv` (6215/6252 gaps are exactly 20ms; the other 37 range
  from ~200ms to 55s). A gap much larger than the normal cadence marks the
  boundary between one cycle and the next.
- Classification: a segment is flagged Abnormal if its mean motor current is
  a high z-score outlier versus the file's overall mean — the same kind of
  naive fixed-threshold approach the info kit says is insufficient in real
  deployment (Section 1.2).

Both steps exist only to exercise the pipeline end to end with a
realistically-shaped, multi-row result, not to actually solve the task.
"""

from datetime import datetime

import pandas as pd

META = {
    "label": "Door",
    "allowed_extensions": [".csv"],
    "input_hint": "Continuous door-controller stream (.csv) — motor current/voltage/back-EMF + position",
}

OUTPUT_COLUMNS = ["start_time", "end_time", "prediction"]

CURRENT_COLUMN = "Motor current(mA)"
DATETIME_COLUMN = "Datetime"
GAP_THRESHOLD_MS = 200  # normal sample cadence is ~20ms; anything well beyond that is a cycle boundary
ABNORMAL_Z_THRESHOLD = 1.0


def _parse_datetime(value):
    year, month, day, hour, minute, second, millisecond = (int(p) for p in str(value).split("-"))
    return datetime(year, month, day, hour, minute, second, millisecond * 1000)


def _segment_bounds(timestamps):
    segments = []
    start = 0
    for i in range(1, len(timestamps)):
        gap_ms = (timestamps[i] - timestamps[i - 1]).total_seconds() * 1000
        if gap_ms > GAP_THRESHOLD_MS:
            segments.append((start, i - 1))
            start = i
    segments.append((start, len(timestamps) - 1))
    return segments


def predict(file_storage):
    df = pd.read_csv(file_storage)
    timestamps = df[DATETIME_COLUMN].map(_parse_datetime).tolist()
    segment_bounds = _segment_bounds(timestamps)

    mean_current = df[CURRENT_COLUMN].mean()
    std_current = df[CURRENT_COLUMN].std() or 1.0

    results = []
    abnormal_count = 0
    for start, end in segment_bounds:
        segment = df.iloc[start : end + 1]
        z_score = (segment[CURRENT_COLUMN].mean() - mean_current) / std_current
        label = "Abnormal resistance" if z_score > ABNORMAL_Z_THRESHOLD else "Normal"
        if label == "Abnormal resistance":
            abnormal_count += 1
        results.append(
            {
                "start_time": segment[DATETIME_COLUMN].iloc[0],
                "end_time": segment[DATETIME_COLUMN].iloc[-1],
                "prediction": label,
            }
        )

    abnormal_fraction = abnormal_count / len(results)
    health_score = round(100 * (1 - abnormal_fraction))
    return {
        "health_score": health_score,
        "alert": health_score < 80,
        "results": results,
    }
