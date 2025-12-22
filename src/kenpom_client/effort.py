"""Dynamic effort classification for AI-assisted workflows.

This module provides utilities to classify user queries and tool calls
by complexity, enabling dynamic allocation of reasoning effort:
- Low effort: Simple lookups, single-fact retrieval
- Medium effort: Moderate reasoning, explanations
- High effort: Complex reasoning, agentic coding, multi-step tasks

Usage:
    from kenpom_client.effort import classify_effort, EffortLevel

    effort = classify_effort("What's Duke's current ranking?")
    # Returns: EffortLevel.LOW

    effort = classify_effort("Implement a prediction model using historical data")
    # Returns: EffortLevel.HIGH
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EffortLevel(Enum):
    """Effort levels for query classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def model_hint(self) -> str:
        """Suggested model for this effort level."""
        return {
            EffortLevel.LOW: "haiku",
            EffortLevel.MEDIUM: "sonnet",
            EffortLevel.HIGH: "opus",
        }[self]

    @property
    def thinking_budget(self) -> int:
        """Suggested thinking token budget."""
        return {
            EffortLevel.LOW: 1024,
            EffortLevel.MEDIUM: 4096,
            EffortLevel.HIGH: 16384,
        }[self]


@dataclass
class EffortSignals:
    """Configurable signals for effort classification."""

    # High effort indicators (agentic, complex reasoning)
    high_patterns: list[str] = field(
        default_factory=lambda: [
            r"\bimplement\b",
            r"\brefactor\b",
            r"\bdebug\b",
            r"\bdesign\b",
            r"\bbuild\b",
            r"\bcreate\b",
            r"\bfix\s+bug\b",
            r"\barchitect\b",
            r"\boptimize\b",
            r"\banalyze\s+.*\s+and\b",  # Multi-step analysis
            r"\bcompare\s+.*\s+across\b",  # Cross-comparison
            r"\bpredict\b",
            r"\bmodel\b",
            r"\bbacktest\b",
            r"\bintegrate\b",
            r"\bmigrate\b",
            r"\bwrite\s+.*\s+code\b",
            r"\badd\s+.*\s+feature\b",
            r"\bplan\b",
            r"\bstrategy\b",
            r"\bwhy\s+.*\s+not\s+working\b",
        ]
    )

    # Medium effort indicators (moderate reasoning)
    medium_patterns: list[str] = field(
        default_factory=lambda: [
            r"\bhow\s+does\b",
            r"\bexplain\b",
            r"\bwhy\b",
            r"\bcompare\b",
            r"\bdifference\b",
            r"\btrend\b",
            r"\bsummarize\b",
            r"\brecommend\b",
            r"\bsuggest\b",
            r"\bevaluate\b",
            r"\bwhich\s+is\s+better\b",
            r"\bpros\s+and\s+cons\b",
        ]
    )

    # Low effort indicators (simple lookups)
    low_patterns: list[str] = field(
        default_factory=lambda: [
            r"\bwhere\s+is\b",
            r"\bshow\s+me\b",
            r"\bshow\b",
            r"\bfind\b",
            r"\bwhat\s+is\b",
            r"\blist\b",
            r"\bget\b",
            r"\blookup\b",
            r"\bfetch\b",
            r"\bretrieve\b",
            r"\bwhat's\b",
            r"\brating\b",
            r"\branking\b",
            r"\bstats\s+for\b",
            r"\btoday's\b",
            r"\bcurrent\b",
        ]
    )

    # Complexity multipliers (increase effort level)
    complexity_patterns: list[str] = field(
        default_factory=lambda: [
            r"\bmultiple\b",
            r"\ball\s+teams\b",
            r"\bevery\b",
            r"\bacross\b",
            r"\bover\s+time\b",
            r"\bhistorical\b",
            r"\bseason\s+by\s+season\b",
            r"\band\s+also\b",
            r"\bthen\b",
            r"\bafter\s+that\b",
        ]
    )


@dataclass
class EffortClassification:
    """Result of effort classification."""

    level: EffortLevel
    confidence: float  # 0.0 - 1.0
    signals_matched: list[str]
    reasoning: str

    @property
    def model_hint(self) -> str:
        """Suggested model based on effort level."""
        return self.level.model_hint

    @property
    def thinking_budget(self) -> int:
        """Suggested thinking token budget."""
        return self.level.thinking_budget


