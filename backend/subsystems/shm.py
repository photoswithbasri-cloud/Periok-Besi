"""SHM subsystem — cumulative fatigue-damage regression.

Task (see docs/Info_kits/SHM/SHM_Info_Kit.md): predict a single cumulative
fatigue-damage value for a dynamic-stress time series. The reference labels
were produced with rainflow counting + Miner's linear damage rule (Section
1.3), so rather than generic statistical features this reproduces that same
physical calculation directly:

    D = sum_i( n_i / N_i ),  N_i = C / sigma_a_i^m

`rainflow.extract_cycles` does the counting (range, mean, count per cycle;
half-cycles count as 0.5). Each cycle's amplitude is range/2, so summing
`n_i * amplitude_i^m` gives D up to the unknown material constant C, i.e.
D = raw_sum / C.

The exponent m and the constant C aren't given, so both were fit against
`data/SHM/Train_Labels.csv` (64 files): raw_sum was computed for m across
3.5-10, and m=5.0 gave a near-perfect linear correlation with the true
damage (0.9997, clearly the best of the range tried) — strong evidence the
labels were actually generated with an S-N slope of m=5. C then comes from
a single least-squares fit (through the origin, since raw_sum=0 must give
D=0) of `damage = raw_sum / C` across all 64 files.

Leave-one-out cross-validation across the 64 training files (refitting C
each fold) gives a MAPE of 2.62%, i.e. a MAPE-derived score (Section 4:
max(0, 1 - MAPE)) of 0.974 — matching the in-sample fit (0.974), so this
single-feature physical model isn't overfitting the small training set.
"""

import numpy as np
import pandas as pd
import rainflow

META = {
    "label": "SHM",
    "allowed_extensions": [".csv"],
    "input_hint": "Dynamic stress time series, single column, no header (.csv)",
}

OUTPUT_COLUMNS = ["file_id", "prediction"]

# S-N curve exponent, fit against Train_Labels.csv (see module docstring).
SN_EXPONENT = 5.0

# Miner's-rule scale constant (1/C), least-squares fit through the origin
# against all 64 training files at SN_EXPONENT=5.0.
DAMAGE_SCALE = 1.3677492441408104e-09


def _rainflow_damage_sum(series):
    total = 0.0
    for rng, _mean, count, _i_start, _i_end in rainflow.extract_cycles(series):
        amplitude = rng / 2.0
        total += count * amplitude**SN_EXPONENT
    return total


def predict(file_storage):
    series = pd.read_csv(file_storage, header=None).iloc[:, 0].to_numpy(dtype=float)

    raw_damage_sum = _rainflow_damage_sum(series)
    damage = float(DAMAGE_SCALE * raw_damage_sum)

    health_score = round(100 * (1 - min(damage, 1.0)))
    return {
        "health_score": health_score,
        "alert": health_score < 80,
        "results": [{"file_id": file_storage.filename, "prediction": round(damage, 6)}],
    }
