from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from .client import KenPomClient
from .config import Settings
from .slate import fanmatch_slate_table, join_with_odds, validate_backtest
from .snapshot import build_snapshot_from_archive, build_snapshot_from_ratings

log = logging.getLogger(__name__)

# =============================================================================
# Output File Naming Convention
# =============================================================================
# All output files follow the pattern:
#   kenpom_{data_type}_{identifiers}.{ext}
#
# Examples:
#   kenpom_teams_2025.csv              - Team rosters for 2025 season
#   kenpom_conferences_2025.csv        - Conference list for 2025 season
#   kenpom_ratings_2025_2024-12-21.csv - Ratings snapshot for 2025 season
#   kenpom_archive_2024-12-21.csv      - Historical archive for specific date
#   kenpom_predictions_2024-12-21.csv  - Game predictions for specific date
#   kenpom_fourfactors_2025.csv        - Four Factors data for 2025 season
#   kenpom_pointdist_2025.csv          - Point distribution for 2025 season
#   kenpom_height_2025.csv             - Height/experience for 2025 season
#   kenpom_miscstats_2025.csv          - Misc stats for 2025 season
#
# This makes files:
#   - Easy to identify as KenPom data
#   - Sortable by data type
#   - Clear about what parameters were used
# =============================================================================


def _write_outputs(df: pd.DataFrame, out_base: Path) -> None:
    """Write DataFrame to CSV, JSON, and Parquet formats.

    Args:
        df: DataFrame to write.
        out_base: Base path without extension (e.g., data/kenpom_teams_2025).
    """
    out_base.parent.mkdir(parents=True, exist_ok=True)

    csv_path = out_base.with_suffix(".csv")
    json_path = out_base.with_suffix(".json")
    parquet_path = out_base.with_suffix(".parquet")

    df.to_csv(csv_path, index=False)
    df.to_json(json_path, orient="records", indent=2)
    df.to_parquet(parquet_path, index=False)

    print(f"Wrote {len(df)} rows:")
    print(f"  -> {csv_path}")
    print(f"  -> {json_path}")
    print(f"  -> {parquet_path}")


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s"
    )

    parser = argparse.ArgumentParser(prog="kenpom")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # Team and conference data
    p_teams = sub.add_parser("teams", help="Fetch teams list for a season")
    p_teams.add_argument("--y", type=int, required=True, help="Season year")

    p_conf = sub.add_parser("conferences", help="Fetch conferences list for a season")
    p_conf.add_argument("--y", type=int, required=True, help="Season year")

    # Ratings and snapshots
    p_ratings = sub.add_parser("ratings", help="Fetch ratings for a season and write snapshot")
    p_ratings.add_argument("--y", type=int, required=True, help="Season year")
    p_ratings.add_argument("--date", type=str, required=True, help="Label date (YYYY-MM-DD)")
    p_ratings.add_argument(
        "--four-factors",
        action="store_true",
        help="Include four factors metrics (eFG%%, TO%%, OR%%, FT Rate)",
    )
    p_ratings.add_argument(
        "--point-dist",
        action="store_true",
        help="Include point distribution metrics (FT/2PT/3PT breakdown)",
    )
    p_ratings.add_argument(
        "--sigma",
        action="store_true",
        help="Calculate sigma (scoring margin std dev) for win probability",
    )

    p_archive = sub.add_parser("archive", help="Fetch archived ratings for a specific date")
    p_archive.add_argument("--date", type=str, required=True, help="YYYY-MM-DD")
    p_archive.add_argument(
        "--four-factors",
        action="store_true",
        help="Include four factors metrics (season-wide data)",
    )
    p_archive.add_argument(
        "--point-dist",
        action="store_true",
        help="Include point distribution metrics (season-wide data)",
    )
    p_archive.add_argument(
        "--sigma",
        action="store_true",
        help="Calculate sigma (scoring margin std dev) for win probability",
    )

    # Game predictions
    p_fan = sub.add_parser("fanmatch", help="Fetch KenPom game predictions for a date")
    p_fan.add_argument("--date", type=str, required=True, help="YYYY-MM-DD")

    # Slate table (projections with optional odds join)
    p_slate = sub.add_parser(
        "slate", help="Build projection slate table with model scores and optional odds"
    )
    p_slate.add_argument("--date", type=str, required=True, help="YYYY-MM-DD")
    p_slate.add_argument(
        "--backtest",
        action="store_true",
        help="Use archive features (time-correct for backtesting)",
    )
    p_slate.add_argument(
        "--join-odds",
        action="store_true",
        help="Join with market odds from overtime_ncaab_odds_{date}.csv",
    )
    p_slate.add_argument(
        "--home-adv",
        type=float,
        default=3.0,
        help="Home court advantage in points (default: 3.0)",
    )
    p_slate.add_argument(
        "--k",
        type=float,
        default=11.0,
        help="Sigmoid scale for win probability (default: 11.0)",
    )

    # Advanced stats
    p_ff = sub.add_parser("fourfactors", help="Fetch Four Factors data for a season")
    p_ff.add_argument("--y", type=int, required=True, help="Season year")

    p_pd = sub.add_parser("pointdist", help="Fetch point distribution data for a season")
    p_pd.add_argument("--y", type=int, required=True, help="Season year")

    p_ht = sub.add_parser("height", help="Fetch height/experience data for a season")
    p_ht.add_argument("--y", type=int, required=True, help="Season year")

    p_misc = sub.add_parser("miscstats", help="Fetch miscellaneous stats for a season")
    p_misc.add_argument("--y", type=int, required=True, help="Season year")

    # Home Court Advantage scraping
    p_hca = sub.add_parser("hca", help="Scrape Home Court Advantage data from KenPom")
    p_hca.add_argument("--y", type=int, default=2025, help="Season year (default: 2025)")
    p_hca.add_argument(
        "--headed", action="store_true", help="Run browser in headed mode (for debugging)"
    )

    args = parser.parse_args()
    settings = Settings.from_env()

    client = KenPomClient(settings)
    try:
        out_dir = Path(settings.out_dir)

        if args.cmd == "teams":
            data = client.teams(y=args.y)
            df = pd.DataFrame([t.model_dump() for t in data])
            _write_outputs(df, out_dir / f"kenpom_teams_{args.y}")

        elif args.cmd == "conferences":
            data = client.conferences(y=args.y)
            df = pd.DataFrame([c.model_dump() for c in data])
            _write_outputs(df, out_dir / f"kenpom_conferences_{args.y}")

        elif args.cmd == "ratings":
            # Build snapshot with optional enrichment
            df = build_snapshot_from_ratings(
                client=client,
                date=args.date,
                season_y=args.y,
                include_four_factors=args.four_factors,
                include_point_dist=args.point_dist,
                calculate_sigma=args.sigma,
            )

            # Add enriched suffix to filename if enrichment requested
            enriched = "_enriched" if (args.four_factors or args.point_dist) else ""
            filename = f"kenpom_ratings_{args.y}_{args.date}{enriched}"
            _write_outputs(df, out_dir / filename)

            if args.four_factors or args.point_dist:
                print("Enriched with: ", end="")
                enrichments = []
                if args.four_factors:
                    enrichments.append("four_factors")
                if args.point_dist:
                    enrichments.append("point_dist")
                if args.sigma:
                    enrichments.append("sigma")
                print(", ".join(enrichments))

        elif args.cmd == "archive":
            # Build snapshot with optional enrichment
            df = build_snapshot_from_archive(
                client=client,
                date=args.date,
                include_four_factors=args.four_factors,
                include_point_dist=args.point_dist,
                calculate_sigma=args.sigma,
            )

            # Add enriched suffix to filename if enrichment requested
            enriched = "_enriched" if (args.four_factors or args.point_dist) else ""
            filename = f"kenpom_archive_{args.date}{enriched}"
            _write_outputs(df, out_dir / filename)

            if args.four_factors or args.point_dist:
                print("Enriched with: ", end="")
                enrichments = []
                if args.four_factors:
                    enrichments.append("four_factors")
                if args.point_dist:
                    enrichments.append("point_dist")
                if args.sigma:
                    enrichments.append("sigma")
                print(", ".join(enrichments))

        elif args.cmd == "fanmatch":
            data = client.fanmatch(d=args.date)
            df = pd.DataFrame([g.model_dump() for g in data])
            _write_outputs(df, out_dir / f"kenpom_predictions_{args.date}")

        elif args.cmd == "slate":
            # Build slate with optional backtest mode
            use_archive = args.backtest
            df = fanmatch_slate_table(
                d=args.date,
                k=args.k,
                home_adv=args.home_adv,
                use_archive=use_archive,
                archive_fallback_to_ratings=True,
                client=client,
            )

            if df.empty:
                print(f"No games found for {args.date}")
                return

            # Validate backtest mode if enabled
            if use_archive:
                warnings = validate_backtest(df, args.date)
                if warnings:
                    print("BACKTEST VALIDATION WARNINGS:")
                    for w in warnings:
                        print(f"  - {w}")
                else:
                    print("Backtest validation: PASSED (all features time-correct)")

            # Join with odds if requested
            if args.join_odds:
                df = join_with_odds(df, odds_date=args.date)
                joined_count = df["odds_joined"].sum() if "odds_joined" in df.columns else 0
                print(f"Joined odds for {joined_count}/{len(df)} games")

            # Determine output filename
            suffix = "_backtest" if use_archive else ""
            suffix += "_with_odds" if args.join_odds else ""
            filename = f"kenpom_slate_{args.date}{suffix}"
            _write_outputs(df, out_dir / filename)

            # Summary
            print(f"\nSlate summary for {args.date}:")
            print(f"  Games: {len(df)}")
            print(f"  Method: {'archive (backtest)' if use_archive else 'ratings (live)'}")
            if "spread_edge" in df.columns:
                edges = df["spread_edge"].dropna()
                if len(edges) > 0:
                    print(f"  Avg spread edge: {edges.mean():+.1f} pts")

        elif args.cmd == "fourfactors":
            data = client.four_factors(y=args.y)
            df = pd.DataFrame([f.model_dump() for f in data])
            _write_outputs(df, out_dir / f"kenpom_fourfactors_{args.y}")

        elif args.cmd == "pointdist":
            data = client.point_distribution(y=args.y)
            df = pd.DataFrame([p.model_dump() for p in data])
            _write_outputs(df, out_dir / f"kenpom_pointdist_{args.y}")

        elif args.cmd == "height":
            data = client.height(y=args.y)
            df = pd.DataFrame([h.model_dump() for h in data])
            _write_outputs(df, out_dir / f"kenpom_height_{args.y}")

        elif args.cmd == "miscstats":
            data = client.misc_stats(y=args.y)
            df = pd.DataFrame([m.model_dump() for m in data])
            _write_outputs(df, out_dir / f"kenpom_miscstats_{args.y}")

        elif args.cmd == "hca":
            # HCA scraping uses Playwright, not the API client
            from datetime import date as date_type

            from .hca_scraper import HCAScraper

            scraper = HCAScraper(headless=not args.headed)
            snapshot = scraper.fetch_hca_data(season=args.y)

            if snapshot:
                today = date_type.today().isoformat()

                # Save JSON snapshot
                json_path = out_dir / f"kenpom_hca_{today}.json"
                json_path.parent.mkdir(parents=True, exist_ok=True)
                json_path.write_text(snapshot.to_json())
                print(f"HCA snapshot saved to: {json_path}")

                # Save CSV
                df = snapshot.to_dataframe()
                csv_path = out_dir / f"kenpom_hca_{today}.csv"
                df.to_csv(csv_path, index=False)
                print(f"HCA CSV saved to: {csv_path}")

                # Summary
                print(f"\nTeams scraped: {len(snapshot.teams)}")
                print(f"National average HCA: {snapshot.national_avg_hca:.2f}")

                # Top 5 HCAs
                sorted_teams = sorted(snapshot.teams, key=lambda t: t.hca, reverse=True)
                print("\nTop 5 Home Court Advantages:")
                for i, team in enumerate(sorted_teams[:5], 1):
                    print(f"  {i}. {team.team}: {team.hca:.2f}")
            else:
                print("ERROR: Failed to scrape HCA data")
                raise SystemExit(1)
            return  # Don't close API client (not used for HCA)

    finally:
        client.close()