class EffortClassifier:
    """Classifies queries by effort level for dynamic routing."""

    def __init__(self, signals: EffortSignals | None = None):
        """Initialize with optional custom signals."""
        self.signals = signals or EffortSignals()
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        self._high_re = [re.compile(p, re.IGNORECASE) for p in self.signals.high_patterns]
        self._medium_re = [re.compile(p, re.IGNORECASE) for p in self.signals.medium_patterns]
        self._low_re = [re.compile(p, re.IGNORECASE) for p in self.signals.low_patterns]
        self._complexity_re = [
            re.compile(p, re.IGNORECASE) for p in self.signals.complexity_patterns
        ]

    def classify(self, query: str) -> EffortClassification:
        """Classify a query by effort level.

        Args:
            query: The user query or prompt to classify

        Returns:
            EffortClassification with level, confidence, and reasoning
        """
        query_lower = query.lower()
        signals_matched: list[str] = []

        # Count matches at each level
        high_matches = self._count_matches(query_lower, self._high_re, signals_matched)
        medium_matches = self._count_matches(query_lower, self._medium_re, signals_matched)
        low_matches = self._count_matches(query_lower, self._low_re, signals_matched)
        complexity_boost = self._count_matches(query_lower, self._complexity_re, signals_matched)

        # Calculate base scores
        # Only apply complexity boost if there are actual high/medium signals
        # Otherwise simple queries like "list all teams" shouldn't become HIGH
        effective_complexity = complexity_boost if (high_matches > 0 or medium_matches > 0) else 0
        high_score = high_matches * 3 + effective_complexity
        medium_score = medium_matches * 2 + (complexity_boost if medium_matches > 0 else 0)
        low_score = low_matches * 1

        # Query length heuristic (longer queries often need more reasoning)
        word_count = len(query.split())
        if word_count > 50:
            high_score += 2
        elif word_count > 20:
            medium_score += 1

        # Determine level based on scores
        total_score = high_score + medium_score + low_score
        if total_score == 0:
            # Default to medium for ambiguous queries
            level = EffortLevel.MEDIUM
            confidence = 0.5
            reasoning = "No clear signals detected, defaulting to medium effort"
        elif high_score >= medium_score and high_score >= low_score:
            level = EffortLevel.HIGH
            confidence = min(0.95, 0.5 + (high_score / max(total_score, 1)) * 0.5)
            reasoning = f"High complexity signals detected: {', '.join(signals_matched[:3])}"
        elif medium_score >= low_score:
            level = EffortLevel.MEDIUM
            confidence = min(0.9, 0.5 + (medium_score / max(total_score, 1)) * 0.4)
            reasoning = f"Moderate reasoning required: {', '.join(signals_matched[:3])}"
        else:
            level = EffortLevel.LOW
            confidence = min(0.95, 0.6 + (low_score / max(total_score, 1)) * 0.35)
            reasoning = f"Simple lookup/retrieval: {', '.join(signals_matched[:3])}"

        return EffortClassification(
            level=level,
            confidence=confidence,
            signals_matched=signals_matched,
            reasoning=reasoning,
        )

    def _count_matches(self, text: str, patterns: list[re.Pattern[str]], signals: list[str]) -> int:
        """Count pattern matches and collect matched signals."""
        count = 0
        for pattern in patterns:
            if pattern.search(text):
                count += 1
                signals.append(pattern.pattern)
        return count

    def classify_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_metadata: dict[str, Any] | None = None,
    ) -> EffortClassification:
        """Classify a tool call by effort level.

        Args:
            tool_name: Name of the tool being called
            arguments: Arguments passed to the tool
            tool_metadata: Optional metadata about the tool (e.g., effort hints)

        Returns:
            EffortClassification for the tool call
        """
        # Check for explicit effort hints in tool metadata
        if tool_metadata and "effort_level" in tool_metadata:
            level = EffortLevel(tool_metadata["effort_level"])
            return EffortClassification(
                level=level,
                confidence=1.0,
                signals_matched=["explicit_metadata"],
                reasoning=f"Tool has explicit effort level: {level.value}",
            )

        # Build a description string from tool call
        description = f"{tool_name} {' '.join(str(v) for v in arguments.values())}"
        return self.classify(description)


# Module-level convenience functions
_default_classifier = EffortClassifier()


def classify_effort(query: str) -> EffortClassification:
    """Classify a query's effort level using the default classifier.

    Args:
        query: The user query to classify

    Returns:
        EffortClassification with level, confidence, and reasoning
    """
    return _default_classifier.classify(query)


def classify_tool_effort(
    tool_name: str,
    arguments: dict[str, Any],
    tool_metadata: dict[str, Any] | None = None,
) -> EffortClassification:
    """Classify a tool call's effort level.

    Args:
        tool_name: Name of the tool
        arguments: Tool arguments
        tool_metadata: Optional tool metadata with effort hints

    Returns:
        EffortClassification for the tool call
    """
    return _default_classifier.classify_tool_call(tool_name, arguments, tool_metadata)


def get_model_for_query(query: str) -> str:
    """Get the recommended model for a query.

    Args:
        query: The user query

    Returns:
        Model name hint (haiku, sonnet, or opus)
    """
    return classify_effort(query).model_hint


def get_thinking_budget(query: str) -> int:
    """Get the recommended thinking token budget for a query.

    Args:
        query: The user query

    Returns:
        Suggested thinking token budget
    """
    return classify_effort(query).thinking_budget
