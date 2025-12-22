# Interpreting Game Predictions and Finding Analytical Edge

## Overview

This guide explains how to interpret the enriched KenPom game predictions CSV and identify analytical edge for sports betting, DFS, and predictive modeling.

## CSV Column Reference

### Team Information
- **away_team** / **home_team**: Team names (matched to KenPom database)

### Team Efficiency Metrics (KenPom Core Stats)
- **away_adj_em** / **home_adj_em**: Adjusted Efficiency Margin
  - Points per 100 possessions better than average team
  - Example: Duke 25.5 = 25.5 points better than average per 100 possessions
  - **Elite**: 20+, **Good**: 10-20, **Average**: 0-10, **Below Average**: negative

- **away_adj_oe** / **home_adj_oe**: Adjusted Offensive Efficiency
  - Points scored per 100 possessions (tempo-adjusted)
  - **Elite**: 115+, **Good**: 110-115, **Average**: 105-110, **Poor**: <105

- **away_adj_de** / **home_adj_de**: Adjusted Defensive Efficiency
  - Points allowed per 100 possessions (tempo-adjusted)
  - **Elite**: <95, **Good**: 95-100, **Average**: 100-105, **Poor**: 105+
  - **Lower is better** for defense

### Game Variance Metrics
- **away_sigma** / **home_sigma**: Team-specific scoring margin standard deviation
  - Measures game-to-game variance in performance
  - **Typical range**: 10.0 - 12.0
  - **Low variance** (9.5-10.5): Consistent, predictable team
  - **High variance** (11.5-13.0): Volatile, boom-or-bust team
  - **Factors**: High tempo teams and 3PT-heavy teams have higher sigma

- **avg_sigma**: Average of both teams' sigma values
  - Used for win probability calculation
  - Higher avg_sigma = more unpredictable game outcome

### Predictions
- **predicted_margin**: Expected point differential (home team perspective)
  - **Positive**: Home team favored (e.g., +9.7 = home by 9.7)
  - **Negative**: Away team favored (e.g., -5.2 = away by 5.2)
  - **Formula**: Home AdjEM - Away AdjEM + 3.5 (home court advantage)

- **home_win_prob** / **away_win_prob**: Win probability percentages
  - Calculated using normal distribution with predicted_margin and avg_sigma
  - **Formula**: P(win) = Normal_CDF(predicted_margin / avg_sigma)
  - Sum to 1.0 (100%)

- **confidence**: Model confidence in prediction
  - **High**: Win probability > 80% or < 20% (strong favorite)
  - **Medium**: Win probability 65-80% or 20-35% (moderate favorite)
  - **Low**: Win probability 35-65% (toss-up game)

## What is "Analytical Edge"?

**Analytical edge** (also called "value") is the difference between your model's assessment of probability and the implied probability from market odds.

### Finding Edge: The Process

1. **Get your model's prediction** (from CSV):
   - Example: Gonzaga home vs Oregon
   - Model: Gonzaga -9.7 points, 76.4% win probability

2. **Get market odds** (from sportsbooks):
   - Example: Sportsbook line Gonzaga -12.0
   - Implied probability: ~54.5% to cover -12

3. **Calculate edge**:
   - **Point spread edge**: Model -9.7 vs Market -12.0 = +2.3 points of value on Oregon
   - **Win probability edge**: Model 76.4% vs Implied ~92% = Market overvalues Gonzaga

4. **Identify betting opportunity**:
   - If model says Gonzaga -9.7 but market is -12, **bet Oregon +12** (getting 2.3 extra points)
   - If model says 76.4% win probability but market implies 92%, **bet Oregon moneyline** (value)

### Edge Thresholds

- **2+ points of spread edge**: Strong betting opportunity
- **1-2 points of spread edge**: Moderate betting opportunity
- **0-1 points**: Marginal, consider other factors
- **5%+ win probability edge**: Significant value
- **3-5% win probability edge**: Moderate value

## Practical Applications

### 1. Point Spread Betting

**Step-by-step example using today's games:**

```
Game: Oregon @ Gonzaga
Model Prediction: Gonzaga -9.7 (76.4% win probability)
Market Line: Gonzaga -12.0 (-110)

Analysis:
- Model gives Gonzaga 9.7 point edge
- Market requires Gonzaga to win by 12+
- Edge: 2.3 points in favor of Oregon
- Action: Bet Oregon +12 ✓

Confidence Check:
- avg_sigma = 10.8 (typical variance)
- 68% of outcomes fall within ±10.8 of predicted margin
- If Gonzaga -9.7, 68% chance actual margin is between +1.1 and -20.5
- Market line of -12 is within expected range but on high side
```

### 2. Moneyline Betting

