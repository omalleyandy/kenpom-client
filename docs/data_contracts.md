# Data Contracts — Odds & Projection Pipeline (NCAAB)

Authoritative data contracts for the **overtime.ag → KenPom → edge analysis** pipeline.

This document exists to **prevent silent drift**.  
If data breaks, this is the first place to check.

---

## Scope

These contracts govern the following artifacts:

- Market odds ingested from **overtime.ag**
- Model projections derived from **KenPom**
- Downstream **edge / EV / sizing** outputs

All files are **date-stamped**, **immutable**, and treated as factual records.

---

## Contract Versioning

- **Current version:** v1
- Schema changes require:
  - Explicit version bump (v2, v3…)
  - Migration note in this file
  - Update to dependent scripts

No implicit schema changes allowed.

---

## File Inventory