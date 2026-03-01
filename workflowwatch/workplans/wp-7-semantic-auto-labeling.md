# WP-7: Semantic Auto-Labeling

> **Goal:** Eliminate "uncategorized" time by automatically labeling events using a tiered approach — from instant lookups to lightweight local embeddings — with zero user configuration and zero cloud dependencies.
>
> **Testable outcome:** Open the timeline for any day. Events that match previously labeled workflows are pre-labeled with a confidence badge. The user sees a "suggested" label on events they never manually tagged, and can accept/dismiss with one click. After a week of normal use, 90%+ of events carry a label without writing any rules.

---

## Architecture Critique & Simplification

The Gemini spec proposes 4 tiers. Here's what we're actually building and why:

### What we keep (Tiers 1 + 2 + 4, simplified)

**Tier 1: Exact-match cache (SQLite lookup table)**
Already partially exists — `workflow_patterns` stores indicator co-occurrences. We extend this into a proper **event signature → workflow_id cache**. When we've seen `(app="Visual Studio Code", title_prefix="baghdad")` labeled as "Coding" 5 times, we cache that mapping. Next time we see it, instant hit. This alone will cover 60-70% of events because people use the same apps repeatedly.

**Tier 2: Embedding similarity (sentence-transformers + FAISS)**
For unknown events — apps/titles we've never seen before — we encode the event signature (app + title + domain) into a vector and find the nearest labeled event. Example: user opens "Zed" for the first time. The embedding of `"zed editor - baghdad/main.py"` is close to `"visual studio code - baghdad/main.py"`, so we suggest "Coding". This requires a one-time ~100MB model download (`all-MiniLM-L6-v2`) and runs in <10ms per query.

**Tier 4 (relabeled as Tier 3): Contextual window (already exists as WP-6)**
The existing `pattern_service.py` block-scoring logic IS Tier 4 — it detects multi-app workflows by co-occurrence. We keep it as-is and layer the new tiers underneath. The block-level context becomes the tiebreaker when Tier 1/2 produce ambiguous per-event labels.

### What we drop

**Tier 3 (batch LLM via Ollama):** Overengineered for this problem. The user's event vocabulary is small — maybe 50-100 distinct (app, title_prefix) combinations. Embeddings handle unknown events well enough. Adding Ollama as a dependency for batch cleanup adds install friction, memory overhead (~4GB), and complexity for marginal accuracy gain. If needed later, it's easy to add as a separate workplan.

### How the tiers compose

```
Event arrives on timeline
  │
  ├─ Tier 1: Cache lookup (event_signature → workflow_id)
  │   Hit? → Return label (confidence: high)
  │
  ├─ Tier 2: Embedding similarity (FAISS nearest-neighbor)
  │   Distance < threshold? → Return label (confidence: medium)
  │
  └─ Tier 3: Block context (existing WP-6 pattern scoring)
      Score ≥ 2? → Return suggestion (confidence: contextual)
```

Each event gets at most one auto-label. The frontend shows confidence level so the user knows which labels are certain vs suggested.

---

## Prerequisites

- WP-1 through WP-6 complete and working.
- Python packages: `sentence-transformers`, `faiss-cpu` (added to requirements.txt).
- ~100MB disk for the embedding model (downloaded on first run, cached locally).

---

## Deliverables

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | Event signature cache table + service | SQLite `label_cache` table mapping normalized event signatures to workflow_id with hit counts |
| 2 | Cache population from existing sessions | On startup / after session creation, populate cache from `session_events` |
| 3 | Embedding index service | Load sentence-transformers model, build FAISS index from cached signatures, query for unknown events |
| 4 | Auto-label pipeline (combines all tiers) | `auto_label_service.py` that runs Tier 1→2→3 for a day's events and returns labels with confidence |
| 5 | API endpoint for auto-labeled timeline | `GET /api/v1/timeline?date=...&auto_label=true` returns events with `suggested_workflow_id` + `confidence` |
| 6 | Frontend: confidence badges + accept/dismiss | Timeline events show suggested labels, one-click accept (creates session), dismiss (skip) |
| 7 | Feedback loop: accepted labels update cache + index | Accepting a suggestion triggers cache + embedding index update |

---

## Tasks

### 1. Event signature normalization

Create `workflowwatch/backend/services/signature_service.py`:

```python
def event_signature(data: dict) -> str:
    """
    Normalize an event into a stable, hashable signature.

    Strategy:
    - app: lowercase, strip version suffixes
    - title: extract meaningful prefix (project name, document title),
             drop dynamic suffixes (line numbers, "- Modified", etc.)
    - domain: lowercase, strip www.

    Returns: "app|title_prefix|domain" string
    """
```

The signature must be stable across sessions — same app+document should produce the same signature even if the full title varies slightly. Use regex to strip noise like line numbers, timestamps, "- Edited", etc.