**When to use moneyline vs spread:**

```
Game: Close matchup with predicted_margin < 3
Example: Vanderbilt @ Wake Forest
Model: Wake Forest -1.6 (55.4% win probability)
Market Moneyline: Wake Forest -150 (60% implied), Vanderbilt +130 (43.5% implied)

Analysis:
- Model says Wake Forest 55.4% to win
- Market implies 60% to win
- Edge: 4.6% in favor of Vanderbilt
- Odds: +130 pays $130 on $100 bet
- Expected Value: 0.554 * (-100) + 0.446 * 130 = +2.6% EV on Vanderbilt ML
- Action: Bet Vanderbilt moneyline +130 ✓
```

### 3. Cover Probability Calculations

Use sigma to calculate probability of covering specific spreads:

```python
# Formula: P(cover spread S) = Normal_CDF((predicted_margin - S) / avg_sigma)

Example: Gonzaga -12.0 spread
predicted_margin = 9.7
avg_sigma = 10.8
spread = -12.0

z_score = (9.7 - 12.0) / 10.8 = -0.213
P(cover -12) = Normal_CDF(-0.213) = 41.6%

Interpretation:
- Model gives Gonzaga only 41.6% chance to cover -12
- But market implies 52.4% (from -110 odds)
- Edge: 10.8% in favor of Oregon +12
- This is a STRONG betting opportunity
```

### 4. Totals (Over/Under) Betting

Calculate expected total points using offensive/defensive efficiency:

```python
# Formula (approximate):
# Expected total = (Home AdjOE + Away AdjDE + Away AdjOE + Home AdjDE) / 2 + tempo_adjustment

Example: Oregon @ Gonzaga
Home AdjOE: 120.5 (Gonzaga offense)
Home AdjDE: 98.2 (Gonzaga defense)
Away AdjOE: 112.3 (Oregon offense)
Away AdjDE: 103.5 (Oregon defense)

Expected total ≈ (120.5 + 103.5 + 112.3 + 98.2) / 2 = 217.3 points

Market Total: 150.5

Analysis:
- Model expects ~217 combined points
- If both teams play at faster tempo, could exceed total
- Check tempo stats from enriched data for validation
- Potential Over play if tempos align
```

### 5. DFS (Daily Fantasy Sports)

**Using enriched data for DFS lineup construction:**

```
High-Value Targets:
1. Games with high predicted totals (lots of fantasy points)
2. Teams with high AdjOE facing poor AdjDE (mismatch)
3. High tempo games (more possessions = more stats)

Example from today's slate:
Game: Southern @ Baylor
Baylor AdjOE: 115.2, Southern AdjDE: 90.5 (huge mismatch)
Predicted margin: Baylor -25+
Strategy: Stack Baylor players (high scoring expected)

Contrarian Plays:
1. Low-ownership high-variance teams (high sigma)
2. Close games (predicted_margin < 5) = competitive = more minutes
3. Road underdogs with good AdjOE (lower ownership, high ceiling)
```

### 6. Sharp vs Square Indicators

**Identifying sharp betting opportunities:**

```
Sharp Indicators:
✓ Model differs from public perception by 2+ points
✓ Low-profile teams with strong underlying metrics (AdjEM)
✓ Road teams with better AdjEM than market suggests
✓ Unders in low-tempo matchups (public loves overs)

Square Indicators (avoid):
✗ Big-name schools getting too much credit
✗ Recent performance bias (team won big last game)
✗ Emotional betting (rivalry games, tournament rematches)
✗ Media narratives not supported by efficiency metrics

Example: Pittsburgh @ Penn State
If media hypes Penn State but model shows Pittsburgh +2 edge:
- This is likely sharp value on Pittsburgh
- Public overvalues name recognition
```

## Advanced Analysis: Four Factors

The enriched CSV includes four_factors data. Use this for prop betting and deeper analysis:

### Offensive Four Factors
- **efg_pct**: Effective Field Goal % (accounts for 3PT being worth more)
  - Use for player points props (high eFG% = efficient scoring)
- **to_pct**: Turnover %
  - Use for assists props (low TO% = better ball movement)
- **or_pct**: Offensive Rebound %
  - Use for rebounds props (high OR% = second chance points)
- **ft_rate**: Free Throw Rate (FTA per FGA)
  - Use for points props (high FT Rate = more scoring opportunities)

### Defensive Four Factors
- **defg_pct**: Opponent Effective FG%
  - Lower = better defense against scoring
- **dto_pct**: Opponent Turnover %
  - Higher = forces more turnovers (steals props)
- **dor_pct**: Opponent Offensive Rebound %
  - Lower = limits second chances
