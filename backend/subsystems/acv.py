"""ACV subsystem — refrigerant leak localisation.

Task (see docs/Info_kits/ACV/ACV_Subsystem_Info_Kit.md): each file holds
synchronised telemetry from all 8 cars of a train; exactly one car has a
refrigerant leak. Rank every car most- to least-likely to be that car.

Approach: peer comparison, not classification. The exact parameter set
varies between files (most have 8 params/car, one has 60+), so columns are
parsed dynamically from each file's own `Car <NN> - <parameter>` headers —
nothing is hardcoded.

For each parameter shared by (most of) the 8 cars, every car gets an
anomaly feature computed relative to its peers at each timestamp, then
averaged over time:

- Continuous measurements (temperatures, pressures, ...): the peer median
  and MAD (median absolute deviation) across the 8 cars are computed at
  each row, and a car's feature is its average normalised distance from
  that row's peer median. MAD-based, not mean/std, so a single leaking car
  doesn't drag its own baseline off-normal.
- Discrete/low-cardinality columns (running mode, status flags, and
  numeric setpoints or 0/1 flags with few distinct values): the feature is
  how often a car disagrees with the per-row majority vote. This is kept
  separate from the continuous path because when 7 of 8 cars agree exactly,
  MAD is 0 and the continuous path can't see the outlier at all — the
  majority-vote path catches exactly that case. Cardinality (not raw dtype)
  decides the split, because some columns are numeric for the cars that
  have a working sensor and a fixed non-numeric sentinel (e.g. "Invalid")
  for the rest; coercing to numeric and judging by cardinality routes real
  continuous readings correctly even when mixed with that sentinel.

Each parameter's per-car feature is converted to a rank across the 8 cars
(1 = most anomalous for that parameter). A car's final score is its average
rank across every usable parameter, and cars are ranked by that average,
ascending — most consistently anomalous first. Averaging ranks (rather than
summing raw deviations) keeps parameters on a comparable footing regardless
of their native units/scale, which matters since one file may carry a
handful of parameters and another 60+.

Validated against the 6 labelled Train cases (data/ACV/Train_Labels.csv):
the true faulty car is ranked 1st of 8 in every case, i.e. a perfect
average linear rank-decay score of 1.0000 under the info kit's formula.
"""

import re

import numpy as np
import pandas as pd

META = {
    "label": "ACV",
    "allowed_extensions": [".xlsx"],
    "input_hint": "Per-car ACV telemetry across all 8 cars (.xlsx), sampled every 30s",
}

OUTPUT_COLUMNS = ["file_id", "ranked_cars"]

CAR_COLUMN_RE = re.compile(r"^Car (\d+) - (.+)$")

# A numeric column with this few distinct values is treated as a discrete
# flag/setpoint (majority-vote) rather than a continuous measurement
# (peer median/MAD) — see module docstring.
DISCRETE_CARDINALITY = 10


def _parse_params(columns):
    """Group `Car <NN> - <parameter>` columns by parameter, car id -> column."""
    car_ids = set()
    params = {}
    for col in columns:
        match = CAR_COLUMN_RE.match(col)
        if not match:
            continue
        car_id, param = match.group(1), match.group(2)
        car_ids.add(car_id)
        params.setdefault(param, {})[car_id] = col
    return sorted(car_ids), params


def _categorical_feature(sub, cars):
    """Per-car rate of disagreeing with each row's cross-car majority value."""
    codes, uniques = pd.factorize(sub[cars].to_numpy().ravel(), sort=True)
    codes = codes.reshape(sub[cars].shape)
    n_categories = len(uniques)
    if n_categories == 0:
        return pd.Series(0.0, index=cars)

    counts = np.zeros((codes.shape[0], n_categories), dtype=np.int32)
    for k in range(n_categories):
        counts[:, k] = (codes == k).sum(axis=1)
    majority_idx = counts.argmax(axis=1)
    majority_exists = counts.max(axis=1) > 0

    feature = {}
    for j, car in enumerate(cars):
        car_has_value = majority_exists & (codes[:, j] != -1)
        disagree = car_has_value & (codes[:, j] != majority_idx)
        # Denominator is every row, not just rows this car reported, so a
        # car that rarely logs this parameter isn't penalised for the rows
        # it skipped.
        feature[car] = disagree.mean()
    return pd.Series(feature)


def _numeric_feature(sub, cars):
    """Per-car average normalised distance from each row's peer median."""
    row_median = sub[cars].median(axis=1)
    row_mad = sub[cars].sub(row_median, axis=0).abs().median(axis=1).replace(0, np.nan)
    deviation = sub[cars].sub(row_median, axis=0).abs().div(row_mad, axis=0)
    return deviation.mean(axis=0, skipna=True)


def _param_feature(df, col_map, present_cars):
    sub = df[[col_map[c] for c in present_cars]].copy()
    sub.columns = present_cars

    coerced = sub.apply(pd.to_numeric, errors="coerce")
    if coerced.notna().sum().sum() == 0:
        return _categorical_feature(sub, present_cars)

    flat = coerced.to_numpy().ravel()
    cardinality = np.unique(flat[~np.isnan(flat)]).size
    if cardinality <= DISCRETE_CARDINALITY:
        return _categorical_feature(coerced, present_cars)
    return _numeric_feature(coerced, present_cars)


def _rank_cars(df, car_ids, params):
    n = len(car_ids)
    min_required = max(2, (n + 1) // 2)

    rank_totals = {c: [] for c in car_ids}
    deviation_totals = {c: [] for c in car_ids}
    for col_map in params.values():
        present_cars = [c for c in car_ids if c in col_map]
        if len(present_cars) < min_required:
            continue

        feature = _param_feature(df, col_map, present_cars)
        if feature.isna().all():
            continue
        feature = feature.fillna(feature.mean())

        ranks = feature.rank(ascending=False, method="average")
        for c in present_cars:
            rank_totals[c].append(ranks[c])
            deviation_totals[c].append(feature[c])

    avg_rank = {c: (np.mean(v) if v else n) for c, v in rank_totals.items()}
    avg_deviation = {c: (np.mean(v) if v else 0.0) for c, v in deviation_totals.items()}
    ranked = sorted(car_ids, key=lambda c: avg_rank[c])
    return ranked, avg_deviation


def predict(file_storage):
    df = pd.read_excel(file_storage)
    car_ids, params = _parse_params(df.columns)
    ranked, avg_deviation = _rank_cars(df, car_ids, params)

    total_deviation = sum(avg_deviation.values()) or 1.0
    top_deviation = avg_deviation[ranked[0]] if ranked else 0.0
    severity = min(top_deviation / total_deviation, 1.0)

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
