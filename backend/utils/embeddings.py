from __future__ import annotations

import hashlib
import math
from typing import Iterable


def get_embeddings(texts: Iterable[str], settings=None) -> list[list[float]]:
    return [_hash_embedding(text or "") for text in texts]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _hash_embedding(text: str, dims: int = 16) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
    values: list[float] = []
    for index in range(dims):
        start = (index * 2) % len(digest)
        chunk = digest[start:start + 2]
        if len(chunk) < 2:
            chunk = (chunk + digest)[:2]
        raw = int.from_bytes(chunk, "big")
        values.append((raw / 65535.0) * 2.0 - 1.0)
    return values