- **dft_rate**: Opponent Free Throw Rate
  - Lower = doesn't foul (impacts pace and scoring)

### Point Distribution
- **off_ft / off_fg2 / off_fg3**: % of points from each source
  - Use for player props (3PT-heavy teams = shooters get more attempts)
- **def_ft / def_fg2 / def_fg3**: % of opponent points allowed
  - Use for player props (teams weak against 3PT = target opposing shooters)

## Real Examples from Today's Slate

### Example 1: Identifying Value

```
Game: UConn @ DePaul
Model: UConn -18.5
Hypothetical Market: UConn -22.0

Analysis:
- 3.5 points of edge on DePaul
- UConn likely overvalued due to name recognition
- Action: Bet DePaul +22 (strong value)
```

### Example 2: Avoiding Bad Bets

```
Game: Gardner-Webb @ Tennessee
Model: Tennessee -27.5
Hypothetical Market: Tennessee -26.0

Analysis:
- Model says Tennessee should win by MORE than market suggests
- No value on either side
- Action: Pass (or small Tennessee if forced to bet)
```

### Example 3: Totals Edge

```
Game: Oregon @ Gonzaga
Model Expected Total: ~158 (based on AdjOE/AdjDE)
Hypothetical Market: 152.5

Analysis:
- Model expects 5.5 more points than market
- Both teams have high AdjOE
- Action: Bet Over 152.5 (value play)
```

## Closing Line Value (CLV)

**Most important metric for long-term success:**

- Opening lines are often less sharp than closing lines
- If you bet early and closing line moves in your direction = positive CLV
- Track your CLV over time, not win percentage
- Positive CLV = beating the market = long-term profit

```
Example:
You bet: Oregon +12 (model edge of 2.3 points)
Closing line: Oregon +10.5

CLV = +12 - (+10.5) = +1.5 points
This is EXCELLENT - you got 1.5 points better than closing

Even if Oregon loses by 11 (bet loses), you made the right decision
Over hundreds of bets with positive CLV, you will profit
```

## Key Takeaways

1. **Edge is everything**: Only bet when model shows 2+ points of edge or 5%+ probability edge
2. **Sigma matters**: Higher variance games are less predictable (require more edge to bet)
3. **Use cover probability**: Calculate exact probability of covering spread with Normal_CDF
4. **Track CLV**: Measure success by closing line value, not wins/losses
5. **Shop lines**: Different sportsbooks offer different lines - find the best edge
6. **Combine factors**: Use AdjEM for spreads, four_factors for props, sigma for risk assessment
7. **Avoid public bias**: Big-name teams often overvalued, look for efficiency-based edge
8. **Bet volume wisely**: Only bet games with clear edge, not every game on slate

## Tools and Formulas

### Calculate cover probability in Python:
```python
import math

def normal_cdf(x):
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

def cover_probability(predicted_margin, spread, avg_sigma):
    """Calculate probability of covering the spread."""
    z_score = (predicted_margin - spread) / avg_sigma
    return normal_cdf(z_score)

# Example
prob = cover_probability(predicted_margin=9.7, spread=12.0, avg_sigma=10.8)
print(f"Cover probability: {prob:.1%}")  # 41.6%
```

### Expected Value (EV) calculation:
```python
def expected_value(win_probability, american_odds):
    """Calculate expected value of a bet."""
    if american_odds > 0:
        decimal_odds = 1 + (american_odds / 100)
    else:
        decimal_odds = 1 + (100 / abs(american_odds))

    ev = (win_probability * (decimal_odds - 1)) - (1 - win_probability)
    return ev

# Example
ev = expected_value(win_probability=0.554, american_odds=130)
print(f"Expected Value: {ev:.1%}")  # +2.6%
```

## Next Steps

1. **Export today's predictions**: Already done - `data/todays_game_predictions_2025-12-21.csv`
2. **Get market lines**: Visit sportsbook websites to collect current lines
3. **Calculate edge**: Compare model predictions to market for each game
4. **Identify opportunities**: Filter for 2+ points edge or 5%+ probability edge
5. **Place bets**: Bet only games with clear value
6. **Track results**: Log bets with CLV, not just wins/losses
7. **Iterate**: Update model with new data, refine sigma calculations, improve predictions

## Warnings

- **Bankroll management**: Never bet more than 1-3% of bankroll on single game
- **Line shopping**: Always get the best available line (can add 1-2% to EV)
- **Injury updates**: Model doesn't know about late scratches - check lineups before betting
- **Bias awareness**: Don't bet your favorite teams - let the model decide
- **Overconfidence**: Even 5-point edges lose ~30-40% of the time - variance is real
- **Data freshness**: KenPom updates daily - always use latest snapshot for predictions
