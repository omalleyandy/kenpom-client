# Projection Model Specification

Score/margin/total/winprob projections using KenPom efficiency ratings.

## Inputs

| Variable | Source | Description |
|----------|--------|-------------|
| `AdjOE_home` | ratings | Home team adjusted offensive efficiency |
| `AdjDE_home` | ratings | Home team adjusted defensive efficiency |
| `AdjTempo_home` | ratings | Home team adjusted tempo |
| `AdjOE_visitor` | ratings | Visitor adjusted offensive efficiency |
| `AdjDE_visitor` | ratings | Visitor adjusted defensive efficiency |
| `AdjTempo_visitor` | ratings | Visitor adjusted tempo |
| `home_adv` | calibrated | Home court advantage (points) |
| `k` | calibrated | Sigmoid scaling factor for win probability |

## Algorithm

```
1. COMPUTE possessions
   poss = (AdjTempo_home + AdjTempo_visitor) / 2

2. COMPUTE expected efficiencies
   E_home = (AdjOE_home + AdjDE_visitor) / 2
   E_visitor = (AdjOE_visitor + AdjDE_home) / 2

3. COMPUTE raw scores (neutral site)
   raw_home = poss * E_home / 100
   raw_visitor = poss * E_visitor / 100

4. APPLY home court adjustment (split evenly)
   proj_home = raw_home + (home_adv / 2)
   proj_visitor = raw_visitor - (home_adv / 2)

5. COMPUTE derived outputs
   proj_total = proj_home + proj_visitor
   proj_margin = proj_home - proj_visitor

6. COMPUTE win probability
   win_prob_home = 1 / (1 + exp(-proj_margin / k))
   win_prob_visitor = 1 - win_prob_home
```

## Outputs

| Field | Formula | Example |
|-------|---------|---------|
| `proj_home` | step 4 | 78.2 |
| `proj_visitor` | step 4 | 71.5 |
| `proj_total` | proj_home + proj_visitor | 149.7 |
| `proj_margin` | proj_home - proj_visitor | +6.7 |
| `win_prob_home` | sigmoid(margin/k) | 0.72 |
| `win_prob_visitor` | 1 - win_prob_home | 0.28 |
| `possessions` | step 1 | 68.5 |

## Calibration Knobs

### `home_adv` (Home Court Advantage)

| Method | Description |
|--------|-------------|
| **Default** | Use `3.5` (historical D1 average) |
| **Dynamic** | Use team-specific HCA from `hca_scraper.py` output |
| **Fitted** | Minimize MSE on historical margin residuals: `argmin_h Σ(actual_margin - pred_margin(h))²` |

Fitting procedure:
1. Collect N games with known outcomes
2. Grid search `home_adv ∈ [2.0, 5.0]` step 0.1
3. Select value minimizing mean squared error on margin

### `k` (Sigmoid Scaling Factor)

| Method | Description |
|--------|-------------|
| **Default** | Use `11.0` (empirical NCAA baseline) |
| **Fitted** | Maximize log-likelihood: `argmax_k Σ[y·log(p) + (1-y)·log(1-p)]` where `y=1` if home won |

Fitting procedure:
1. Collect N games with known outcomes (y ∈ {0,1})
2. Grid search `k ∈ [8.0, 15.0]` step 0.5
3. Select value maximizing log-likelihood (equivalently, minimizing Brier score)

Interpretation:
- Lower `k` → sharper probabilities (more confident)
- Higher `k` → softer probabilities (more conservative)
- At `k=11`, a 10-point favorite ≈ 71% win probability

## Anti-Leakage Rule

**Problem**: Using current ratings to predict past games leaks future information into the model.

**Rule**: For any game on date `D`, features must come from ratings snapshot dated `< D`.

| Use Case | Feature Source | Correct |
|----------|----------------|---------|
| Live predictions | `ratings` endpoint (today) | ✓ |
| Backtesting game on 2024-03-15 | `archive` endpoint with `d=2024-03-14` | ✓ |
| Backtesting game on 2024-03-15 | `ratings` endpoint (current) | ✗ LEAKAGE |

Implementation:
```python
# CORRECT: Use archive for backtesting
snapshot = client.archive(d="2024-03-14")  # day before game

# WRONG: Current ratings leak future games into past predictions
snapshot = client.ratings(y=2024)  # contains info from games after 03-15
```

**Preseason edge case**: For games before ratings stabilize (~2 weeks), use:
```python
snapshot = client.archive(preseason=True, y=2024)
```

**Validation**: Set `feature_source_home` and `feature_source_visitor` in output to the archive date used. Verify `feature_source < game_date` for all backtest rows.
