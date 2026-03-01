"""
Auto-labeling pipeline (WP-7).
Tier 0: user-defined label rules (app name / title keyword)
Tier 1: exact-match SQLite cache
Tier 2: FAISS embedding similarity
"""

import logging
from dataclasses import dataclass
from typing import Literal

from ..models import TimelineEvent
from . import cache_service
from .embedding_service import EMBEDDING_HIGH_THRESHOLD, EmbeddingService
from .rule_service import apply_rules
from .signature_service import event_signature

logger = logging.getLogger(__name__)


@dataclass
class AutoLabelResult:
    workflow_id: str
    confidence: Literal["high", "medium"]
    source: Literal["cache", "embedding", "rule"]
    score: float       # 0.0–1.0 normalized (1.0 for cache/rule hits)
    explanation: str   # Human-readable: shown as tooltip in UI


def auto_label_events(
    events: list[TimelineEvent],
    embedding_service: EmbeddingService,
) -> dict[tuple[str, int], AutoLabelResult]:
    """
    Run the tiered auto-labeling pipeline on timeline events.

    Tier 0: user-defined label rules (app / title_keyword)
    Tier 1: SQLite exact-match cache (event_signature → workflow_id)
    Tier 2: FAISS embedding similarity (semantic nearest-neighbor)
    """
    results: dict[tuple[str, int], AutoLabelResult] = {}
    unlabeled = [e for e in events if e.session_id is None]
    if not unlabeled:
        return results

    # --- Tier 0: User-defined rules (highest priority) ---
    rule_matches = apply_rules(unlabeled)
    rule_matched_keys: set[tuple[str, int]] = set()
    for key, (wf_id, _wf_name, explanation) in rule_matches.items():
        results[key] = AutoLabelResult(
            workflow_id=wf_id,
            confidence="high",
            source="rule",
            score=1.0,
            explanation=explanation,
        )
        rule_matched_keys.add(key)

    # Only run cache/embedding on events not matched by rules
    after_rules = [e for e in unlabeled if (e.aw_bucket_id, e.aw_event_id) not in rule_matched_keys]
    if not after_rules:
        return results

    # Compute signature for each remaining event
    event_sigs: dict[tuple[str, int], str] = {
        (e.aw_bucket_id, e.aw_event_id): event_signature(e.data)
        for e in after_rules
    }

    # --- Tier 1: Batch cache lookup ---
    unique_sigs = list({s for s in event_sigs.values() if s and s != "unknown||"})
    cache_hits = cache_service.bulk_lookup(unique_sigs)

    remaining: list[TimelineEvent] = []
    for event in after_rules:
        key = (event.aw_bucket_id, event.aw_event_id)
        sig = event_sigs[key]
        if sig not in cache_hits:
            remaining.append(event)
            continue

        wf_id = cache_hits[sig]
        # Skip if user has dismissed this combo too many times
        if cache_service.is_dismissed(sig, wf_id):
            remaining.append(event)
            continue

        hit_info = cache_service.lookup(sig)
        hit_count = hit_info[1] if hit_info else 1
        results[key] = AutoLabelResult(
            workflow_id=wf_id,
            confidence="high",
            source="cache",
            score=1.0,
            explanation=f"Exact match from {hit_count} previous label{'s' if hit_count != 1 else ''}",
        )

    # --- Tier 2: Embedding similarity for remaining unknowns ---
    if remaining and embedding_service.is_available:
        for event in remaining:
            key = (event.aw_bucket_id, event.aw_event_id)
            sig = event_sigs[key]
            if not sig or sig == "unknown||":
                continue

            matches = embedding_service.query(sig, k=1)
            if not matches:
                continue

            wf_id, similarity = matches[0]
            if cache_service.is_dismissed(sig, wf_id):
                continue

            confidence: Literal["high", "medium"] = (
                "high" if similarity >= EMBEDDING_HIGH_THRESHOLD else "medium"
            )
            results[key] = AutoLabelResult(
                workflow_id=wf_id,
                confidence=confidence,
                source="embedding",
                score=float(similarity),
                explanation=f"Semantically similar to known events ({similarity:.0%} match)",
            )

    high = sum(1 for r in results.values() if r.confidence == "high")
    medium = sum(1 for r in results.values() if r.confidence == "medium")
    logger.debug(
        "Auto-labeled %d/%d events: %d high, %d medium",
        len(results), len(unlabeled), high, medium,
    )
    return results
