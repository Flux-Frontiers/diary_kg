"""
test_diary_transformer_classifier.py

Unit tests for diary_transformer.classifier — unsupervised category
discovery, chunk classification, hybrid classification, and context
extraction.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from diary_transformer.classifier import (
    _NON_TOPICAL_TERMS,
    _generate_category_name,
    classify_chunk,
    classify_chunk_hybrid,
    discover_semantic_categories,
    extract_context,
)


class TestDiscoverSemanticCategories:
    def test_returns_list_of_strings(self):
        chunks = [
            "Went to the office to do work business.",
            "Had dinner with friends at the social club.",
            "Paid the bills and managed the household money.",
            "Felt sick and stayed home in bed.",
            "Prayed at church this Sunday morning.",
        ] * 4  # repeat to give kmeans enough data
        cats = discover_semantic_categories(chunks, n_categories=3, seed=42)
        assert isinstance(cats, list)
        assert len(cats) > 0
        assert all(isinstance(c, str) for c in cats)

    def test_fewer_categories_than_chunks(self):
        chunks = ["work meeting office"] * 6
        cats = discover_semantic_categories(chunks, n_categories=5, seed=0)
        # Can't have more categories than unique samples
        assert len(cats) <= 5

    def test_single_chunk_returns_one_category(self):
        cats = discover_semantic_categories(["only one chunk here"], n_categories=3, seed=0)
        assert len(cats) == 1

    def test_seed_produces_reproducible_results(self):
        chunks = ["work office meeting"] * 10 + ["home family dinner"] * 10
        a = discover_semantic_categories(chunks, seed=99)
        b = discover_semantic_categories(chunks, seed=99)
        assert a == b


class TestClassifyChunk:
    def test_work_keyword(self):
        categories = ["work", "social", "domestic", "finance"]
        result = classify_chunk("Went to the office for business", categories)
        assert result == "work"

    def test_social_keyword(self):
        categories = ["work", "social", "domestic", "finance"]
        result = classify_chunk("Had dinner with a friend at the club", categories)
        assert result == "social"

    def test_domestic_keyword(self):
        categories = ["work", "social", "domestic", "finance"]
        result = classify_chunk("At home with the family this evening", categories)
        assert result == "domestic"

    def test_finance_keyword(self):
        categories = ["work", "social", "domestic", "finance"]
        result = classify_chunk("Paid the money I owed to the merchant", categories)
        assert result == "finance"

    def test_fallback_to_first_category(self):
        categories = ["misc", "work", "social"]
        result = classify_chunk("Something unrelated entirely", categories)
        assert result == "misc"


class TestClassifyChunkHybrid:
    def test_uses_supervised_when_confident(self):
        mock_tc = MagicMock()
        mock_tc.classify.return_value = {"health": 0.8, "work": 0.1}
        categories = ["work", "social"]
        cat, scores = classify_chunk_hybrid("Felt very ill today", categories, mock_tc)
        assert cat == "health"
        assert scores["health"] == 0.8

    def test_falls_back_when_supervised_below_threshold(self):
        mock_tc = MagicMock()
        mock_tc.classify.return_value = {"health": 0.2, "work": 0.1}
        categories = ["work", "social", "domestic"]
        cat, scores = classify_chunk_hybrid("At home with the family", categories, mock_tc)
        # Should fall back to unsupervised — domestic keyword matches
        assert cat == "domestic"

    def test_falls_back_when_no_classifier(self):
        categories = ["work", "social"]
        cat, scores = classify_chunk_hybrid("office work meeting", categories, None)
        assert cat == "work"

    def test_falls_back_on_classifier_exception(self):
        mock_tc = MagicMock()
        mock_tc.classify.side_effect = RuntimeError("model error")
        categories = ["work", "social"]
        # Should not raise — falls back to unsupervised
        cat, scores = classify_chunk_hybrid("office work", categories, mock_tc)
        assert isinstance(cat, str)

    def test_ignores_unknown_only_result(self):
        mock_tc = MagicMock()
        mock_tc.classify.return_value = {"unknown": 0.0}
        categories = ["work", "social"]
        cat, scores = classify_chunk_hybrid("office work", categories, mock_tc)
        assert cat == "work"  # fell back to unsupervised


class TestExtractContext:
    @pytest.fixture
    def nlp(self):
        """Minimal spaCy-like mock."""
        mock = MagicMock()
        doc = MagicMock()
        doc.ents = []
        doc.sents = []
        mock.return_value = doc
        return mock

    def test_work_keyword(self, nlp):
        assert extract_context("Went to work today", nlp) == "Work"

    def test_office_keyword(self, nlp):
        assert extract_context("At the office all morning", nlp) == "Office"

    def test_home_keyword(self, nlp):
        assert extract_context("Stayed at home all day", nlp) == "Home"

    def test_family_keyword(self, nlp):
        assert extract_context("With my family tonight", nlp) == "Family"

    def test_money_keyword(self, nlp):
        assert extract_context("Paid the money owed", nlp) == "Finance"

    def test_dinner_keyword(self, nlp):
        assert extract_context("Had dinner at the club", nlp) == "Social"

    def test_health_keyword(self, nlp):
        assert extract_context("My health is poor today", nlp) == "Health"

    def test_sick_keyword(self, nlp):
        assert extract_context("I am sick and in bed", nlp) == "Health"

    def test_reflection_words(self, nlp):
        # No keyword match — falls through to word set check
        doc = MagicMock()
        doc.ents = []
        nlp.return_value = doc
        result = extract_context("I think this is a problem", nlp)
        assert result == "Reflection"

    def test_emotion_words(self, nlp):
        doc = MagicMock()
        doc.ents = []
        nlp.return_value = doc
        result = extract_context("I feel angry about it", nlp)
        assert result == "Emotion"

    def test_general_fallback(self, nlp):
        doc = MagicMock()
        doc.ents = []
        nlp.return_value = doc
        result = extract_context("The weather was fine today", nlp)
        assert result == "General"


# ---------------------------------------------------------------------------
# Reproducibility of category discovery
# ---------------------------------------------------------------------------


class TestCategoryDiscoveryIsDeterministic:
    """Category discovery must not vary between runs.

    ``KMeans(random_state=None)`` re-initialised randomly on every call, so the
    discovered categories — and hence the ``category``/``topics`` frontmatter of
    every chunk file — differed between builds of an identical corpus. Measured
    at 86 of 818 chunk files (10.5%) changing content across two back-to-back
    ingests, which propagated downstream into different chunk boundaries,
    embeddings and BM25 ranks, and made any A/B comparison of the corpus
    meaningless.
    """

    CHUNKS = [
        "Up betimes and to the office, where we sat all the morning on Navy business.",
        "Dined at home with my wife, and after dinner to the theatre to see a play.",
        "To church this morning, where a very dull sermon from the young parson.",
        "My head aching mightily, so home early and to bed without supper.",
        "Received letters from my Lord touching the fleet and the victualling.",
        "Walked in the garden with Sir William, discoursing of the Dutch war.",
        "Paid my bills and cast up my accounts, finding myself worth two hundred pound.",
        "Music and singing after supper, my wife playing upon the lute.",
        "A great fire seen from the bridge, much talk of it in the city.",
        "Sick and abed all day, physic taken, and my wife very tender with me.",
        "At the office all afternoon upon the contract for masts and timber.",
        "Supper with my cousin, who told me news of the King's return.",
    ]

    def test_unseeded_calls_agree(self):
        """Two default calls must return the same categories."""
        a = discover_semantic_categories(self.CHUNKS, n_categories=3)
        b = discover_semantic_categories(self.CHUNKS, n_categories=3)
        assert a == b

    def test_explicit_seed_still_honoured(self):
        """An explicit seed must still control clustering."""
        a = discover_semantic_categories(self.CHUNKS, n_categories=3, seed=7)
        b = discover_semantic_categories(self.CHUNKS, n_categories=3, seed=7)
        assert a == b

    def test_seed_none_matches_the_documented_default(self):
        """seed=None must behave as the fixed default, not as randomness."""
        from diary_transformer.classifier import _DEFAULT_CLUSTER_SEED

        assert discover_semantic_categories(
            self.CHUNKS, n_categories=3
        ) == discover_semantic_categories(self.CHUNKS, n_categories=3, seed=_DEFAULT_CLUSTER_SEED)


# ---------------------------------------------------------------------------
# Category naming quality
# ---------------------------------------------------------------------------


class TestCategoryNaming:
    """Names must be topical, not honorifics or narrative filler.

    Falling back blindly to ``top_terms[0]`` produced labels like ``mr``,
    ``lord``, ``bed`` and ``day``. Those are not cosmetic: ``classify_chunk``
    routes any chunk missing its keyword rules to ``categories[0]``, so a
    garbage first category is written into the ``category`` frontmatter of a
    large share of the corpus.
    """

    def test_curated_mapping_wins(self):
        assert _generate_category_name(["office", "ledger"]) == "work"

    def test_honorifics_are_skipped(self):
        assert _generate_category_name(["mr", "lord", "sir", "shipping"]) == "shipping"

    def test_narrative_filler_is_skipped(self):
        assert _generate_category_name(["day", "bed", "went", "theatre"]) == "theatre"

    def test_short_terms_are_skipped(self):
        assert _generate_category_name(["wm", "ye", "navy"]) == "navy"

    def test_all_useless_falls_back_to_general(self):
        assert _generate_category_name(["mr", "sir", "day", "bed"]) == "general"

    def test_multiword_terms_are_underscored(self):
        assert _generate_category_name(["naval stores"]) == "naval_stores"

    def test_mapping_beats_an_earlier_informative_term(self):
        """A curated mapping outranks position, so labels stay stable."""
        assert _generate_category_name(["shipping", "church"]) == "spiritual"


class TestCategoriesAreDeduplicated:
    """Distinct clusters mapping to one label must not appear twice.

    ``classify_chunk`` resolves a label with
    ``next(c for c in categories if label in c)``, so a duplicate is
    unreachable and its cluster slot is wasted. A real run returned
    ``domestic`` and ``lord`` twice each.
    """

    CHUNKS = TestCategoryDiscoveryIsDeterministic.CHUNKS

    def test_no_duplicates_returned(self):
        cats = discover_semantic_categories(self.CHUNKS, n_categories=6)
        assert len(cats) == len(set(cats))

    def test_order_is_preserved(self):
        cats = discover_semantic_categories(self.CHUNKS, n_categories=6)
        assert cats == list(dict.fromkeys(cats))

    def test_no_honorific_or_filler_labels(self):
        cats = discover_semantic_categories(self.CHUNKS, n_categories=6)
        assert not (set(cats) & _NON_TOPICAL_TERMS), cats
