"""classifier.py — Topic and context classification.

Two classification layers:

1. **Supervised** (optional): ``TopicClassifier`` from ``topic_classifier.py``
   uses keyword/phrase matching against a YAML config.  Returns a confidence
   dict; a hit is used when the top score exceeds 0.3.

2. **Unsupervised fallback**: TF-IDF + k-means discovers categories directly
   from the chunk corpus, then a simple keyword-rule assigns each chunk.

Context classification (Work / Home / Social / …) runs independently via
entity and keyword matching.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

_console = Console()

# ---------------------------------------------------------------------------
# Unsupervised category discovery
# ---------------------------------------------------------------------------

_TERM_MAPPINGS: dict[str, str] = {
    "work": "work",
    "office": "work",
    "business": "work",
    "dinner": "social",
    "friend": "social",
    "home": "domestic",
    "family": "domestic",
    "money": "finance",
    "health": "health",
    "sick": "health",
    "church": "spiritual",
    "travel": "travel",
}


# Terms that rank highly in TF-IDF but say nothing about *topic*, so they make
# useless category names. Diaries are dense in honorifics and address forms
# ("my lord", "Mr", "Sir"), which are frequent, discriminative between clusters,
# and meaningless as labels — a real run produced
# "spiritual, mr, domestic, social, lord, domestic, day, lord, bed, sir".
#
# This is a heuristic list, not a claim about language. It only affects the
# *name* chosen for a cluster; the clustering itself is untouched.
_NON_TOPICAL_TERMS: frozenset[str] = frozenset(
    {
        # Honorifics and address forms
        "mr",
        "mrs",
        "ms",
        "sir",
        "madam",
        "lord",
        "lady",
        "master",
        "mistress",
        "dr",
        "captain",
        "col",
        "colonel",
        "my lord",
        "my lady",
        "sir william",
        "sir w",
        "mr moore",
        "good morrow",
        # Generic temporal / narrative filler
        "day",
        "days",
        "night",
        "morning",
        "evening",
        "afternoon",
        "time",
        "today",
        "yesterday",
        "hour",
        "week",
        "month",
        "year",
        "late",
        "early",
        # Generic diary verbs and motion, topically empty on their own
        "went",
        "came",
        "thence",
        "thither",
        "hither",
        "did",
        "done",
        "having",
        "away",
        "home again",
        "so home",
        "up betimes",
        "bed",
        "abed",
        "rose",
    }
)

# A name must be at least this long to be informative ("mr", "wm" are not).
_MIN_NAME_LEN = 4


def _is_informative(term: str) -> bool:
    """Whether *term* is usable as a category label.

    :param term: Candidate term from a cluster's top TF-IDF features.
    :return: ``True`` if it is long enough and not a known non-topical term.
    """
    t = term.strip().lower()
    return len(t) >= _MIN_NAME_LEN and t not in _NON_TOPICAL_TERMS


def _generate_category_name(top_terms: list[str]) -> str:
    """Derive a human-readable category name from a cluster's top terms.

    Prefers a curated mapping; otherwise falls back to the first *informative*
    term rather than blindly to ``top_terms[0]``, which routinely produced
    labels like ``mr`` and ``bed``. Those are not merely cosmetic: unmatched
    chunks fall back to ``categories[0]`` in :func:`classify_chunk`, so a
    garbage first category is written into the ``category`` frontmatter of every
    chunk that misses the keyword rules.

    :param top_terms: Cluster top terms, most significant first.
    :return: Category name; ``"general"`` when no term is usable.
    """
    for term in top_terms:
        mapped = _TERM_MAPPINGS.get(term.lower())
        if mapped:
            return mapped
    for term in top_terms:
        if _is_informative(term):
            return term.replace(" ", "_").lower()
    return "general"


# Fixed fallback so category discovery is reproducible when no seed is given.
# See discover_semantic_categories for why this is not left to chance.
_DEFAULT_CLUSTER_SEED = 0


def discover_semantic_categories(
    chunks: list[str], n_categories: int = 10, seed: int | None = None
) -> list[str]:
    """Discover topic categories from a corpus via TF-IDF k-means.

    Deterministic by default.  ``KMeans(random_state=None)`` re-initialises
    randomly on every call, so the discovered categories — and therefore the
    ``category``/``topics`` frontmatter of *every* chunk file — differed between
    builds of an identical corpus.  Measured: 86 of 818 chunk files (10.5%)
    changed content across two back-to-back ingests, which then propagated
    downstream as different chunk boundaries, embeddings and BM25 ranks.

    Unlike the diversity sampler in ``features.py``, which also clusters but
    generates *and reports* a seed when none is supplied, this call reported
    nothing — so an affected run could not be reproduced even after the fact.

    Category discovery fits a model over the whole chunk set; it is not a
    sampling decision, and its randomness serves no caller. An explicit *seed*
    still wins, so callers wanting to vary it can.

    :param chunks: All text chunks to cluster.
    :param n_categories: Desired number of categories.
    :param seed: RNG seed for reproducible clustering.  ``None`` (default) uses
        :data:`_DEFAULT_CLUSTER_SEED` rather than a random initialisation.
    :return: List of human-readable category name strings.
    """
    _console.print(
        f"  Discovering [bold]{n_categories}[/bold] semantic categories "
        f"from [bold]{len(chunks)}[/bold] chunks …"
    )

    n = min(n_categories, max(1, len(chunks) // 2))
    min_df = max(1, min(2, len(chunks) // 10))

    with _console.status("[dim]TF-IDF vectorising …[/dim]", spinner="dots"):
        vectorizer = TfidfVectorizer(
            max_features=1000, stop_words="english", ngram_range=(1, 2), min_df=min_df
        )
        tfidf = vectorizer.fit_transform(chunks)

    with _console.status(f"[dim]K-means clustering (k={n}) …[/dim]", spinner="dots"):
        kmeans = KMeans(
            n_clusters=n,
            random_state=_DEFAULT_CLUSTER_SEED if seed is None else seed,
        )
        kmeans.fit(tfidf)

    feature_names = vectorizer.get_feature_names_out()

    # Widen the candidate window past 5: with non-topical terms now skipped, a
    # cluster whose top terms are all honorifics still needs something to fall
    # back on before resorting to "general".
    categories: list[str] = []
    for i in range(n):
        top_idx = kmeans.cluster_centers_[i].argsort()[-12:][::-1]
        categories.append(_generate_category_name([feature_names[j] for j in top_idx]))

    # Distinct clusters can map to the same label — several terms share a
    # mapping, so two clusters both reach "domestic". A duplicated name makes
    # those clusters indistinguishable downstream: classify_chunk resolves a
    # label with `next(c for c in categories if label in c)`, so the second
    # cluster is unreachable and its slot is wasted. Deduplicate, preserving
    # discovery order.
    deduped = list(dict.fromkeys(categories))

    _console.print(f"  Categories: [dim]{', '.join(deduped)}[/dim]")
    if len(deduped) < n:
        _console.print(
            f"  [dim]({n} clusters collapsed to {len(deduped)} distinct "
            f"categories — _TERM_MAPPINGS resolves many terms onto a handful of "
            f"labels, so extra clusters cannot get distinct names. Widen it, or "
            f"lower n_categories to match.)[/dim]"
        )
    return deduped


# ---------------------------------------------------------------------------
# Chunk classification
# ---------------------------------------------------------------------------


def classify_chunk(chunk: str, categories: list[str]) -> str:
    """Assign a chunk to one of the discovered unsupervised categories.

    Uses simple keyword heuristics; falls back to the first category.

    :param chunk: Text chunk.
    :param categories: Categories returned by ``discover_semantic_categories``.
    :return: Matched category string.
    """
    cl = chunk.lower()
    rules = [
        (["work", "office", "business", "job"], "work"),
        (["dinner", "social", "friend"], "social"),
        (["home", "family", "house"], "domestic"),
        (["money", "paid", "cost"], "finance"),
    ]
    for keywords, label in rules:
        if any(kw in cl for kw in keywords):
            match = next((c for c in categories if label in c), None)
            if match:
                return match
    return categories[0]


def classify_chunk_hybrid(
    chunk: str,
    categories: list[str],
    topic_classifier: Any | None = None,
) -> tuple[str, dict[str, float]]:
    """Classify using supervised classification with unsupervised fallback.

    If *topic_classifier* is provided and its top prediction exceeds 0.3
    confidence, that result is returned.  Otherwise falls back to the
    unsupervised ``classify_chunk``.

    :param chunk: Text chunk to classify.
    :param categories: Unsupervised category list.
    :param topic_classifier: Optional ``TopicClassifier`` instance.
    :return: ``(category_name, confidence_dict)`` tuple.
    """
    if topic_classifier is not None:
        try:
            scores = topic_classifier.classify(chunk, return_list=False)
            if scores and scores != {"unknown": 0.0}:
                best_cat, best_score = max(scores.items(), key=lambda x: x[1])
                if best_score > 0.3:
                    return best_cat, scores
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"Warning: Supervised classification failed: {exc}")

    cat = classify_chunk(chunk, categories)
    return cat, {cat: 1.0}


# ---------------------------------------------------------------------------
# Context classification
# ---------------------------------------------------------------------------

_CONTEXT_KEYWORDS: dict[str, str] = {
    "work": "Work",
    "office": "Office",
    "home": "Home",
    "family": "Family",
    "money": "Finance",
    "dinner": "Social",
    "sick": "Health",
    "health": "Health",
}

_REFLECTION_WORDS = {"think", "believe", "suppose"}
_EMOTION_WORDS = {"feel", "angry", "pleased", "fear"}


def extract_context(chunk: str, nlp: Any) -> str:
    """Return a coarse context label for a chunk.

    :param chunk: Text chunk.
    :param nlp: Loaded spaCy model.
    :return: Context label string (``"Work"``, ``"Home"``, ``"Social"``, etc.).
    """
    cl = chunk.lower()
    for keyword, label in _CONTEXT_KEYWORDS.items():
        if keyword in cl:
            return label

    doc = nlp(chunk)
    for ent in doc.ents:
        et = ent.text.lower()
        if "work" in et or "office" in et:
            return "Work"
        if "home" in et or "house" in et:
            return "Home"

    if _REFLECTION_WORDS & set(cl.split()):
        return "Reflection"
    if _EMOTION_WORDS & set(cl.split()):
        return "Emotion"
    return "General"
