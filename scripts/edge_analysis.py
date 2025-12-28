"""Edge analysis comparing KenPom projections to ESPN lines."""

from dataclasses import dataclass


@dataclass
class GameEdge:
    """Edge calculation for a single game."""

    away_team: str
    home_team: str
    espn_spread: float  # From home team perspective (negative = home fav)
    kenpom_margin: float  # From home team perspective (positive = home fav)
    espn_total: float
    kenpom_total: float
    spread_edge: float  # Positive = underdog value
    total_edge: float  # Positive = over value
    play: str  # Recommended play


def analyze_edges():
    """Analyze today's games for betting edges."""
    # ESPN lines (spread from favorite perspective, converted to home spread)
    # KenPom margin is always from home team perspective
    games = [
        # (away, home, espn_home_spread, kenpom_margin, espn_total, kenpom_total)
        ("Winthrop", "Texas Tech", -17.5, 14.0, 165.5, 179.8),
        ("UL Monroe", "Kansas St.", -33.5, 28.5, 169.5, 184.0),
        ("Columbia", "North Florida", 13.5, -11.6, 161.5, 175.7),  # Columbia road fav
        ("Le Moyne", "Boston College", -13.5, 12.6, 146.5, 160.5),
        ("Harvard", "Colgate", -2.5, 4.0, 140.5, 156.2),
        ("Liberty", "FIU", 4.5, -3.3, 145.5, 167.2),  # Liberty road fav
        ("Florida A&M", "Georgia Tech", -18.5, 17.3, 147.5, 162.9),
        ("Norfolk St.", "Louisiana", -1.5, -1.7, 128.5, 143.1),  # KenPom has Norfolk!
        ("N. Colorado", "Colorado", -14.5, 11.9, 158.5, 175.6),
        ("CSU Fullerton", "SMU", -20.5, 19.0, 174.5, 187.0),
        ("Old Dominion", "Maryland", -13.5, 11.1, 152.5, 166.9),
        ("Washington St.", "Portland", 4.5, -2.5, 150.5, 169.4),  # WSU road fav
        ("Penn", "George Mason", -15.5, 15.0, 147.5, 165.3),
        ("Santa Clara", "Oregon St.", 5.5, -4.7, 152.5, 164.7),  # SCU road fav
        ("Pacific", "San Diego", 2.5, -4.0, 146.5, 163.1),  # PAC road fav
        ("Charleston So.", "Richmond", -13.5, 13.2, 154.5, 169.6),
        ("Gonzaga", "Pepperdine", 28.5, -24.3, 152.5, 164.4),  # Gonz road fav
        ("San Francisco", "Seattle", -1.5, 1.4, 142.5, 156.7),
        ("Saint Mary's", "LMU", 8.5, -7.0, 138.5, 149.6),  # SMC road fav
        ("Omaha", "Oregon", -19.5, 15.4, 152.5, 168.5),
    ]

    edges = []
    for away, home, espn_spread, kp_margin, espn_total, kp_total in games:
        # Spread edge calculation:
        # ESPN spread < 0 means home favored, KenPom margin > 0 means home favored
        # Edge = |ESPN spread| - |KenPom margin| when both favor same team
        # Positive edge = underdog getting more points than KenPom suggests
        if (espn_spread < 0 and kp_margin > 0) or (espn_spread > 0 and kp_margin < 0):
            # Same team favored by both - calculate raw difference
            spread_edge = abs(espn_spread) - abs(kp_margin)
        else:
            # Different teams favored - major discrepancy
            spread_edge = abs(espn_spread) + abs(kp_margin)
            if espn_spread > 0:  # ESPN has away favored, KenPom has home
                spread_edge = -spread_edge  # Negative = away team value

        # Total edge: KenPom total - ESPN total
        # Positive = KenPom expects more points (over value)
        total_edge = kp_total - espn_total

        # Determine play
        plays = []
        if abs(spread_edge) >= 3.0:
            if spread_edge > 0:
                # Underdog is getting more points than KenPom suggests
                if espn_spread < 0:
                    plays.append(f"{away} +{abs(espn_spread)}")  # Away dog
                else:
                    plays.append(f"{home} +{espn_spread}")  # Home dog
            else:
                # Favorite value (spread too small)
                if espn_spread < 0:
                    plays.append(f"{home} {espn_spread}")  # Home fav
                else:
                    plays.append(f"{away} -{espn_spread}")  # Away fav

        if abs(total_edge) >= 8.0:
            if total_edge > 0:
                plays.append(f"OVER {espn_total}")
            else:
                plays.append(f"UNDER {espn_total}")

        edges.append(
            GameEdge(
                away_team=away,
                home_team=home,
                espn_spread=espn_spread,
                kenpom_margin=kp_margin,
                espn_total=espn_total,
                kenpom_total=kp_total,
                spread_edge=spread_edge,
                total_edge=total_edge,
                play=", ".join(plays) if plays else "PASS",
            )
        )

    return edges


