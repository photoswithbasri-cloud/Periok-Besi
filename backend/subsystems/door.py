"""Door subsystem — segment-then-classify pipeline.

Task (see docs/Info_kits/Door/Door_Subsystem_Info_Kit.md): given a continuous,
unlabelled sensor stream, find every door-open/close cycle within it, then
classify each cycle as Normal or Abnormal resistance. Scored on IoU-weighted
F1 (Section 4), which rewards getting segment *boundaries* right, not just
the label.

Segmentation: the info kit warns against assuming the opening/closing flag
columns mark cycle boundaries (they don't — one is always 1, giving a single
giant blob for the whole file). Instead this uses the stream's own timing:
rows are sampled on a steady ~20ms cadence while a cycle is running, with
irregular gaps between cycles. A gap much larger than the normal cadence
marks a boundary. Validated directly against
`data/Door/Train_Segments_Answer.csv`: with a 200ms threshold this finds
exactly the true 110/110 segments in `Train.csv`, every one an exact
boundary match (IoU = 1.0). On `Test.csv`, gaps are either exactly 20ms
(6215/6252) or several seconds to tens of seconds — nothing in the
ambiguous middle — so 200ms sits with a comfortable margin on both sides.

Classification: per-segment features (motor current min/mean, motor
voltage mean, and open-vs-close direction inferred from door position) feed
a logistic regression. Motor current turns out to be a very clean signal
for this dataset: an Abnormal-resistance Close segment's current never dips
near zero (sustained resistance keeps the motor working throughout),
whereas every Normal Close segment's current bottoms out at exactly 0; for
Open segments the mean current is what separates the classes, with a clear
gap between the highest Normal (666) and the lowest Abnormal (738) segment
in the training data. A logistic regression on
[current_min, current_mean, voltage_mean, is_open] fit on all 110 labelled
Train segments gets 100% leave-one-out cross-validated accuracy — the
classes are cleanly separable on this data, not a knife-edge fit — so its
coefficients are baked in below rather than depending on scikit-learn at
runtime.

End-to-end validation (segmentation + classification together, not just
classification accuracy): holding out the last 25 of the 110 Train segments
as a genuine contiguous chunk (re-segmenting that raw slice from scratch and
classifying with a model fit only on the earlier segments) gives an
IoU-weighted F1 of 1.0000 on that held-out chunk, using the exact matching
formula from Section 4.1/4.2.
"""

import numpy as np
import pandas as pd

META = {
    "label": "Door",
    "allowed_extensions": [".csv"],
    "input_hint": "Continuous door-controller stream (.csv) — motor current/voltage/back-EMF + position",
}

OUTPUT_COLUMNS = ["start_time", "end_time", "prediction"]

DATETIME_COLUMN = "Datetime"
CURRENT_COLUMN = "Motor current(mA)"
VOLTAGE_COLUMN = "Motor Voltage(10mV)"
POSITION_COLUMN = "Door leaf position"

# Normal sample cadence is ~20ms; real cycle boundaries are several seconds
# or more (see module docstring) — 200ms sits with a large margin on both
# sides, validated against Train_Segments_Answer.csv.
GAP_THRESHOLD_MS = 200

# Logistic regression fit on all 110 labelled Train segments (StandardScaler
# + LogisticRegression), features = [current_min, current_mean, voltage_mean,
# is_open]. 100% leave-one-out cross-validated accuracy on that data.
FEATURE_MEAN = np.array([1.53363636e01, 5.87223697e02, 4.96963644e03, 5.00000000e-01])
FEATURE_SCALE = np.array([3.23315993e01, 1.39121416e02, 7.32703937e02, 5.00000000e-01])
LOGREG_COEF = np.array([2.04160357, 2.83392094, 0.3197992, -1.37544175])
LOGREG_INTERCEPT = -1.75583224


def _parse_datetime_series(raw):
    """Vectorized parse of the dataset's non-zero-padded Y-M-D-H-M-S-ms format."""
    parts = raw.str.split("-", expand=True).astype(int)
    parts.columns = ["year", "month", "day", "hour", "minute", "second", "ms"]
    base = pd.to_datetime(parts[["year", "month", "day", "hour", "minute", "second"]])
    return base + pd.to_timedelta(parts["ms"], unit="ms")


def _segment_bounds(timestamps):
    ts = timestamps.to_numpy()
    if len(ts) < 2:
        return [(0, len(ts) - 1)] if len(ts) else []
    gap_ms = np.diff(ts).astype("timedelta64[ms]").astype(float)
    boundaries = np.where(gap_ms > GAP_THRESHOLD_MS)[0]
    starts = np.concatenate(([0], boundaries + 1))
    ends = np.concatenate((boundaries, [len(ts) - 1]))
    return list(zip(starts.tolist(), ends.tolist()))


def _segment_features(segment_df):
    current = segment_df[CURRENT_COLUMN]
    voltage = segment_df[VOLTAGE_COLUMN]
    position = segment_df[POSITION_COLUMN]
    is_open = float(position.iloc[-1] > position.iloc[0])
    return np.array([current.min(), current.mean(), voltage.mean(), is_open])


def _classify(features):
    scaled = (features - FEATURE_MEAN) / FEATURE_SCALE
    logit = float(np.dot(scaled, LOGREG_COEF) + LOGREG_INTERCEPT)
    return "Abnormal resistance" if logit > 0 else "Normal"


def predict(file_storage):
    df = pd.read_csv(file_storage)
    timestamps = _parse_datetime_series(df[DATETIME_COLUMN])
    bounds = _segment_bounds(timestamps)

    results = []
    abnormal_count = 0
    for start, end in bounds:
        segment = df.iloc[start : end + 1]
        label = _classify(_segment_features(segment))
        if label == "Abnormal resistance":
            abnormal_count += 1
        results.append(
            {
                "start_time": segment[DATETIME_COLUMN].iloc[0],
                "end_time": segment[DATETIME_COLUMN].iloc[-1],
                "prediction": label,
            }
        )

    abnormal_fraction = abnormal_count / len(results) if results else 0.0
    health_score = round(100 * (1 - abnormal_fraction))
    return {
        "health_score": health_score,
        "alert": health_score < 80,
        "results": results,
    }
