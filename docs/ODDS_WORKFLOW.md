# Overtime.ag Odds Fetching & Edge Analysis Workflow (NCAAB)

Authoritative operator runbook for automating **NCAAB odds ingestion** from overtime.ag, integrating **KenPom projections**, and producing **backtesting-safe edge analysis**.

This workflow prioritizes **boring reliability**, explicit assumptions, and deterministic outputs.

---

## Overview

Daily automated flow:

1. Fetch NCAAB odds from **overtime.ag** (boards typically populate ~**4:00 AM PT**)
2. Build or fetch a **KenPom snapshot** (archive-safe when required)
3. Generate **same-day projections**
4. (Optional) Calculate **edge, EV, and Kelly-based sizing**

**Success metric**  
> Date-stamped odds + projections produced reliably, with logs and clear failure modes.

---

## Operating Principles

- Reproducibility > novelty  
- Date-stamped outputs only  
- No silent failures (logs or screenshots required)  
- Explicit data contracts between steps  
- Backtesting correctness matters (archive endpoints preferred)

---

## Prerequisites

### Credentials (`.env`)
```bash
OV_CUSTOMER_ID=...
OV_PASSWORD=...
KENPOM_API_KEY=...

# Optional (KenPom web scraping)
KENPOM_EMAIL=...
KENPOM_PASSWORD=...