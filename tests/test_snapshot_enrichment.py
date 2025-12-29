"""Tests for snapshot enrichment functionality."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from kenpom_client.models import FourFactors, PointDistribution, Rating, Team
from kenpom_client.snapshot import (
    _calculate_sigma,
    _extract_season_from_archive_date,
    _merge_enrichment_data,
    build_snapshot_from_ratings,
)


class TestCalculateSigma:
    """Test sigma (scoring margin std dev) calculation."""

    def test_baseline_values(self):
        """Test sigma with median NCAA values."""
        sigma = _calculate_sigma(
            off_fg3=30.0,
            def_fg3=30.0,
            tempo=68.0,
        )
        # Should be close to 11.0 (base variance) with median values
        assert 10.5 < sigma < 11.5

    def test_high_tempo_increases_sigma(self):
        """High tempo should increase variance."""
        sigma_normal = _calculate_sigma(
            off_fg3=30.0,
            def_fg3=30.0,
            tempo=68.0,
        )

        sigma_high = _calculate_sigma(
            off_fg3=30.0,
            def_fg3=30.0,
            tempo=75.0,  # High tempo
        )

        assert sigma_high > sigma_normal

    def test_high_3pt_rate_increases_sigma(self):
        """High 3PT rate should increase variance."""
        sigma_normal = _calculate_sigma(
            off_fg3=30.0,
            def_fg3=30.0,
            tempo=68.0,
        )

        sigma_high_3pt = _calculate_sigma(
            off_fg3=40.0,  # High 3PT rate
            def_fg3=40.0,  # High 3PT rate
            tempo=68.0,
        )

        assert sigma_high_3pt > sigma_normal

    def test_sigma_clamped_to_range(self):
        """Sigma should be clamped to [9.5, 13.0]."""
        # Try extreme values that would produce very high sigma
        sigma_extreme = _calculate_sigma(
            off_fg3=50.0,  # Extreme 3PT
            def_fg3=50.0,
            tempo=80.0,  # Extreme tempo
        )

        assert 9.5 <= sigma_extreme <= 13.0


class TestExtractSeasonFromArchiveDate:
    """Test season inference from archive dates."""

    def test_november_date_next_year_season(self):
        """November should be next year's season."""
        season = _extract_season_from_archive_date("2024-11-15")
        assert season == 2025

    def test_december_date_next_year_season(self):
        """December should be next year's season."""
        season = _extract_season_from_archive_date("2024-12-20")
        assert season == 2025

    def test_march_date_current_year_season(self):
        """March should be current year's season."""
        season = _extract_season_from_archive_date("2025-03-15")
        assert season == 2025

    def test_october_date_current_year_season(self):
        """October should be current year's season."""
        season = _extract_season_from_archive_date("2024-10-31")
        assert season == 2024

    def test_january_date_current_year_season(self):
        """January should be current year's season."""
        season = _extract_season_from_archive_date("2025-01-15")
        assert season == 2025


