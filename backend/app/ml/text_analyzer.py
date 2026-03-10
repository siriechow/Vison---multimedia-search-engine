"""
Vison - NLP Text Analyzer Module
Text processing and analysis for search queries and crawled content.
"""

import logging
import re
import numpy as np
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-loaded vectorizer
_tfidf_vectorizer = None
_is_fitted = False


def _get_vectorizer():
    """Get or create the TF-IDF vectorizer."""
    global _tfidf_vectorizer
    if _tfidf_vectorizer is None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        _tfidf_vectorizer = TfidfVectorizer(
            max_features=settings.TEXT_FEATURE_DIM,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95,
            sublinear_tf=True,
        )
    return _tfidf_vectorizer


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove URLs
    text = re.sub(r"https?://\S+", " ", text)
    # Remove special characters but keep basic punctuation
    text = re.sub(r"[^\w\s.,!?-]", " ", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def extract_keywords(text: str, top_n: int = 20) -> list[str]:
    """Extract the most relevant keywords from text using TF-IDF scoring."""
    text = clean_text(text)
    if not text or len(text.split()) < 3:
        return text.split() if text else []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        # Use a local vectorizer for keyword extraction
        vec = TfidfVectorizer(
            max_features=500,
            stop_words="english",
            ngram_range=(1, 2),
        )
        tfidf_matrix = vec.fit_transform([text])
        feature_names = vec.get_feature_names_out()
        scores = tfidf_matrix.toarray().flatten()

        # Sort by score, return top_n
        top_indices = scores.argsort()[-top_n:][::-1]
        keywords = [feature_names[i] for i in top_indices if scores[i] > 0]
        return keywords

    except Exception as e:
        logger.warning(f"Keyword extraction failed: {e}")
        # Fallback: simple word frequency
        words = text.split()
        from collections import Counter
        freq = Counter(words)
        return [w for w, _ in freq.most_common(top_n)]


def extract_text_features(text: str) -> np.ndarray | None:
    """
    Convert text to a feature vector using TF-IDF.

    Args:
        text: Input text string

    Returns:
        Normalized feature vector of dimension TEXT_FEATURE_DIM, or None
    """
    global _is_fitted
    text = clean_text(text)
    if not text:
        return None

    try:
        vectorizer = _get_vectorizer()

        if not _is_fitted:
            # First time: fit and transform
            features = vectorizer.fit_transform([text]).toarray().flatten()
            _is_fitted = True
        else:
            features = vectorizer.transform([text]).toarray().flatten()

        # Pad to target dimension if needed
        target_dim = settings.TEXT_FEATURE_DIM
        if len(features) < target_dim:
            features = np.pad(features, (0, target_dim - len(features)))
        else:
            features = features[:target_dim]

        # Normalize
        norm = np.linalg.norm(features)
        if norm > 0:
            features = features / norm

        return features.astype(np.float32)

    except Exception as e:
        logger.error(f"Text feature extraction failed: {e}")
        return None


def compute_text_similarity(query: str, documents: list[str]) -> list[float]:
    """
    Compute similarity between a query and a list of documents.

    Returns:
        List of similarity scores (0-1) for each document
    """
    if not query or not documents:
        return []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        all_texts = [clean_text(query)] + [clean_text(d) for d in documents]
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        tfidf_matrix = vec.fit_transform(all_texts)

        # Compute cosine similarity between query and each document
        query_vec = tfidf_matrix[0:1]
        doc_vecs = tfidf_matrix[1:]
        similarities = cosine_similarity(query_vec, doc_vecs).flatten()

        return similarities.tolist()

    except Exception as e:
        logger.error(f"Text similarity computation failed: {e}")
        return [0.0] * len(documents)
