"""Tests for the effort classification module."""

import pytest

from kenpom_client.effort import (
    EffortClassification,
    EffortClassifier,
    EffortLevel,
    EffortSignals,
    classify_effort,
    classify_tool_effort,
    get_model_for_query,
    get_thinking_budget,
)


class TestEffortLevel:
    """Tests for EffortLevel enum."""

    def test_model_hints(self) -> None:
        """Test that each level has correct model hint."""
        assert EffortLevel.LOW.model_hint == "haiku"
        assert EffortLevel.MEDIUM.model_hint == "sonnet"
        assert EffortLevel.HIGH.model_hint == "opus"

    def test_thinking_budgets(self) -> None:
        """Test that thinking budgets increase with effort level."""
        assert EffortLevel.LOW.thinking_budget < EffortLevel.MEDIUM.thinking_budget
        assert EffortLevel.MEDIUM.thinking_budget < EffortLevel.HIGH.thinking_budget


class TestEffortClassifier:
    """Tests for EffortClassifier."""

    @pytest.fixture
    def classifier(self) -> EffortClassifier:
        """Create a default classifier."""
        return EffortClassifier()

    def test_low_effort_queries(self, classifier: EffortClassifier) -> None:
        """Test that simple lookups are classified as LOW."""
        low_queries = [
            "What is Duke's current ranking?",
            "Show me the ratings for Kentucky",
            "Get the stats for North Carolina",
            "List all teams in the ACC",
            "Find Duke's AdjEM",
            "What's the current ranking?",
        ]
        for query in low_queries:
            result = classifier.classify(query)
            assert result.level == EffortLevel.LOW, f"Expected LOW for: {query}"
            assert result.confidence > 0.5

    def test_medium_effort_queries(self, classifier: EffortClassifier) -> None:
        """Test that analytical queries are classified as MEDIUM."""
        medium_queries = [
            "How does Duke's offense compare to their defense?",
            "Explain the four factors for Kentucky",
            "Why is Gonzaga ranked so high?",
            "Compare the top 5 teams in efficiency",
            "Summarize the Big 10 conference performance",
        ]
        for query in medium_queries:
            result = classifier.classify(query)
            assert result.level in (EffortLevel.MEDIUM, EffortLevel.HIGH), (
                f"Expected MEDIUM+ for: {query}"
            )

    def test_high_effort_queries(self, classifier: EffortClassifier) -> None:
        """Test that complex/agentic queries are classified as HIGH."""
        high_queries = [
            "Implement a prediction model using KenPom data",
            "Build a backtesting system for tournament predictions",
            "Debug why the ratings aren't updating correctly",
            "Refactor the matchup analysis to include tempo adjustments",
            "Design an architecture for real-time rating updates",
            "Create a feature that tracks rating changes over time",
            "Why is the prediction not working correctly?",
        ]
        for query in high_queries:
            result = classifier.classify(query)
            assert result.level == EffortLevel.HIGH, f"Expected HIGH for: {query}"

    def test_classification_returns_signals(self, classifier: EffortClassifier) -> None:
        """Test that classification includes matched signals."""
        result = classifier.classify("Implement a new prediction feature")
        assert len(result.signals_matched) > 0
        assert result.reasoning != ""

    def test_classification_confidence_range(self, classifier: EffortClassifier) -> None:
        """Test that confidence is always between 0 and 1."""
        queries = [
            "Get ratings",
            "Compare Duke and UNC",
            "Build a complex multi-model prediction system with backtesting",
        ]
        for query in queries:
            result = classifier.classify(query)
            assert 0.0 <= result.confidence <= 1.0

    def test_long_queries_boost_effort(self, classifier: EffortClassifier) -> None:
        """Test that very long queries increase effort level."""
        short = "Get ratings"
        long = (
            "I need you to analyze the historical performance of all Big 10 teams "
            "over the past 5 seasons, compare their offensive and defensive efficiency "
            "ratings, identify trends in their four factors metrics, and create a "
            "comprehensive report with visualizations showing how each team has "
            "evolved their playing style. Additionally, cross-reference this with "
            "their tournament performance and calculate correlation coefficients."
        )
        short_result = classifier.classify(short)
        long_result = classifier.classify(long)

        # Long query should have higher or equal effort
        effort_order = {EffortLevel.LOW: 0, EffortLevel.MEDIUM: 1, EffortLevel.HIGH: 2}
        assert effort_order[long_result.level] >= effort_order[short_result.level]

    def test_custom_signals(self) -> None:
        """Test that custom signals work correctly."""
        custom_signals = EffortSignals(
            high_patterns=[r"\bcustom_high\b"],
            medium_patterns=[r"\bcustom_medium\b"],
            low_patterns=[r"\bcustom_low\b"],
            complexity_patterns=[],
        )
        classifier = EffortClassifier(signals=custom_signals)

        assert classifier.classify("custom_high task").level == EffortLevel.HIGH
        assert classifier.classify("custom_medium task").level == EffortLevel.MEDIUM
        assert classifier.classify("custom_low task").level == EffortLevel.LOW


class TestToolEffortClassification:
    """Tests for tool-based effort classification."""

    def test_classify_tool_with_metadata(self) -> None:
        """Test that explicit metadata overrides analysis."""
        result = classify_tool_effort(
            tool_name="any_tool",
            arguments={"complex": "data"},
            tool_metadata={"effort_level": "high"},
        )
        assert result.level == EffortLevel.HIGH
        assert result.confidence == 1.0

    def test_classify_tool_without_metadata(self) -> None:
        """Test that tools without metadata fall back to query analysis."""
        result = classify_tool_effort(
            tool_name="get_ratings",
            arguments={"team": "Duke"},
            tool_metadata=None,
        )
        # Should classify based on tool name + args
        assert result.level in (EffortLevel.LOW, EffortLevel.MEDIUM)


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_classify_effort_function(self) -> None:
        """Test the classify_effort convenience function."""
        result = classify_effort("Get Duke's ratings")
        assert isinstance(result, EffortClassification)
        assert result.level == EffortLevel.LOW

    def test_get_model_for_query(self) -> None:
        """Test model hint retrieval."""
        assert get_model_for_query("show ratings") == "haiku"
        assert get_model_for_query("implement feature") == "opus"

    def test_get_thinking_budget(self) -> None:
        """Test thinking budget retrieval."""
        low_budget = get_thinking_budget("get ratings")
        high_budget = get_thinking_budget("implement complex feature")
        assert high_budget > low_budget


class TestEffortClassificationDataclass:
    """Tests for EffortClassification dataclass."""

    def test_model_hint_property(self) -> None:
        """Test that model_hint property works."""
        classification = EffortClassification(
            level=EffortLevel.HIGH,
            confidence=0.9,
            signals_matched=["implement"],
            reasoning="High complexity detected",
        )
        assert classification.model_hint == "opus"

    def test_thinking_budget_property(self) -> None:
        """Test that thinking_budget property works."""
        classification = EffortClassification(
            level=EffortLevel.LOW,
            confidence=0.8,
            signals_matched=["get"],
            reasoning="Simple lookup",
        )
        assert classification.thinking_budget == 1024
