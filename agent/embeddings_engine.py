import math
import re
from collections import Counter
from typing import List, Dict, Any, Tuple

def tokenize(text: str) -> List[str]:
    """Tokenizes text into normalized alphanumeric words."""
    if not text:
        return []
    # Strip HTML tags
    cleaned = re.sub(r'<[^>]+>', ' ', text)
    tokens = re.findall(r'\b[a-zA-Z0-9_\+\#\.\-]{2,}\b', cleaned.lower())
    # Normalize common tech terms (e.g. c++, node.js)
    return [t.strip('.') for t in tokens if len(t.strip('.')) > 1]

def get_character_ngrams(word: str, n: int = 3) -> List[str]:
    """Generates character n-grams for fuzzy subword matching."""
    padded = f"^{word}$"
    return [padded[i:i+n] for i in range(len(padded) - n + 1)]

class LocalSemanticEngine:
    """
    Lightweight, ultra-fast BM25 & subword TF-IDF vector retrieval engine
    designed for ranking resume vault entries against job descriptions with zero dependencies.
    """
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def rank_items(
        self,
        query: str,
        items: List[Dict[str, Any]],
        text_extractor = None,
        top_k: int = 5
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Ranks a list of vault items against a query string.
        text_extractor: function(item) -> str that converts item into searchable text corpus.
        """
        if not items:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return [(item, 0.0) for item in items[:top_k]]

        # Default extractor merges title, context, bullets, tags, role, company
        if text_extractor is None:
            def default_extractor(it: Dict[str, Any]) -> str:
                parts = []
                for k in ["title", "role", "company", "context", "category"]:
                    if it.get(k):
                        parts.append(str(it[k]))
                if "tags" in it and isinstance(it["tags"], list):
                    parts.extend(it["tags"])
                if "bullets" in it and isinstance(it["bullets"], list):
                    parts.extend(it["bullets"])
                if "points_tier" in it and isinstance(it["points_tier"], dict):
                    for tier_bullets in it["points_tier"].values():
                        if isinstance(tier_bullets, list):
                            parts.extend(tier_bullets)
                return " ".join(parts)
            text_extractor = default_extractor

        # Build corpus
        docs = [tokenize(text_extractor(it)) for it in items]
        N = len(docs)
        if N == 0:
            return []

        avg_doc_len = sum(len(d) for d in docs) / float(N) if N > 0 else 1.0

        # Calculate Document Frequencies (DF)
        df = Counter()
        for doc in docs:
            unique_words = set(doc)
            for w in unique_words:
                df[w] += 1

        # Calculate BM25 scores
        scored_items = []
        for idx, item in enumerate(items):
            doc = docs[idx]
            doc_len = len(doc)
            tf = Counter(doc)
            score = 0.0

            for q_term in query_tokens:
                if q_term in tf:
                    doc_freq = df.get(q_term, 0)
                    # Robertson-Spärck Jones IDF
                    idf = math.log(1.0 + (N - doc_freq + 0.5) / (doc_freq + 0.5))
                    term_tf = tf[q_term]
                    denom = term_tf + self.k1 * (1.0 - self.b + self.b * (doc_len / (avg_doc_len or 1.0)))
                    score += idf * ((term_tf * (self.k1 + 1.0)) / (denom or 1.0))

            # Bonus for exact tag matches
            item_tags = [t.lower() for t in item.get("tags", [])]
            for q_term in query_tokens:
                if q_term in item_tags:
                    score += 1.5

            scored_items.append((item, score))

        # Sort by score descending
        scored_items.sort(key=lambda x: x[1], reverse=True)
        return scored_items[:top_k]

semantic_engine = LocalSemanticEngine()
