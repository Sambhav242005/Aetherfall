import math
from app.ai.rag.embeddings import HashEmbedder


def test_deterministic_and_dim():
    e = HashEmbedder(dim=32)
    a = e.embed(["hello world"])[0]
    b = e.embed(["hello world"])[0]
    assert a == b
    assert len(a) == 32 == e.dim


def test_unit_norm_and_distinct():
    e = HashEmbedder(dim=16)
    v = e.embed(["a"])[0]
    assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-6)
    assert e.embed(["a"]) != e.embed(["completely different text"])
