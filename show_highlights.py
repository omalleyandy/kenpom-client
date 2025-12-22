"""Show highlights from today's game predictions."""

import pandas as pd

df = pd.read_csv("data/todays_game_predictions_2025-12-21.csv")

print("=" * 80)
print("GAME HIGHLIGHTS - December 21, 2025")
print("=" * 80)

print("\n=== CLOSEST GAMES (Margin < 5 points) ===\n")
close = df[abs(df["predicted_margin"]) < 5].sort_values("predicted_margin")
for _, g in close.iterrows():
    favorite = g["home_team"] if g["predicted_margin"] > 0 else g["away_team"]
    margin = abs(g["predicted_margin"])
    win_prob = max(g["home_win_prob"], g["away_win_prob"])
    print(f"{g['away_team']:25} @ {g['home_team']:25}")
    print(f"  Favorite: {favorite} by {margin:.1f} | Win Prob: {win_prob:.1%}")
    print()

print("\n=== BIGGEST ROAD FAVORITES (Away team favored by 5+) ===\n")
upsets = df[df["predicted_margin"] < -5].sort_values("predicted_margin")
for _, g in upsets.head(5).iterrows():
    print(f"{g['away_team']:25} @ {g['home_team']:25}")
    print(
        f"  {g['away_team']} by {abs(g['predicted_margin']):.1f} | "
        f"Win Prob: {g['away_win_prob']:.1%}"
    )
    print()

print("\n=== TOP RANKED MATCHUPS (Both teams AdjEM > 15) ===\n")
top_matchups = df[(df["away_adj_em"] > 15) & (df["home_adj_em"] > 15)].sort_values(
    "predicted_margin", key=abs, ascending=False
)
for _, g in top_matchups.iterrows():
    favorite = g["home_team"] if g["predicted_margin"] > 0 else g["away_team"]
    print(f"{g['away_team']:25} @ {g['home_team']:25}")
    print(f"  Away: {g['away_adj_em']:.1f} AdjEM | Home: {g['home_adj_em']:.1f} AdjEM")
    print(
        f"  {favorite} by {abs(g['predicted_margin']):.1f} | "
        f"Win Prob: {max(g['home_win_prob'], g['away_win_prob']):.1%}"
    )
    print()

print("\n=== HIGHEST VARIANCE GAMES (Most Unpredictable) ===\n")
volatile = df.nlargest(5, "avg_sigma")
for _, g in volatile.iterrows():
    print(f"{g['away_team']:25} @ {g['home_team']:25}")
    print(f"  Sigma: {g['avg_sigma']:.2f} | Margin: {abs(g['predicted_margin']):.1f}")
    print()