class TestMergeEnrichmentData:
    """Test merging of base snapshots with enrichment data."""

    def test_exact_match_merging(self):
        """Test that exact team name matches populate enrichment fields."""
        from kenpom_client.snapshot import TeamSnapshot

        base_rows = [
            TeamSnapshot(
                date="2025-01-15",
                season=2025,
                team_id=1,
                team="Duke",
                conf="ACC",
                wins=15,
                losses=2,
                adj_em=25.5,
                adj_oe=120.0,
                adj_de=94.5,
                adj_tempo=70.0,
                tempo=70.0,
                sos=5.0,
            )
        ]

        ff_data = [
            FourFactors(
                DataThrough="2025-01-15",
                ConfOnly="N",
                TeamName="Duke",
                Season=2025,
                eFG_Pct=55.0,
                RankeFG_Pct=10,
                TO_Pct=18.0,
                RankTO_Pct=25,
                OR_Pct=32.0,
                RankOR_Pct=15,
                FT_Rate=35.0,
                RankFT_Rate=20,
                DeFG_Pct=48.0,
                RankDeFG_Pct=8,
                DTO_Pct=20.0,
                RankDTO_Pct=12,
                DOR_Pct=28.0,
                RankDOR_Pct=5,
                DFT_Rate=30.0,
                RankDFT_Rate=18,
                OE=110.0,
                RankOE=5,
                DE=95.0,
                RankDE=3,
                Tempo=70.0,
                RankTempo=100,
                AdjOE=120.0,
                RankAdjOE=4,
                AdjDE=94.5,
                RankAdjDE=2,
                AdjTempo=70.0,
                RankAdjTempo=95,
            )
        ]

        pd_data = [
            PointDistribution(
                DataThrough="2025-01-15",
                ConfOnly="N",
                Season=2025,
                TeamName="Duke",
                ConfShort="ACC",
                OffFt=20.0,
                RankOffFt=50,
                OffFg2=50.0,
                RankOffFg2=40,
                OffFg3=30.0,
                RankOffFg3=60,
                DefFt=18.0,
                RankDefFt=45,
                DefFg2=52.0,
                RankDefFg2=35,
                DefFg3=30.0,
                RankDefFg3=55,
            )
        ]

        enriched = _merge_enrichment_data(
            base_rows, ff_data, pd_data, include_sigma=True, date="2025-01-15"
        )

        assert len(enriched) == 1
        assert enriched[0].team == "Duke"
        assert enriched[0].efg_pct == 55.0
        assert enriched[0].off_ft == 20.0
        assert enriched[0].sigma is not None
        assert 10.0 < enriched[0].sigma < 12.0

    def test_missing_enrichment_data(self):
        """Test that missing enrichment data results in None fields."""
        from kenpom_client.snapshot import TeamSnapshot

        base_rows = [
            TeamSnapshot(
                date="2025-01-15",
                season=2025,
                team_id=1,
                team="Duke",
                conf="ACC",
                wins=15,
                losses=2,
                adj_em=25.5,
                adj_oe=120.0,
                adj_de=94.5,
                adj_tempo=70.0,
                tempo=70.0,
                sos=5.0,
            )
        ]

        # No enrichment data provided
        enriched = _merge_enrichment_data(
            base_rows, None, None, include_sigma=False, date="2025-01-15"
        )

        assert len(enriched) == 1
        assert enriched[0].team == "Duke"
        assert enriched[0].efg_pct is None
        assert enriched[0].off_ft is None
        assert enriched[0].sigma is None

    def test_dict_based_rows(self):
        """Test merging with dict-based rows (archive snapshots)."""
        base_rows = [
            {
                "date": "2025-01-15",
                "season": 2025,
                "team": "Duke",
                "conf": "ACC",
                "adj_em": 25.5,
                "adj_oe": 120.0,
                "adj_de": 94.5,
                "adj_tempo": 70.0,
                "preseason": "N",
            }
        ]

        ff_data = [
            FourFactors(
                DataThrough="2025-01-15",
                ConfOnly="N",
                TeamName="Duke",
                Season=2025,
                eFG_Pct=55.0,
                RankeFG_Pct=10,
                TO_Pct=18.0,
                RankTO_Pct=25,
                OR_Pct=32.0,
                RankOR_Pct=15,
                FT_Rate=35.0,
                RankFT_Rate=20,
                DeFG_Pct=48.0,
                RankDeFG_Pct=8,
                DTO_Pct=20.0,
                RankDTO_Pct=12,
                DOR_Pct=28.0,
                RankDOR_Pct=5,
                DFT_Rate=30.0,
                RankDFT_Rate=18,
                OE=110.0,
                RankOE=5,
                DE=95.0,
                RankDE=3,
                Tempo=70.0,
                RankTempo=100,
                AdjOE=120.0,
                RankAdjOE=4,
                AdjDE=94.5,
                RankAdjDE=2,
                AdjTempo=70.0,
                RankAdjTempo=95,
            )
        ]

        enriched = _merge_enrichment_data(
            base_rows, ff_data, None, include_sigma=False, date="2025-01-15"
        )

        assert len(enriched) == 1
        assert enriched[0].team == "Duke"
        assert enriched[0].efg_pct == 55.0
        assert enriched[0].team_id == -1  # Archive doesn't have team_id
        assert enriched[0].wins == 0  # Archive doesn't have wins/losses


