"""
Unit Tests — Redis Client helpers
Test encode/decode embedding payload.
"""
import pytest

from core.redis_client import _decode_embedding_payload, _encode_embedding_payload


class TestEmbeddingPayloadCodec:
    def test_roundtrip_embedding_payload(self):
        embedding = [0.123456789, -0.987654321, 1.23456789]

        encoded = _encode_embedding_payload(embedding)
        decoded = _decode_embedding_payload(encoded)

        assert len(decoded) == len(embedding)
        for actual, expected in zip(decoded, embedding):
            assert actual == pytest.approx(round(expected, 6), abs=1e-6)