def print_analysis(edges: list[GameEdge]):
    """Print formatted edge analysis."""
    print("=" * 80)
    print("EDGE ANALYSIS: KenPom vs ESPN Lines - December 28, 2025")
    print("=" * 80)
    print()

    # Spread plays (sorted by edge magnitude)
    spread_plays = sorted(edges, key=lambda x: abs(x.spread_edge), reverse=True)

    print("SPREAD EDGE ANALYSIS (sorted by edge size)")
    print("-" * 80)
    print(
        f"{'Matchup':<35} {'ESPN':>8} {'KenPom':>8} {'Edge':>8} {'Play':<20}"
    )
    print("-" * 80)

    for g in spread_plays:
        matchup = f"{g.away_team} @ {g.home_team}"
        espn = f"{g.espn_spread:+.1f}"
        kp = f"{g.kenpom_margin:+.1f}"
        edge = f"{g.spread_edge:+.1f}"

        # Highlight significant edges
        marker = "***" if abs(g.spread_edge) >= 3.0 else "   "

        print(f"{marker} {matchup:<32} {espn:>8} {kp:>8} {edge:>8}")

    print()
    print("TOTAL EDGE ANALYSIS (sorted by edge size)")
    print("-" * 80)
    print(
        f"{'Matchup':<35} {'ESPN':>8} {'KenPom':>8} {'Edge':>8} {'Play':<20}"
    )
    print("-" * 80)

    total_plays = sorted(edges, key=lambda x: abs(x.total_edge), reverse=True)
    for g in total_plays:
        matchup = f"{g.away_team} @ {g.home_team}"
        espn = f"{g.espn_total:.1f}"
        kp = f"{g.kenpom_total:.1f}"
        edge = f"{g.total_edge:+.1f}"

        marker = "***" if abs(g.total_edge) >= 8.0 else "   "

        print(f"{marker} {matchup:<32} {espn:>8} {kp:>8} {edge:>8}")

    print()
    print("=" * 80)
    print("RECOMMENDED PLAYS (Edge >= 3.0 spread, >= 8.0 total)")
    print("=" * 80)

    plays = [g for g in edges if g.play != "PASS"]
    if plays:
        for g in sorted(plays, key=lambda x: abs(x.spread_edge), reverse=True):
            print(f"\n{g.away_team} @ {g.home_team}")
            print(f"  ESPN Line: {g.espn_spread:+.1f}")
            print(f"  KenPom Proj: {g.kenpom_margin:+.1f}")
            print(f"  Spread Edge: {g.spread_edge:+.1f}")
            if abs(g.total_edge) >= 8.0:
                print(f"  Total Edge: {g.total_edge:+.1f}")
            print(f"  >>> PLAY: {g.play}")
    else:
        print("No plays meeting threshold criteria.")

    print()
    print("=" * 80)
    print("LEGEND:")
    print("  Edge > 0: Underdog getting more points than KenPom suggests (dog value)")
    print("  Edge < 0: Favorite getting fewer points than KenPom suggests (fav value)")
    print("  *** = Significant edge (>= 3.0 spread or >= 8.0 total)")
    print("=" * 80)


if __name__ == "__main__":
    edges = analyze_edges()
    print_analysis(edges)
