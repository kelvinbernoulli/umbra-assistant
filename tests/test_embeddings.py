import asyncio
import math

import pytest

from app.services.embeddings.hf_embedder import (
    DeterministicFakeEmbedder,
    embed_batch,
    settings,
)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def test_fake_embeddings_are_stable_normalized_and_nonzero():
    first_embedder = DeterministicFakeEmbedder(embedding_dim=128)
    second_embedder = DeterministicFakeEmbedder(embedding_dim=128)
    texts = [
        "Hello, WORLD!",
        "",
        "  \t\n",
        "Café déjà vu 東京 🚀",
        "Hello, WORLD!",
    ]

    first = first_embedder.embed(texts)
    second = second_embedder.embed(texts)

    assert first == second
    assert first[0] == first_embedder.embed(["hello world"])[0]
    assert first[0] == first[4]
    assert first[1] == first[2]
    assert first[3] != first[1]
    assert first_embedder.embed([]) == []
    assert first == [first_embedder.embed([text])[0] for text in texts]

    for vector in first:
        assert len(vector) == 128
        assert all(math.isfinite(value) for value in vector)
        assert math.sqrt(sum(value * value for value in vector)) == pytest.approx(1.0)
        assert any(value != 0 for value in vector)

    assert first_embedder.embed(["Café"])[0] == first_embedder.embed(["Cafe\u0301"])[0]


def test_fake_embeddings_reward_shared_words():
    embedder = DeterministicFakeEmbedder(embedding_dim=256)
    base, related, unrelated = embedder.embed(
        [
            "project alpha planning meeting tomorrow",
            "project alpha meeting notes",
            "banana telescope ocean violin",
        ]
    )

    assert _cosine_similarity(base, related) > _cosine_similarity(base, unrelated)


def test_embed_batch_uses_the_deterministic_fake_without_a_token(monkeypatch):
    monkeypatch.setattr(settings, "HUGGINGFACE_API_TOKEN", None)

    first = asyncio.run(embed_batch(["repeatable search text", "second item"]))
    second = asyncio.run(embed_batch(["repeatable search text", "second item"]))

    assert first == second


def test_fake_embedder_rejects_invalid_dimensions():
    with pytest.raises(ValueError, match="greater than zero"):
        DeterministicFakeEmbedder(embedding_dim=0)
