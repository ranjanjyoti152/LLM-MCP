"""
Embedding engine for semantic vector search.

Supports multiple providers:
  - 'local'    : Zero-dependency TF-IDF hashing (no API keys needed, works offline)
  - 'ollama'   : Local Ollama server (high quality, free, private)
  - 'openai'   : OpenAI text-embedding-3-small (highest quality, requires API key)

The local provider generates 512-dimensional vectors using a deterministic
hash-based approach that captures word co-occurrence patterns. It's not as
good as neural embeddings but works out of the box with zero setup.
"""

import hashlib
import math
import os
import re
from typing import Optional

EMBEDDING_DIM = 512
PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "local")
_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "nomic-embed-text")
_OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")


# ─── Tokenizer ──────────────────────────────────────────────────────────────

_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "shall should may might can could and but or nor for yet so at by from in into "
    "of on to with as it its this that these those i me my we our you your he him "
    "his she her they them their what which who whom".split()
)

def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer with stop-word removal."""
    words = re.findall(r'[a-z0-9]+', text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


# ─── Local Hash Embeddings ──────────────────────────────────────────────────

def _hash_embed(text: str) -> list[float]:
    """Generate a deterministic embedding via feature hashing.

    Uses multiple hash functions to project word unigrams and bigrams
    into a fixed-size vector space. Normalized to unit length.
    """
    tokens = _tokenize(text)
    vec = [0.0] * EMBEDDING_DIM

    # Unigrams
    for token in tokens:
        for seed in (0, 1, 2):
            h = int(hashlib.md5(f"{seed}:{token}".encode()).hexdigest(), 16)
            idx = h % EMBEDDING_DIM
            sign = 1.0 if (h >> 16) % 2 == 0 else -1.0
            vec[idx] += sign

    # Bigrams (capture word order)
    for i in range(len(tokens) - 1):
        bigram = f"{tokens[i]}_{tokens[i+1]}"
        h = int(hashlib.md5(f"bi:{bigram}".encode()).hexdigest(), 16)
        idx = h % EMBEDDING_DIM
        sign = 1.0 if (h >> 16) % 2 == 0 else -1.0
        vec[idx] += sign * 0.5

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


# ─── Remote Embedding Providers ─────────────────────────────────────────────

async def _ollama_embed(text: str) -> list[float]:
    """Get embedding from local Ollama server."""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{_OLLAMA_URL}/api/embeddings",
            json={"model": _OLLAMA_MODEL, "prompt": text},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Ollama returned {resp.status}: {await resp.text()}")
            data = await resp.json()
            return data["embedding"]


async def _openai_embed(text: str) -> list[float]:
    """Get embedding from OpenAI API."""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.openai.com/v1/embeddings",
            json={"model": "text-embedding-3-small", "input": text},
            headers={"Authorization": f"Bearer {_OPENAI_KEY}"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"OpenAI returned {resp.status}: {await resp.text()}")
            data = await resp.json()
            return data["data"][0]["embedding"]


# ─── Public API ──────────────────────────────────────────────────────────────

async def get_embedding(text: str) -> list[float]:
    """Generate an embedding vector for the given text.

    Uses the provider configured via EMBEDDING_PROVIDER env var.
    Falls back to local hash embeddings on any error.
    """
    text = text[:8000]  # Truncate to reasonable length

    if PROVIDER == "ollama":
        try:
            return await _ollama_embed(text)
        except Exception:
            return _hash_embed(text)  # Fallback
    elif PROVIDER == "openai":
        if not _OPENAI_KEY:
            return _hash_embed(text)  # No key, fallback
        try:
            return await _openai_embed(text)
        except Exception:
            return _hash_embed(text)  # Fallback
    else:
        return _hash_embed(text)


async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts."""
    return [await get_embedding(t) for t in texts]


def get_embedding_dim() -> int:
    """Return the dimension of the embedding vector."""
    if PROVIDER == "openai":
        return 1536  # text-embedding-3-small
    elif PROVIDER == "ollama":
        return 768  # nomic-embed-text default
    return EMBEDDING_DIM  # local hash
