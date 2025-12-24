# Daily Slate API

Output contract for daily game prediction tables.

## Schema Reference

| Schema | Path | Description |
|--------|------|-------------|
| Row | `schemas/daily_slate_row.json` | Single game prediction |
| Table | `schemas/daily_slate_table.json` | Array of predictions |

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `date` | date | Game date (YYYY-MM-DD) |
| `season` | int | Season year (e.g., 2025) |
| `game_id` | string | Unique game identifier |
| `home` / `visitor` | string | Team names |
| `proj_home` / `proj_visitor` | number | Projected scores |
| `proj_total` | number | Projected total points |
| `proj_margin_home_minus_visitor` | number | Spread (positive = home favored) |
| `win_prob_home` / `win_prob_visitor` | number | Win probability [0,1] |
| `possessions` | number | Projected possessions |
| `method` | enum | `fanmatch`, `kenpom_model`, or `archive_backtest` |
| `feature_source_home` / `feature_source_visitor` | string | Snapshot file/cache key |
| `warnings` | array | Empty if clean; contains issue strings |

## Optional Trace Fields (fanmatch_*)

Include when `method=fanmatch` for debugging and audit trails:

| Field | Description |
|-------|-------------|
| `fanmatch_raw_margin` | Original API margin (HomePred - VisitorPred) |
| `fanmatch_raw_total` | Original API total (HomePred + VisitorPred) |
| `fanmatch_hca_applied` | HCA value used in projection |
| `fanmatch_tempo_home` | Home team PredTempo from fanmatch |
| `fanmatch_tempo_visitor` | Visitor team tempo (derived from ratings) |
| `fanmatch_home_rank` | Home team KenPom rank |
| `fanmatch_visitor_rank` | Visitor team KenPom rank |
| `fanmatch_thrill_score` | Thrill score indicating game watchability |

### When to Include Trace Fields

Include `fanmatch_*` fields when:
1. `method=fanmatch` (using fanmatch API as primary source)
2. Debugging projection discrepancies between our model and KenPom
3. Auditing historical predictions for model validation
4. Comparing raw API values against recomputed projections

Omit trace fields when:
1. `method=kenpom_model` or `method=archive_backtest` (no fanmatch data)
2. Minimizing payload size for production exports
3. Consumer only needs final projections, not audit trail

---

## Join Plan: Fanmatch → TeamID Mapping

### Data Flow

```
fanmatch(d) ──┐
              ├──→ normalize_name() ──→ lookup(Teams) ──→ TeamID
teams(y)   ──┘

For each game in fanmatch:
  1. Extract Home/Visitor names
  2. Derive season from game date
  3. Lookup TeamID from teams(season)
  4. On mismatch: apply normalization → fuzzy match → fallback
```

### Join Plan Object

```json
{
  "join_plan": {
    "name": "fanmatch_to_team_id",
    "version": "1.0",
    "steps": [
      {
        "step": 1,
        "action": "fetch_fanmatch",
        "inputs": { "d": "YYYY-MM-DD" },
        "outputs": ["games[]"],
        "cache_key": "fanmatch:{d}"
      },
      {
        "step": 2,
        "action": "derive_season",
        "inputs": { "date": "from step 1" },
        "outputs": ["season"],
        "logic": "if month >= 11: year + 1 else: year"
      },
      {
        "step": 3,
        "action": "fetch_teams",
        "inputs": { "y": "season from step 2" },
        "outputs": ["teams[]", "name_to_id_map"],
        "cache_key": "teams:{y}"
      },
      {
        "step": 4,
        "action": "build_lookup",
        "inputs": { "teams": "from step 3" },
        "outputs": ["exact_map", "normalized_map", "alias_map"],
        "logic": "Create 3-tier lookup: exact → normalized → alias"
      },
      {
        "step": 5,
        "action": "join_games",
        "inputs": {
          "games": "from step 1",
          "lookup_maps": "from step 4"
        },
        "outputs": ["enriched_games[]"],
        "logic": "For each game, resolve Home→TeamID and Visitor→TeamID"
      }
    ],
    "mismatch_strategy": {
      "tier_1_exact": "Direct match on TeamName",
      "tier_2_normalize": "Strip punctuation, lowercase, collapse whitespace",
      "tier_3_alias": "Known mappings (e.g., 'UConn' → 'Connecticut')",
      "tier_4_fuzzy": "Levenshtein distance ≤ 2 with warning",
      "tier_5_fallback": "Set TeamID=null, add warning 'team_not_found:{name}'"
    },
    "caching": {
      "fanmatch": { "key": "fanmatch:{d}", "ttl": 3600 },
      "teams": { "key": "teams:{y}", "ttl": 86400 }
    }
  }
}
```

### Normalization Rules

| Rule | Example Input | Normalized Output |
|------|---------------|-------------------|
| Strip punctuation | `St. Mary's (CA)` | `st marys ca` |
| Lowercase | `North Carolina` | `north carolina` |
| Collapse whitespace | `Miami  (FL)` | `miami fl` |
| Remove articles | `The Citadel` | `citadel` |

### Known Aliases

| Fanmatch Name | KenPom TeamName |
|---------------|-----------------|
| `UConn` | `Connecticut` |
| `UNC` | `North Carolina` |
| `USC` | `Southern California` |
| `SMU` | `Southern Methodist` |
| `UNLV` | `Nevada Las Vegas` |
| `UCF` | `Central Florida` |
| `VCU` | `Virginia Commonwealth` |
| `BYU` | `Brigham Young` |
| `LSU` | `Louisiana St.` |
| `Ole Miss` | `Mississippi` |

### Fallback Behavior

When a team name cannot be resolved:

1. **Log warning**: Add to `warnings[]`: `"team_not_found:{original_name}"`
2. **Set null**: `TeamID = null` for that team
3. **Partial row**: Include game with available projections but missing enrichment
4. **Downstream handling**: Consumers check `warnings` before using TeamID-dependent features

---

## Explanation (10 lines max)

1. **Row schema** defines 16 required fields covering game identity, projections, and data lineage.
2. **Table schema** is an array of rows with unique game entries.
3. **Trace fields** (`fanmatch_*`) provide audit trail for debugging; include when `method=fanmatch`.
4. **Join flow**: `fanmatch(d)` → derive `season` → `teams(y)` → build lookup → resolve names.
5. **Season derivation**: November+ belongs to next year's season (Nov 2024 → Season 2025).
6. **3-tier lookup**: exact match → normalized match → alias match before fuzzy/fallback.
7. **Normalization**: lowercase, strip punctuation, remove articles, collapse whitespace.
8. **Aliases**: Map common abbreviations (UConn, LSU, etc.) to canonical KenPom names.
9. **Fallback**: Unresolved names get `TeamID=null` plus warning; row still emitted.
10. **Caching**: `teams` cached 24h (stable), `fanmatch` cached 1h (game-day updates).
