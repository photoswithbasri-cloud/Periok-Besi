"""SHM subsystem — PLACEHOLDER ONLY, not the real model.

Real task (see docs/Info_kits/SHM/SHM_Info_Kit.md): predict a single
cumulative fatigue-damage value (Miner's rule + rainflow counting produced
the reference labels, though that method isn't required).

Placeholder approach used here: scale the signal's RMS by a fixed constant
into a 0-1 range. This has no relationship to the real Miner's-rule damage
value (checked against `data/SHM/Train_Labels.csv` — RMS does not correlate
with the disclosed `damage` labels) — it exists only to exercise the
pipeline end to end with a plausibly-shaped number.
"""

import pandas as pd

META = {
    "label": "SHM",
    "allowed_extensions": [".csv"],
    "input_hint": "Dynamic stress time series, single column, no header (.csv)",
}

OUTPUT_COLUMNS = ["file_id", "prediction"]

RMS_SCALE = 20.0


def predict(file_storage):
    series = pd.read_csv(file_storage, header=None).iloc[:, 0]

    rms = float((series**2).mean() ** 0.5)
    damage = max(0.0, min(1.0, rms / RMS_SCALE))

    health_score = round(100 * (1 - damage))
    return {
        "health_score": health_score,
        "alert": health_score < 80,
        "results": [{"file_id": file_storage.filename, "prediction": round(damage, 6)}],
    }
