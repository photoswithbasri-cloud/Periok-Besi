"""Subsystem registry.

Every subsystem module implements the same interface:

- `META` (dict): at minimum `label`, `allowed_extensions` (a set of lowercase
  file extensions including the dot, e.g. `{".csv"}`), and `input_hint`
  (a short human-readable description shown in the UI).
- `predict(file_storage) -> dict`: takes a Werkzeug `FileStorage` (the
  uploaded file) and returns
  `{"health_score": 0-100, "alert": bool, "results": [...]}`, where each row
  in `results` matches that subsystem's exact example-submission schema.

To add a 5th subsystem: write `backend/subsystems/<name>.py` implementing
this interface, then add one line to `REGISTRY` below. No other file needs
to change.
"""

from . import acv, door, rail_corrugation, shm

REGISTRY = {
    "door": door,
    "acv": acv,
    "rail_corrugation": rail_corrugation,
    "shm": shm,
}
