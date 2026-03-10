"""
Vison - FAISS Vector Store
High-performance vector similarity search using Facebook AI Similarity Search.
"""

import logging
import threading
import numpy as np
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    """
    FAISS-based vector store with separate indices per media type.
    Uses Inner Product on L2-normalized vectors, equivalent to cosine similarity.
    """

    def __init__(self):
        self._indices = {}       # media_type -> faiss.Index
        self._id_maps = {}       # media_type -> list[int] (maps faiss internal idx -> item id)
        self._lock = threading.Lock()
        self._initialized = False

    def initialize(self):
        """Initialize FAISS indices for each media type."""
        try:
            import faiss

            dimensions = {
                "image": settings.IMAGE_FEATURE_DIM,
                "audio": settings.AUDIO_FEATURE_DIM,
                "video": settings.VIDEO_FEATURE_DIM,
                "text": settings.TEXT_FEATURE_DIM,
            }

            for media_type, dim in dimensions.items():
                index_path = settings.INDEX_DIR / f"{media_type}.index"
                id_map_path = settings.INDEX_DIR / f"{media_type}_ids.npy"

                if index_path.exists() and id_map_path.exists():
                    # Load existing index
                    self._indices[media_type] = faiss.read_index(str(index_path))
                    self._id_maps[media_type] = np.load(str(id_map_path)).tolist()
                    logger.info(
                        f"✓ Loaded {media_type} index: {self._indices[media_type].ntotal} vectors"
                    )
                else:
                    # Create new index (Inner Product for cosine similarity on normalized vectors)
                    self._indices[media_type] = faiss.IndexFlatIP(dim)
                    self._id_maps[media_type] = []
                    logger.info(f"✓ Created new {media_type} index (dim={dim})")

            self._initialized = True
            logger.info("✓ Vector store initialized")

        except ImportError:
            logger.warning("FAISS not available — using numpy fallback for similarity search")
            self._use_numpy_fallback()

    def _use_numpy_fallback(self):
        """Fallback when FAISS is not installed: use numpy arrays + brute-force search."""
        dimensions = {
            "image": settings.IMAGE_FEATURE_DIM,
            "audio": settings.AUDIO_FEATURE_DIM,
            "video": settings.VIDEO_FEATURE_DIM,
            "text": settings.TEXT_FEATURE_DIM,
        }
        for media_type, dim in dimensions.items():
            self._indices[media_type] = {
                "vectors": np.empty((0, dim), dtype=np.float32),
                "type": "numpy",
                "dim": dim,
            }
            self._id_maps[media_type] = []
        self._initialized = True
        logger.info("✓ Vector store initialized (NumPy fallback)")

    def add(self, media_type: str, item_id: int, features: np.ndarray) -> bool:
        """
        Add a feature vector to the index.

        Args:
            media_type: One of 'image', 'audio', 'video', 'text'
            item_id:    Database ID of the item
            features:   Normalized feature vector
        """
        if media_type not in self._indices:
            logger.error(f"Unknown media type: {media_type}")
            return False

        with self._lock:
            try:
                vec = features.reshape(1, -1).astype(np.float32)
                index = self._indices[media_type]

                if isinstance(index, dict) and index.get("type") == "numpy":
                    # NumPy fallback
                    expected_dim = index["dim"]
                    if vec.shape[1] != expected_dim:
                        vec_padded = np.zeros((1, expected_dim), dtype=np.float32)
                        vec_padded[0, : vec.shape[1]] = vec[0, : expected_dim]
                        vec = vec_padded
                    index["vectors"] = np.vstack([index["vectors"], vec])
                else:
                    # FAISS
                    index.add(vec)

                self._id_maps[media_type].append(item_id)
                return True

            except Exception as e:
                logger.error(f"Failed to add vector: {e}")
                return False

    def search(
        self, media_type: str, query_vector: np.ndarray, top_k: int = None
    ) -> list[tuple[int, float]]:
        """
        Search for similar vectors in the index.

        Args:
            media_type:   Which index to search
            query_vector: Query feature vector
            top_k:        Number of results to return

        Returns:
            List of (item_id, similarity_score) tuples, sorted by score descending
        """
        if top_k is None:
            top_k = settings.DEFAULT_TOP_K

        if media_type not in self._indices:
            return []

        with self._lock:
            try:
                index = self._indices[media_type]
                id_map = self._id_maps[media_type]

                n_items = (
                    index["vectors"].shape[0]
                    if isinstance(index, dict)
                    else index.ntotal
                )

                if n_items == 0:
                    return []

                query = query_vector.reshape(1, -1).astype(np.float32)
                top_k = min(top_k, n_items)

                if isinstance(index, dict) and index.get("type") == "numpy":
                    # NumPy brute-force search (cosine similarity via dot product)
                    similarities = np.dot(index["vectors"], query.T).flatten()
                    top_indices = np.argsort(similarities)[-top_k:][::-1]
                    results = [
                        (id_map[i], float(similarities[i]))
                        for i in top_indices
                        if similarities[i] >= settings.SIMILARITY_THRESHOLD
                    ]
                else:
                    # FAISS search
                    scores, indices = index.search(query, top_k)
                    results = [
                        (id_map[idx], float(score))
                        for score, idx in zip(scores[0], indices[0])
                        if idx >= 0 and score >= settings.SIMILARITY_THRESHOLD
                    ]

                return results

            except Exception as e:
                logger.error(f"Search failed: {e}")
                return []

    def remove(self, media_type: str, item_id: int) -> bool:
        """Remove a vector from the index by item ID. Note: FAISS doesn't support deletion natively."""
        if media_type not in self._id_maps:
            return False

        with self._lock:
            try:
                if item_id in self._id_maps[media_type]:
                    idx = self._id_maps[media_type].index(item_id)
                    self._id_maps[media_type].pop(idx)

                    index = self._indices[media_type]
                    if isinstance(index, dict) and index.get("type") == "numpy":
                        vectors = index["vectors"]
                        index["vectors"] = np.delete(vectors, idx, axis=0)
                    else:
                        # For FAISS, we need to rebuild the index without the removed vector
                        self._rebuild_faiss_index(media_type, idx)

                    return True
                return False
            except Exception as e:
                logger.error(f"Remove failed: {e}")
                return False

    def _rebuild_faiss_index(self, media_type: str, remove_idx: int):
        """Rebuild a FAISS index after removing a vector."""
        try:
            import faiss

            old_index = self._indices[media_type]
            dim = old_index.d
            n = old_index.ntotal

            if n <= 1:
                self._indices[media_type] = faiss.IndexFlatIP(dim)
                return

            # Reconstruct all vectors
            all_vectors = np.zeros((n, dim), dtype=np.float32)
            for i in range(n):
                all_vectors[i] = old_index.reconstruct(i)

            # Remove the target vector
            all_vectors = np.delete(all_vectors, remove_idx, axis=0)

            # Build new index
            new_index = faiss.IndexFlatIP(dim)
            new_index.add(all_vectors)
            self._indices[media_type] = new_index

        except Exception as e:
            logger.error(f"Index rebuild failed: {e}")

    def save(self):
        """Persist all indices to disk."""
        with self._lock:
            try:
                import faiss

                for media_type, index in self._indices.items():
                    if isinstance(index, dict):
                        # NumPy fallback
                        np.save(
                            str(settings.INDEX_DIR / f"{media_type}_vectors.npy"),
                            index["vectors"],
                        )
                    else:
                        faiss.write_index(
                            index,
                            str(settings.INDEX_DIR / f"{media_type}.index"),
                        )
                    np.save(
                        str(settings.INDEX_DIR / f"{media_type}_ids.npy"),
                        np.array(self._id_maps[media_type]),
                    )

                logger.info("✓ Vector store saved to disk")
            except Exception as e:
                logger.error(f"Save failed: {e}")

    def get_stats(self) -> dict:
        """Get statistics about the vector store."""
        stats = {}
        for media_type in ["image", "audio", "video", "text"]:
            if media_type in self._indices:
                index = self._indices[media_type]
                count = (
                    index["vectors"].shape[0]
                    if isinstance(index, dict)
                    else index.ntotal
                )
                stats[media_type] = {"count": count}
        return stats


# Singleton instance
vector_store = VectorStore()
