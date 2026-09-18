"""Rail Corrugation subsystem — 3-class corrugation classifier.

Task (see docs/Info_kits/Rail_Corrugation/Rail_Corrugation_Info_Kit.md):
classify a 1-second, 10kHz axle-box vibration/shock recording as Normal,
Side I, or Side II corrugation. Positions 1/3/5/7 (across all 8 cars) are
Side I; positions 2/4/6/8 are Side II — the two sides are judged
independently from the same file, then combined into one 3-class label
(exactly one of Normal/Side I/Side II, never both sides faulted at once per
the info kit's Section 2.2).

Feature extraction (per side, aggregated across that side's 32 axle boxes
across all 8 cars — the same rail section passes under every car in the
1s window, so a real corrugation signature shows up consistently across
cars on the affected side):
- Vibration & shock RMS (mean/max/std across the side's channels) — plain
  amplitude features, but they turned out to separate the classes cleanly
  in the training data: Side I files' Side-I-channel vibration RMS runs
  ~1.9-2.7x a Normal file's, and likewise for Side II (~2.5-3.2x).
- Vibration spectral peakiness (peak/mean of the Welch PSD) and kurtosis
  (both vibration and shock) — frequency-domain / impulsiveness features,
  since corrugation is a resonance phenomenon (Section 1.1), not just raw
  amplitude.
- log-ratio of each side's RMS features against the other side's — the two
  sides share the same train speed and car-to-car mounting effects, so this
  isolates the side-specific anomaly from those confounds.
- One global feature: train speed, derived from the toothed-wheel pulse
  count (90 teeth, 0.85m wheel diameter) in "Rotating speed".

This gives 22 features total (8 per side + 5 side-ratio + speed) — kept
deliberately small given only 14 Side I examples in the 272-file training
set; an earlier attempt with ~145 features (every per-channel stat
individually) badly overfit the minority classes (macro F1 ~0.55-0.66
cross-validated) before being cut down to this curated set.

Model: GradientBoostingClassifier (shallow trees, depth=2), trained with
balanced sample weights to counter the 234/14/24 class imbalance — plain
unweighted training or a random-forest alternative scored consistently
lower in cross-validation. Only tabular tree-based models were considered,
per the task's own guidance and the modest, imbalanced sample size.

Validation: stratified 5-fold cross-validation (not random — preserves the
Side I/II proportions in every fold) across all 272 labelled Train files,
averaged over 5 different fold-assignment seeds to reduce variance from the
very small Side I count: mean macro F1 = 0.865 (std 0.024). Per-class F1 at
one representative seed: Normal 0.983, Side I 0.769, Side II 0.920 (macro
0.891) — Side I remains the weakest class, expected given only 14 training
examples, but far from the ~0 a "always predict Normal" baseline would
score on it.

The final shipped model (rail_corrugation_model.pkl, next to this file) is
refit on all 272 labelled files with the same balanced-sample-weight
scheme; the numbers above are from cross-validation held-out folds, not
this final in-sample fit.

Processing time: ~0.25-0.35s per file (CSV read + feature extraction), well
within interactive/demo latency.
"""

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import welch
from scipy.stats import kurtosis

META = {
    "label": "Rail Corrugation",
    "allowed_extensions": [".csv"],
    "input_hint": "1s axle-box vibration/shock recording (.csv), 64 axle boxes x vibration+shock",
}

OUTPUT_COLUMNS = ["file_id", "prediction"]

FS = 10000
NPERSEG = 2048
WHEEL_TEETH = 90
WHEEL_DIAMETER_M = 0.85

SIDE_I_POSITIONS = [1, 3, 5, 7]
SIDE_II_POSITIONS = [2, 4, 6, 8]
CARS = range(1, 9)

