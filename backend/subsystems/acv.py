"""ACV subsystem — PLACEHOLDER ONLY, not the real model.

Real task (see docs/Info_kits/ACV/ACV_Subsystem_Info_Kit.md): identify which
of the 8 cars has a refrigerant leak and rank every car most- to
least-likely faulty.

Placeholder approach used here: parse car identifiers from the file's own
`Car <NN> - <parameter>` column headers (per the info kit, the exact
parameter set varies between files, so nothing is hardcoded), then rank cars
by the total variability (std) of their own numeric telemetry — a cheap
proxy for "this car's readings look unusually erratic", not a real
diagnostic signal.
"""

import re

import pandas as pd

META = {
    "label": "ACV",
    "allowed_extensions": [".xlsx"],
    "input_hint": "Per-car ACV telemetry across all 8 cars (.xlsx), sampled every 30s",
}

OUTPUT_COLUMNS = ["file_id", "ranked_cars"]

CAR_COLUMN_RE = re.compile(r"^Car (\d+) - ")


def _car_ids(columns):
    ids = set()
    for col in columns:
        match = CAR_COLUMN_RE.match(col)
        if match:
            ids.add(match.group(1))
    return sorted(ids)


def predict(file_storage):
    df = pd.read_excel(file_storage)
    car_ids = _car_ids(df.columns)

    scores = {}
    for car_id in car_ids:
        car_columns = [c for c in df.columns if c.startswith(f"Car {car_id} - ")]
        numeric = df[car_columns].select_dtypes(include="number")
        scores[car_id] = float(numeric.std().sum()) if not numeric.empty else 0.0

    ranked = sorted(car_ids, key=lambda c: scores[c], reverse=True)

    total_score = sum(scores.values()) or 1.0
    top_score = scores[ranked[0]] if ranked else 0.0
    severity = min(top_score / total_score, 1.0)

    health_score = round(100 * (1 - severity))
    return {
        "health_score": health_score,
        "alert": health_score < 80,
        "results": [
            {
                "file_id": file_storage.filename,
                "ranked_cars": "|".join(ranked),
            }
        ],
    }
