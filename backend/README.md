# Backend contract

This is the interface every subsystem module plugs into. The UI and routing
never change when a subsystem's internal logic changes — only its module
file does.

## Adding a subsystem

1. Create `backend/subsystems/<name>.py` implementing:
   - `META` (dict): `label` (display name), `allowed_extensions` (list of
     lowercase extensions with the dot, e.g. `[".csv"]`), `input_hint`
     (short description shown in the UI).
   - `OUTPUT_COLUMNS` (list of str): the exact column order/names of that
     subsystem's reference submission schema (see
     `docs/example_submissions/`).
   - `predict(file_storage) -> dict`: takes the uploaded file (a Werkzeug
     `FileStorage`) and returns:
     ```json
     {
       "health_score": 0-100,
       "alert": true | false,
       "results": [ { ...one row per OUTPUT_COLUMNS... }, ... ]
     }
     ```
     `alert` is `true` whenever `health_score < 80`.
2. Register it in `backend/subsystems/__init__.py`'s `REGISTRY` dict —
   nothing else needs to change. The frontend fetches `/api/subsystems` on
   load and builds tabs from whatever is registered.

## Routing

- `GET /api/subsystems` — metadata for every registered subsystem (label,
  accepted file extension(s), input hint, output columns). Drives the
  frontend's tabs and results table without any per-subsystem frontend code.
- `POST /api/predict/<subsystem>` — single generic endpoint for every
  subsystem, `multipart/form-data` with the file under the `file` field.
  Looks up `<subsystem>` in `REGISTRY` and delegates to that module's
  `predict()`. Returns 404 for an unknown subsystem, 400 for a missing file
  or wrong extension, 500 with the error message if `predict()` raises.

## Current status: placeholders, not real models

Every module in `backend/subsystems/` right now implements a cheap,
deterministic heuristic on the real input schema (documented at the top of
each file) — enough to prove the schema and pipeline end to end, not enough
to be a real fault/anomaly detector. Each file's docstring explains exactly
what placeholder logic it uses and why it isn't the real approach. Swapping
in a trained model later means rewriting that module's `predict()` body —
the `META`/`OUTPUT_COLUMNS`/return-shape contract above does not change.