RATIO_BASE_FEATURES = ["vib_rms_mean", "vib_rms_max", "vib_rms_std", "shk_rms_mean", "shk_rms_max"]
SIDE_FEATURE_NAMES = [
    "vib_rms_mean",
    "vib_rms_max",
    "vib_rms_std",
    "shk_rms_mean",
    "shk_rms_max",
    "vib_peakiness_mean",
    "vib_kurtosis_mean",
    "shk_kurtosis_mean",
]
FEATURE_ORDER = (
    [f"side1_{f}" for f in SIDE_FEATURE_NAMES]
    + [f"side2_{f}" for f in SIDE_FEATURE_NAMES]
    + [f"ratio_{f}" for f in RATIO_BASE_FEATURES]
    + ["speed_mps"]
)

_MODEL_PATH = Path(__file__).with_name("rail_corrugation_model.pkl")
with open(_MODEL_PATH, "rb") as _f:
    _MODEL = pickle.load(_f)


def _side_columns(positions, signal_type):
    return [f"{signal_type} of bearing in position {pos} of car {car}" for car in CARS for pos in positions]


def _time_domain_stats(x):
    return float(np.sqrt(np.mean(x**2))), float(kurtosis(x))


def _vib_peakiness(x):
    freqs, psd = welch(x, fs=FS, nperseg=min(NPERSEG, len(x)))
    peak_idx = np.argmax(psd[1:]) + 1
    return float(psd[peak_idx] / (psd.mean() + 1e-12))


def _side_features(df, positions, prefix):
    vib_rms, vib_kurt, vib_peak = [], [], []
    for col in _side_columns(positions, "Vibration"):
        x = df[col].to_numpy()
        rms, kurt = _time_domain_stats(x)
        vib_rms.append(rms)
        vib_kurt.append(kurt)
        vib_peak.append(_vib_peakiness(x))

    shk_rms, shk_kurt = [], []
    for col in _side_columns(positions, "Shock"):
        x = df[col].to_numpy()
        rms, kurt = _time_domain_stats(x)
        shk_rms.append(rms)
        shk_kurt.append(kurt)

    vib_rms, vib_kurt, vib_peak = np.array(vib_rms), np.array(vib_kurt), np.array(vib_peak)
    shk_rms, shk_kurt = np.array(shk_rms), np.array(shk_kurt)

    return {
        f"{prefix}_vib_rms_mean": vib_rms.mean(),
        f"{prefix}_vib_rms_max": vib_rms.max(),
        f"{prefix}_vib_rms_std": vib_rms.std(),
        f"{prefix}_shk_rms_mean": shk_rms.mean(),
        f"{prefix}_shk_rms_max": shk_rms.max(),
        f"{prefix}_vib_peakiness_mean": vib_peak.mean(),
        f"{prefix}_vib_kurtosis_mean": vib_kurt.mean(),
        f"{prefix}_shk_kurtosis_mean": shk_kurt.mean(),
    }


def _speed_mps(df):
    pulses = df["Rotating speed"].to_numpy()
    transitions = np.sum(np.diff(pulses) != 0)
    revolutions_per_sec = (transitions / 2.0) / WHEEL_TEETH
    return float(revolutions_per_sec * np.pi * WHEEL_DIAMETER_M)


def _extract_feature_vector(df):
    side1 = _side_features(df, SIDE_I_POSITIONS, "side1")
    side2 = _side_features(df, SIDE_II_POSITIONS, "side2")
    feats = {**side1, **side2}
    for name in RATIO_BASE_FEATURES:
        feats[f"ratio_{name}"] = float(np.log((side1[f"side1_{name}"] + 1e-9) / (side2[f"side2_{name}"] + 1e-9)))
    feats["speed_mps"] = _speed_mps(df)
    return np.array([[feats[c] for c in FEATURE_ORDER]])


def predict(file_storage):
    df = pd.read_csv(file_storage)
    features = _extract_feature_vector(df)
    label = str(_MODEL.predict(features)[0])

    proba = dict(zip(_MODEL.classes_, _MODEL.predict_proba(features)[0]))
    severity = 1.0 - float(proba.get("Normal", 0.0))
    health_score = round(100 * (1 - severity))
    return {
        "health_score": health_score,
        "alert": health_score < 80,
        "results": [{"file_id": file_storage.filename, "prediction": label}],
    }
