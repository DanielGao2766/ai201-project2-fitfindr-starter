"""
tests/test_tools.py

Pytest tests for each FitFindr tool. Tests cover:
- Happy path (correct return type and content)
- Each failure mode (empty results, empty wardrobe, empty outfit)
- Filter correctness (price ceiling, size substring match)

Run with:
    pytest tests/
"""

import pytest

from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0
    assert isinstance(results[0], dict)
    assert "title" in results[0]


def test_search_empty_results():
    """Impossible query — should return [] without raising."""
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    """No result should exceed the price ceiling."""
    results = search_listings("jacket", size=None, max_price=30)
    assert all(item["price"] <= 30 for item in results)


def test_search_no_price_filter():
    """Without a price ceiling, results may include expensive items."""
    results_no_filter = search_listings("jacket", size=None, max_price=None)
    results_filtered = search_listings("jacket", size=None, max_price=30)
    assert len(results_no_filter) >= len(results_filtered)


def test_search_size_filter():
    """Size filter uses case-insensitive substring match."""
    results = search_listings("top", size="M", max_price=None)
    for item in results:
        assert "m" in item["size"].lower()


def test_search_result_order():
    """More keyword matches should rank higher."""
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    assert len(results) > 0
    # First result must contain at least one of the keywords
    combined = " ".join([
        results[0]["title"],
        results[0]["description"],
        results[0]["category"],
        " ".join(results[0]["style_tags"]),
    ]).lower()
    keywords = {"vintage", "graphic", "tee"}
    assert any(kw in combined for kw in keywords)


def test_search_returns_list_on_no_match_no_exception():
    """Completely nonsense query — must return [] not raise."""
    results = search_listings("zzzyyyxxx123", size=None, max_price=None)
    assert results == []


# ── suggest_outfit ────────────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    """With a populated wardrobe, returns a non-empty string."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    result = suggest_outfit(results[0], get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_suggest_outfit_empty_wardrobe_returns_string():
    """Empty wardrobe must return general advice (not raise, not return empty)."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    result = suggest_outfit(results[0], get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_returns_string():
    """Happy path — returns a non-empty caption string."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    outfit = suggest_outfit(results[0], get_example_wardrobe())
    card = create_fit_card(outfit, results[0])
    assert isinstance(card, str)
    assert len(card.strip()) > 0


def test_create_fit_card_empty_outfit_returns_error_string():
    """Empty outfit must return an error string, not raise an exception."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    result = create_fit_card("", results[0])
    assert isinstance(result, str)
    assert len(result.strip()) > 0
    # Should communicate that no outfit was available
    assert any(word in result.lower() for word in ["unable", "no outfit", "missing", "error"])


def test_create_fit_card_whitespace_outfit_returns_error_string():
    """Whitespace-only outfit is treated the same as empty."""
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    result = create_fit_card("   ", results[0])
    assert isinstance(result, str)
    assert any(word in result.lower() for word in ["unable", "no outfit", "missing", "error"])
