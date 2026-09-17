# Rail Fleet Health Monitor — NEBULA X 2026

AI/ML-powered fault detection and health scoring for train subsystems,
built for NEBULA X (LTA Singapore, 18-20 Sep 2026), Problem Statement 3:
"A living railway whispers secrets about our trains" — predictive fault
detection using AI/ML across train subsystem signals.

## Team
- [Basri] — [Troller]
- [Sufi] — [Code]
- [Bing Liang] — [Code]

## Subsystems covered
- Door
- ACV
- Rail Corrugation
- SHM (Structural Health Monitoring)

Each subsystem has its own Info Kit and reference submission schema
(see `/docs`) but shares one unified interface — see "Architecture" below.

## Status
🚧 Pre-event build. Real competition dataset drops on Day 1 (18 Sep);
until then this runs on synthetic/placeholder data matching each
subsystem's reference schema.

## Architecture
- One shared contract every subsystem plugs into: upload → health score
  (0-100) → alert if <80% → results table matching that subsystem's
  reference schema.
- `backend/subsystems/<name>.py` — one self-contained module per subsystem
- `backend/` — API routing to the right subsystem module
- `frontend/` — single UI, one tab/card per subsystem
- `docs/` — Info Kits + reference submission schemas (not committed if
  under NDA — check competition rules)
- `data/` — example/demo CSVs

## Setup
```bash
git clone <this-repo-url>
cd rail-fleet-health
# setup instructions TBD once backend/frontend scaffolded
```

## Swapping in the real dataset (Day 1)
See `backend/subsystems/` — each module's data-loading step is the only
thing that needs to change once the real dataset is released.
