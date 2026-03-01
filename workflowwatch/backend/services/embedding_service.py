"""
Embedding-based similarity service (WP-7 Tier 2).
Uses sentence-transformers + FAISS to find semantically similar labeled events.
Lazy-loads model on first query. Degrades gracefully if dependencies not installed.
"""

import logging

logger = logging.getLogger(__name__)

# Cosine similarity thresholds
EMBEDDING_HIGH_THRESHOLD = 0.90
EMBEDDING_MEDIUM_THRESHOLD = 0.75


class EmbeddingService:
    """
    FAISS index of event signatures for semantic nearest-neighbor search.

    Model: all-MiniLM-L6-v2 (384-dim vectors, ~80MB, CPU-fast)
    Index type: IndexFlatIP (exact brute-force inner product on L2-normalized vecs = cosine)

    For <10K distinct signatures, brute-force is faster than ANN and needs no tuning.
    """

    def __init__(self) -> None:
        self._model = None
        self._index = None
        self._signatures: list[str] = []      # parallel array: position → signature string
        self._sig_to_wf: dict[str, str] = {}  # signature → workflow_id
        self._available: bool | None = None    # None = not yet checked

    @property
    def is_available(self) -> bool:
        if self._available is None:
            self._available = self._try_load()
        return self._available

    def _try_load(self) -> bool:
        """Attempt to load model + build index. Returns True on success."""
        try:
            import faiss  # noqa: F401
            from sentence_transformers import SentenceTransformer  # noqa: F401
        except ImportError:
            logger.warning(
                "sentence-transformers or faiss-cpu not installed — "
                "embedding auto-labeling disabled. "
                "Install: pip install sentence-transformers faiss-cpu"
            )
            return False
        try:
            logger.info("Loading embedding model all-MiniLM-L6-v2…")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            self._rebuild_index()
            logger.info(
                "Embedding service ready. Index size: %d signatures", len(self._signatures)
            )
            return True
        except Exception as exc:
            logger.warning("Embedding model failed to load: %s", exc)
            return False

    def _rebuild_index(self) -> None:
        """Build (or rebuild) FAISS index from the label_cache table."""
        import faiss
        import numpy as np
        from ..database import get_db

        db = get_db()
        rows = db.execute("SELECT signature, workflow_id FROM label_cache").fetchall()

        if not rows:
            self._signatures = []
            self._sig_to_wf = {}
            self._index = None
            return

        self._signatures = [r["signature"] for r in rows]
        self._sig_to_wf = {r["signature"]: r["workflow_id"] for r in rows}

        embeddings = self._model.encode(
            self._signatures,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=64,
        )
        arr = np.array(embeddings, dtype="float32")
        dim = arr.shape[1]
        self._index = faiss.IndexFlatIP(dim)
        self._index.add(arr)

    def query(self, text: str, k: int = 3) -> list[tuple[str, float]]:
        """
        Find the k most similar cached signatures to `text`.
        Returns list of (workflow_id, cosine_similarity) above EMBEDDING_MEDIUM_THRESHOLD.
        """
        if not self.is_available or self._index is None or not self._signatures:
            return []
        try:
            import numpy as np
            vec = self._model.encode(
                [text], normalize_embeddings=True, show_progress_bar=False
            )
            arr = np.array(vec, dtype="float32")
            k_actual = min(k, len(self._signatures))
            scores, indices = self._index.search(arr, k_actual)

            results: list[tuple[str, float]] = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0:
                    continue
                sim = float(score)
                if sim < EMBEDDING_MEDIUM_THRESHOLD:
                    continue
                sig = self._signatures[int(idx)]
                wf_id = self._sig_to_wf.get(sig)
                if wf_id:
                    results.append((wf_id, sim))
            return results
        except Exception as exc:
            logger.warning("Embedding query failed: %s", exc)
            return []

    def add(self, signature: str, workflow_id: str) -> None:
        """Add a single new signature to the live index (no full rebuild needed)."""
        if not self.is_available:
            return
        if signature in self._sig_to_wf:
            # Update mapping only — vector already in index (or close enough)
            self._sig_to_wf[signature] = workflow_id
            return
        try:
            import numpy as np
            if self._index is None:
                self._rebuild_index()
                return
            vec = self._model.encode(
                [signature], normalize_embeddings=True, show_progress_bar=False
            )
            arr = np.array(vec, dtype="float32")
            self._index.add(arr)
            self._signatures.append(signature)
            self._sig_to_wf[signature] = workflow_id
        except Exception as exc:
            logger.warning("Failed to add signature to embedding index: %s", exc)

    def rebuild(self) -> None:
        """Force full index rebuild from label_cache (call after bulk changes)."""
        if self._available:
            self._rebuild_index()
            logger.info("Embedding index rebuilt. Size: %d", len(self._signatures))
