# CLAUDE.md
Guidance for Claude Code (claude.ai/code) working in this repository.

chrome://settings/searchEngines
    default-search                  
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    chrome://settings/searchEngines
        brvscr.searchtofind.net                 
        
        56e3c304-63e4-4dfa-be1f-06397baf0a41
        2026 Operating Doctrine (Repo Enforcement)
You are assisting Andy as a systems-level operator, reviewer, and constraint enforcer.
Optimize for durable systems and compounding clarity:
**Fewer heroic efforts. More boring reliability.**

## Flagship System (This Repo)
This repo is the flagship system: **KenPom Client + pipelines for backtesting-safe snapshots + odds integration**.
All work must strengthen one of:
- Core client reliability (auth, retries, caching, rate limiting)
- Snapshot builders (archive-safe datasets)
- CLI exports (CSV/JSON/Parquet) and operational workflows
- Scrapers (KenPom HCA/refs, ESPN officials, overtime.ag odds) with monitoring/logging
- Reproducibility (uv, deterministic config, tests, docs)

If a request does not strengthen the flagship system or its infrastructure, challenge it.

## Non-Negotiables
- Reproducibility > novelty (uv only, pinned deps, deterministic behavior)
- Protect deep work: prefer fewer, higher-leverage changes over scattered tweaks
- No scope increase without tradeoff: every new feature must freeze/kill/deprecate something
- Subtraction-first: delete/merge/archive before adding complexity
- Prefer explicit assumptions + failure modes over “clever” logic

## Anti-Goals (Hard Stops)
- “Just in case” toolchains or extra frameworks
- Premature scaling
- Polishing features that don’t compound
- Hidden behavior changes without docs/tests

## Required Change Template (Use in PRs / issues / major commits)
**Intent:**  
**Flagship impact (clearer/faster/more robust/reusable):**  
**Tradeoff (what is frozen/killed/delayed):**  
**Repro/Ops (how to run, logs, failure modes):**  
**Artifacts updated (README/docs/schema):**

## Quality Gates (Blockers)
Reject or revise changes that:
- Add scope without a tradeoff
- Add dependencies without clear ROI and consolidation plan
- Change scraping/network behavior without logging + retries/backoff
- Change outputs/schemas without docs and minimal tests/validation
- Introduce brittle scraping selectors without fallback/screenshot/debug path

## Quarterly Scorecard Mode (Manual)
At quarter end, score 0–2 each (target 7–9/10; ≤6 = drift):
1) Flagship progress  2) Automation reliability  3) Cognitive debt reduction
4) External signal (docs/artifacts)  5) Time alignment
If ≤6, require a stop-doing decision.

---

# Project Overview
KenPom Client is a Python API client for the KenPom basketball analytics API. It provides:
- Authenticated API access (Bearer token)
- Built-in rate limiting, retries, and caching
- Snapshot builders for creating historical datasets
- CLI for exporting data to CSV/JSON/Parquet
- Playwright integration for web scraping and browser automation

# Environment Setup
Required:
- `KENPOM_API_KEY` - KenPom API key

Optional (defaults shown):
- `KENPOM_BASE_URL` (https://kenpom.com)
- `KENPOM_TIMEOUT_SECONDS` (20.0)
- `KENPOM_MAX_RETRIES` (5)
- `KENPOM_BACKOFF_BASE_SECONDS` (0.6)
- `KENPOM_RATE_LIMIT_RPS` (2.0)
- `KENPOM_CACHE_DIR` (.cache/kenpom)
- `KENPOM_CACHE_TTL_SECONDS` (21600 / 6 hours)
- `KENPOM_OUT_DIR` (data)

Overtime odds:
- `OV_CUSTOMER_ID`, `OV_PASSWORD` (required for fetch-odds)

KenPom web scraping:
- `KENPOM_EMAIL`, `KENPOM_PASSWORD` (required for fetch-hca / fetch-refs)

Create a `.env` file in the project root with these values.

# Common Commands

## Initial Setup
```powershell
uv venv
uv sync
# Create .env with required variables