class TestBuildEnrichedSnapshot:
    """Test building enriched snapshots."""

    def test_backward_compatibility_no_enrichment(self):
        """Test that snapshots without enrichment flags work as before."""
        # Mock client
        mock_client = Mock()
        mock_client.teams.return_value = [
            Team(Season=2025, TeamName="Duke", TeamID=1, ConfShort="ACC")
        ]
        mock_client.ratings.return_value = [
            Rating(
                DataThrough="2025-01-15",
                Season=2025,
                TeamName="Duke",
                ConfShort="ACC",
                Wins=15,
                Losses=2,
                AdjEM=25.5,
                AdjOE=120.0,
                AdjDE=94.5,
                AdjTempo=70.0,
                Tempo=70.0,
                SOS=5.0,
            )
        ]

        df = build_snapshot_from_ratings(client=mock_client, date="2025-01-15", season_y=2025)

        assert len(df) == 1
        assert "team" in df.columns
        assert "adj_em" in df.columns
        # Should NOT have enrichment columns
        assert "efg_pct" not in df.columns
        assert "off_ft" not in df.columns
        assert "sigma" not in df.columns

    def test_enrichment_with_four_factors(self):
        """Test snapshot enriched with four factors."""
        # Mock client
        mock_client = Mock()
        mock_client.teams.return_value = [
            Team(Season=2025, TeamName="Duke", TeamID=1, ConfShort="ACC")
        ]
        mock_client.ratings.return_value = [
            Rating(
                DataThrough="2025-01-15",
                Season=2025,
                TeamName="Duke",
                ConfShort="ACC",
                Wins=15,
                Losses=2,
                AdjEM=25.5,
                AdjOE=120.0,
                AdjDE=94.5,
                AdjTempo=70.0,
                Tempo=70.0,
                SOS=5.0,
            )
        ]
        mock_client.four_factors.return_value = [
            FourFactors(
                DataThrough="2025-01-15",
                ConfOnly="N",
                TeamName="Duke",
                Season=2025,
                eFG_Pct=55.0,
                RankeFG_Pct=10,
                TO_Pct=18.0,
                RankTO_Pct=25,
                OR_Pct=32.0,
                RankOR_Pct=15,
                FT_Rate=35.0,
                RankFT_Rate=20,
                DeFG_Pct=48.0,
                RankDeFG_Pct=8,
                DTO_Pct=20.0,
                RankDTO_Pct=12,
                DOR_Pct=28.0,
                RankDOR_Pct=5,
                DFT_Rate=30.0,
                RankDFT_Rate=18,
                OE=110.0,
                RankOE=5,
                DE=95.0,
                RankDE=3,
                Tempo=70.0,
                RankTempo=100,
                AdjOE=120.0,
                RankAdjOE=4,
                AdjDE=94.5,
                RankAdjDE=2,
                AdjTempo=70.0,
                RankAdjTempo=95,
            )
        ]

        df = build_snapshot_from_ratings(
            client=mock_client,
            date="2025-01-15",
            season_y=2025,
            include_four_factors=True,
        )

        assert len(df) == 1
        assert "efg_pct" in df.columns
        assert "to_pct" in df.columns
        assert "or_pct" in df.columns
        assert "ft_rate" in df.columns
        assert df.iloc[0]["efg_pct"] == 55.0

    def test_enrichment_with_sigma(self):
        """Test snapshot with sigma calculation."""
        # Mock client
        mock_client = Mock()
        mock_client.teams.return_value = [
            Team(Season=2025, TeamName="Duke", TeamID=1, ConfShort="ACC")
        ]
        mock_client.ratings.return_value = [
            Rating(
                DataThrough="2025-01-15",
                Season=2025,
                TeamName="Duke",
                ConfShort="ACC",
                Wins=15,
                Losses=2,
                AdjEM=25.5,
                AdjOE=120.0,
                AdjDE=94.5,
                AdjTempo=70.0,
                Tempo=70.0,
                SOS=5.0,
            )
        ]
        mock_client.point_distribution.return_value = [
            PointDistribution(
                DataThrough="2025-01-15",
                ConfOnly="N",
                Season=2025,
                TeamName="Duke",
                ConfShort="ACC",
                OffFt=20.0,
                RankOffFt=50,
                OffFg2=50.0,
                RankOffFg2=40,
                OffFg3=30.0,
                RankOffFg3=60,
                DefFt=18.0,
                RankDefFt=45,
                DefFg2=52.0,
                RankDefFg2=35,
                DefFg3=30.0,
                RankDefFg3=55,
            )
        ]

        df = build_snapshot_from_ratings(
            client=mock_client,
            date="2025-01-15",
            season_y=2025,
            include_point_dist=True,
            calculate_sigma=True,
        )

        assert len(df) == 1
        assert "off_ft" in df.columns
        assert "sigma" in df.columns
        assert df.iloc[0]["sigma"] is not None
        assert 9.5 <= df.iloc[0]["sigma"] <= 13.0

    def test_calculate_sigma_requires_point_dist(self):
        """Test that calculate_sigma=True requires include_point_dist=True."""
        mock_client = Mock()

        with pytest.raises(ValueError, match="calculate_sigma requires include_point_dist"):
            build_snapshot_from_ratings(
                client=mock_client,
                date="2025-01-15",
                season_y=2025,
                calculate_sigma=True,
                include_point_dist=False,
            )