Key decisions:
- Title prefix length: first 3 meaningful words (skip articles/prepositions) or first path component
- App normalization: map known variants (`Google Chrome` → `chrome`, `Code - OSS` → `vscode`)
- Domain extraction: reuse existing `_domain()` from pattern_service

### 2. Label cache table + service

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS label_cache (
    signature TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    hit_count INTEGER DEFAULT 1,
    last_seen TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_label_cache_workflow ON label_cache(workflow_id);
```

**Service (`cache_service.py`):**
- `populate_from_sessions()`: Scan all `session_events`, compute signatures, insert/update cache. Majority-vote when same signature maps to multiple workflows.
- `lookup(signature) → (workflow_id, hit_count) | None`: Direct lookup.
- `bulk_lookup(signatures) → dict[str, workflow_id]`: Batch lookup for a day's events.
- `record_hit(signature, workflow_id)`: Upsert on accept.
- `invalidate(workflow_id)`: Clear entries for deleted/archived workflow.

Cache population runs:
- Once on startup (if cache is empty)
- After every `create_session` / `delete_session` (incremental)

### 3. Embedding index service

**Service (`embedding_service.py`):**

```python
class EmbeddingService:
    """
    Manages a FAISS index of event signatures for semantic similarity search.
    Uses sentence-transformers all-MiniLM-L6-v2 (384-dim, ~80MB, fast).
    """

    def __init__(self):
        self.model = None       # Lazy-loaded
        self.index = None       # FAISS IndexFlatIP (inner product for cosine)
        self.signatures = []    # Parallel array: index position → signature
        self.sig_to_wf = {}     # signature → workflow_id

    def ensure_loaded(self):
        """Load model + build index from label_cache on first call."""

    def query(self, text: str, k: int = 3) -> list[tuple[str, float]]:
        """
        Find k nearest cached signatures.
        Returns list of (workflow_id, similarity_score).
        """

    def add(self, signature: str, workflow_id: str):
        """Add a new entry to the live index (no rebuild needed with FAISS)."""

    def rebuild(self):
        """Full rebuild from label_cache. Called after bulk changes."""
```

Design choices:
- **Lazy loading**: Model loads on first query, not on startup. Startup stays fast.
- **Index type**: `IndexFlatIP` (exact search with inner product on L2-normalized vectors). For <10K signatures, brute-force is faster than approximate methods and simpler.
- **Similarity threshold**: 0.75 cosine similarity = "medium" confidence. 0.90+ = "high" confidence (nearly identical).
- **Input text**: The same signature string from Tier 1, so the embedding represents `"vscode|baghdad main.py|github.com"`.

### 4. Auto-label pipeline

**Service (`auto_label_service.py`):**

```python
class AutoLabelResult:
    workflow_id: str
    confidence: Literal["high", "medium", "contextual"]
    source: Literal["cache", "embedding", "pattern"]
    score: float           # 0-1 normalized
    explanation: str       # Human-readable: "Matched 5 previous 'Coding' events"

async def auto_label_events(
    events: list[TimelineEvent],
    cache_service: CacheService,
    embedding_service: EmbeddingService,
) -> dict[tuple[str, int], AutoLabelResult]:
    """
    Run the tiered auto-labeling pipeline on a list of timeline events.
    Returns mapping of (bucket_id, event_id) → AutoLabelResult for unlabeled events only.
    """
    results = {}
    unlabeled = [e for e in events if e.session_id is None]

    # Tier 1: Cache lookup (batch)
    signatures = {event_key(e): event_signature(e.data) for e in unlabeled}
    cache_hits = cache_service.bulk_lookup(list(signatures.values()))

    remaining = []
    for event in unlabeled:
        sig = signatures[event_key(event)]
        if sig in cache_hits:
            results[event_key(event)] = AutoLabelResult(
                workflow_id=cache_hits[sig],
                confidence="high",
                source="cache",
                score=1.0,
                explanation=f"Exact match from {cache_hits[sig].hit_count} previous labels"
            )
        else:
            remaining.append(event)

    # Tier 2: Embedding similarity
    for event in remaining:
        sig = signatures[event_key(event)]
        matches = embedding_service.query(sig, k=1)
        if matches and matches[0][1] >= EMBEDDING_THRESHOLD:
            wf_id, sim = matches[0]
            conf = "high" if sim >= 0.90 else "medium"
            results[event_key(event)] = AutoLabelResult(
                workflow_id=wf_id,
                confidence=conf,
                source="embedding",
                score=sim,
                explanation=f"Similar to known '{wf_id}' events ({sim:.0%} match)"
            )

    # Tier 3: Existing pattern scoring fills gaps (already runs via suggestions endpoint)
    # No changes needed — the frontend merges both sources

    return results
```

### 5. API changes

**Extend timeline endpoint:**

`GET /api/v1/timeline?date=2026-03-01&auto_label=true`

Response: same `TimelineEvent[]` but with new optional fields on each event:
```python
class TimelineEvent(BaseModel):
    # ... existing fields ...
    suggested_workflow_id: str | None = None
    suggested_workflow_name: str | None = None
    suggested_workflow_color: str | None = None
    suggestion_confidence: str | None = None   # "high" | "medium" | "contextual"
    suggestion_source: str | None = None       # "cache" | "embedding" | "pattern"
```

**New endpoint for bulk accept:**

`POST /api/v1/auto-label/accept`
```json
{
    "date": "2026-03-01",
    "accepts": [
        {"aw_bucket_id": "...", "aw_event_id": 123, "workflow_id": "uuid"},
        {"aw_bucket_id": "...", "aw_event_id": 124, "workflow_id": "uuid"}
    ]
}
```
Groups accepted events by workflow and creates sessions automatically. Updates cache + index.

**New endpoint for dismiss:**

`POST /api/v1/auto-label/dismiss`
```json
{
    "event_refs": [{"aw_bucket_id": "...", "aw_event_id": 123}],
    "reason": "wrong_workflow"
}
```
Stores negative signal so we don't re-suggest the same thing.

### 6. Frontend changes

**TimelineBar.vue / EventList.vue:**
- Events with `suggested_workflow_id` render with the workflow's color at reduced opacity (e.g., 40%)
- Confidence badge: filled circle (high), half-filled (medium), outline (contextual)
- Hover tooltip: "Auto-labeled as Coding (exact match from 12 events)"
- Click suggested label → accept (turns solid, creates session)
- Click X → dismiss

**New component: `AutoLabelBar.vue`**
- Appears above timeline when auto-labels exist: "23 events auto-labeled. Accept all? [Accept all high-confidence] [Review]"
- "Accept all high-confidence" bulk-accepts everything with confidence=high
- "Review" scrolls to first medium/contextual suggestion

**SuggestionsPanel.vue:**
- Merge auto-label suggestions with existing block-level suggestions
- Auto-labels show per-event; block suggestions show per-block (keep both)

### 7. Feedback loop

When user accepts an auto-label:
1. `POST /api/v1/auto-label/accept` → creates session (reuses session_service)
2. `cache_service.record_hit(signature, workflow_id)` → strengthens cache
3. `embedding_service.add(signature, workflow_id)` → expands index
4. `recompute_patterns()` → updates block-level patterns (existing WP-6 logic)

When user dismisses:
1. Store `(signature, workflow_id, "dismissed")` in a `label_dismissals` table
2. Auto-label pipeline checks dismissals before suggesting
3. If same signature dismissed 2+ times for a workflow → blacklist that combination

---

## Database migrations

```sql
-- label_cache: Tier 1 exact-match store
CREATE TABLE IF NOT EXISTS label_cache (
    signature TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    hit_count INTEGER DEFAULT 1,
    last_seen TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_label_cache_workflow ON label_cache(workflow_id);

-- label_dismissals: negative signals
CREATE TABLE IF NOT EXISTS label_dismissals (
    signature TEXT NOT NULL,
    workflow_id TEXT NOT NULL,
    count INTEGER DEFAULT 1,
    last_dismissed TEXT NOT NULL,
    PRIMARY KEY (signature, workflow_id)
);
```

---

## Performance budget

| Operation | Target | How |
|-----------|--------|-----|
| Tier 1 cache lookup (1 day, ~500 events) | <5ms | SQLite `WHERE signature IN (...)` batch query |
| Tier 2 embedding encode (1 event) | <10ms | MiniLM-L6 on CPU, 384-dim |
| Tier 2 FAISS search (1 query, <10K index) | <1ms | Brute-force inner product |
| Tier 2 full day (~100 uncached events) | <1s | Batch encode + batch search |
| Model load (first query only) | ~2s | Lazy, one-time |
| Total timeline with auto-labels | <2s first load, <200ms subsequent | Cache handles repeat visits |

---

## Implementation order

1. `signature_service.py` — pure functions, easy to test
2. `cache_service.py` + DB migration — Tier 1 working
3. Wire cache into timeline endpoint — immediate value, no ML deps yet
4. `embedding_service.py` + FAISS — Tier 2 working
5. `auto_label_service.py` — pipeline combining tiers
6. API endpoints (auto-label accept/dismiss)
7. Frontend: confidence badges + accept/dismiss UX
8. Frontend: AutoLabelBar bulk actions
9. Feedback loop wiring (accept → update cache + index)

---

## What's explicitly NOT in this workplan

- **Ollama / local LLM**: Dropped. Embeddings handle unknown events. If accuracy is insufficient after real-world testing, add as WP-8.
- **Background daemon / real-time processing**: Events are only labeled when the user opens the timeline for a day. No persistent process watching events in real-time.
- **Category taxonomy**: We don't introduce a fixed category tree ("Productivity > Coding > IDE"). Workflows are user-defined. The auto-labeler maps events to the user's own workflows.
- **Training UI**: No explicit "train the model" flow. The model learns implicitly from every manual label and every accepted suggestion.
