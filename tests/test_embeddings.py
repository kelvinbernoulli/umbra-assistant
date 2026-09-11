import asyncio
from unittest.mock import Mock

import pytest

from app.services.embeddings import hf_embedder
from app.services.vectorstore.pinecone_client import PineconeClient
from app.core.exceptions import VectorStoreError


def test_embeddings_use_model_without_token(monkeypatch):
    monkeypatch.setattr(hf_embedder.settings, "HUGGINGFACE_API_TOKEN", None)
    model = Mock()
    model.embed_documents.return_value = [[0.1, 0.2]]
    factory = Mock(return_value=model)
    monkeypatch.setattr(hf_embedder, "HuggingFaceEmbeddings", factory)
    assert asyncio.run(hf_embedder.embed_batch(["hello"])) == [[0.1, 0.2]]
    model.embed_documents.assert_called_once_with(["hello"])
    factory.assert_called_once()


@pytest.mark.parametrize("initialization_failure", [True, False])
def test_embedding_failures_do_not_return_synthetic_vectors(monkeypatch, initialization_failure):
    model = Mock()
    factory = Mock(return_value=model)
    if initialization_failure:
        factory.side_effect = RuntimeError("model unavailable")
    else:
        model.embed_documents.side_effect = RuntimeError("model unavailable")
    monkeypatch.setattr(hf_embedder, "HuggingFaceEmbeddings", factory)
    with pytest.raises(RuntimeError, match="model unavailable"):
        asyncio.run(hf_embedder.embed_batch(["hello"]))


def test_vectorstore_requires_credentials(monkeypatch):
    monkeypatch.setattr(PineconeClient, "_instance", None)
    monkeypatch.setattr(hf_embedder.settings, "PINECONE_API_KEY", None)
    with pytest.raises(VectorStoreError, match="PINECONE_API_KEY is required"):
        PineconeClient.get_index()
    assert PineconeClient._instance is None


@pytest.mark.parametrize("route", ["brief", "commands"])
def test_unimplemented_endpoints_do_not_return_placeholder_success(route):
    from fastapi import HTTPException
    from app.api.v1.routes.brief import get_today_brief
    from app.api.v1.routes.commands import CommandRequest, submit_command

    with pytest.raises(HTTPException) as exc:
        if route == "brief":
            asyncio.run(get_today_brief())
        else:
            asyncio.run(submit_command(CommandRequest(text="hello")))
    assert exc.value.status_code == 501
