import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

from uranus_research_knowledge.app import create_app
from uranus_research_knowledge.clients import Clients, UpstreamError
from uranus_research_knowledge.config import Settings
from uranus_research_knowledge.evidence import answer
from uranus_research_knowledge.extraction import Snapshot, extract
from uranus_research_knowledge.indexer import plan, reconcile
from uranus_research_knowledge.models import EMBEDDING_VERSION, AnswerRequest, Assertion, Chunk
from uranus_research_knowledge.registry import REGISTRY, Source, safe_path, safe_text
from uranus_research_knowledge.vocabulary import NodeType, edge_id, node_uri

NOW = datetime(2026, 10, 1, tzinfo=UTC)
REPO = "sndcds/uranus-admin"
SHA = "a" * 40
QUOTE = "This repository implements semantic search."


@pytest.fixture
def snapshot(monkeypatch):
    monkeypatch.setitem(
        REGISTRY,
        REPO,
        Source(
            paths=("README.md", "docs/design.md", "src/service.py"),
            assertions={
                "README.md": (
                    Assertion(fact="semantic_search_repository", value=REPO, quote=QUOTE),
                )
            },
        ),
    )
    return Snapshot(
        repository=REPO,
        commit_sha=SHA,
        public_verified_from=f"https://api.github.com/repos/{REPO}",
        complete=True,
        files={
            "README.md": "# Research\n\n" + QUOTE + "\n",
            "docs/design.md": "# Model\n\nQdrant retrieves candidates.\n",
            "src/service.py": (
                '"""Service docs."""\nclass Search:\n    def query(self):\n        return []\n'
            ),
        },
    )


@pytest.fixture
def settings():
    return Settings(api_key="k" * 32, encoder_api_key="e" * 32, qdrant_api_key="q" * 32)


def payloads(chunks):
    return {c.point_id: c.model_dump(mode="json") for c in chunks}


def test_extraction_and_graph(snapshot):
    chunks = extract(snapshot, NOW)
    assert chunks == extract(snapshot, NOW)
    assert len({c.point_id for c in chunks}) == len(chunks)
    assert any(c.symbol == "Search.query" for c in chunks)
    assert all(c.graph_edge_ids for c in chunks)
    for c in chunks:
        text = snapshot.files[c.path]
        assert c.chunk_text in "".join(
            text.splitlines(keepends=True)[c.line_start - 1 : c.line_end]
        )
        assert f"/blob/{SHA}/" in c.source_url
    assert edge_id(node_uri(NodeType.service, "encoder"), "uses", node_uri(NodeType.model, "jina"))
    with pytest.raises(ValueError):
        edge_id(node_uri(NodeType.service, "encoder"), "invented", node_uri(NodeType.model, "jina"))


def test_reconcile_categories(snapshot):
    first = extract(snapshot, NOW)
    old = payloads(first)
    same = extract(snapshot, NOW + timedelta(days=1))
    diff = plan(same, old, repository=REPO, complete=True)
    assert len(diff.unchanged) == len(first)
    revision = snapshot.model_copy(update={"commit_sha": "b" * 40})
    new = extract(revision, NOW)
    diff = plan(new, old, repository=REPO, complete=True)
    assert len(diff.metadata_updated) == len(first)
    assert not diff.updated and not diff.new
    changed = snapshot.model_copy(
        update={"files": {**snapshot.files, "README.md": "# Research\n\nDifferent prose.\n"}}
    )
    diff = plan(extract(changed, NOW), old, repository=REPO, complete=True)
    assert len(diff.updated) == 1
    assert plan([], old, repository=REPO, complete=True).deleted == sorted(old)
    assert not plan([], old, repository=REPO, complete=False).deleted
    partial = snapshot.model_copy(
        update={"complete": False, "files": {"README.md": snapshot.files["README.md"]}}
    )
    assert not plan(extract(partial, NOW), old, repository=REPO, complete=False).deleted


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "docs/.env.local",
        "docs/credentials.json",
        "../README.md",
        "/README.md",
        "secrets.yaml",
        "key.pem",
        "docs/accounts.csv",
    ],
)
def test_forbidden_paths(path):
    assert not safe_path(path)


@pytest.mark.parametrize(
    "text",
    [
        "PRIVATE " + "-----BEGIN RSA PRIVATE KEY-----",
        "person@example.org",
        "api_key='abcdefghijklmnopqrstuv'",
        "ghp_" + "a" * 36,
    ],
)
def test_secret_text_excluded(snapshot, text):
    assert not safe_text(text)
    snapshot = snapshot.model_copy(update={"files": {"README.md": text}})
    assert extract(snapshot, NOW) == []


def test_manifest_rejects_unreviewed_and_incomplete(snapshot):
    for update in (
        {"files": {"secret.txt": "hello"}},
        {"files": {"README.md": "hello"}},
        {"repository": "private/repo"},
    ):
        with pytest.raises(ValidationError):
            Snapshot.model_validate({**snapshot.model_dump(), **update})


def test_forged_provenance(snapshot):
    chunk = next(c for c in extract(snapshot, NOW) if c.assertions)
    for update in (
        {"source_url": "https://evil.example"},
        {"content_hash": "0" * 64},
        {"assertions": [Assertion(fact="founding_date", value="2000", quote=QUOTE)]},
    ):
        with pytest.raises(ValidationError):
            Chunk.model_validate({**chunk.model_dump(), **update})


class Fake:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    async def search(self, query, limit):
        return [(0.9, c) for c in self.chunks[:limit]]

    async def embed(self, texts, kind):
        self.calls.append(("embed", texts))
        return [[1.0] + [0.0] * 1023 for _ in texts]

    async def qdrant(self, method, path, body):
        self.calls.append((path, body))

    async def close(self):
        pass

    async def check_collection(self):
        pass


async def test_supported_and_unknown_founding(snapshot):
    client = Fake(extract(snapshot, NOW))
    supported = await answer(
        client, AnswerRequest(query="Semantic search?", fact="semantic_search_repository")
    )
    assert supported.supported and supported.facts[0].value == REPO
    unsupported = await answer(
        client, AnswerRequest(query="Wann wurde Kulturbytes gegründet?", fact="founding_date")
    )
    assert not unsupported.supported and not unsupported.facts and unsupported.evidence
    assert unsupported.indexed_commits == {REPO: [SHA]}


async def test_metadata_does_not_embed_and_delete_last(snapshot):
    chunks = extract(snapshot, NOW)
    client = Fake(chunks)
    diff = plan(
        extract(snapshot.model_copy(update={"commit_sha": "b" * 40}), NOW),
        payloads(chunks),
        repository=REPO,
        complete=True,
    )
    await reconcile(
        client, extract(snapshot.model_copy(update={"commit_sha": "b" * 40}), NOW), diff
    )
    assert all(c[0] == "/points/payload?wait=true" for c in client.calls)
    client.calls.clear()
    diff = plan(chunks[:1], payloads(chunks[1:]), repository=REPO, complete=True)
    await reconcile(client, chunks[:1], diff)
    assert client.calls[-1][0] == "/points/delete?wait=true"


async def test_failed_write_never_deletes(snapshot):
    chunks = extract(snapshot, NOW)
    client = Fake(chunks)

    async def fail(*args):
        raise UpstreamError()

    client.embed = fail
    diff = plan(chunks[:1], payloads(chunks[1:]), repository=REPO, complete=True)
    with pytest.raises(UpstreamError):
        await reconcile(client, chunks[:1], diff)
    assert not client.calls


async def test_api_auth_bounds_and_no_selectors(snapshot, settings):
    app = create_app(settings, Fake(extract(snapshot, NOW)))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        assert (await client.post("/query", json={"query": "test"})).status_code == 401
        headers = {"Authorization": "Bearer " + "k" * 32}
        for body in (
            {"query": "test", "collection": "other"},
            {"query": "test", "limit": 21},
            {"query": " "},
        ):
            assert (await client.post("/query", json=body, headers=headers)).status_code == 422
        assert (
            await client.post("/query", content=b"x" * 17000, headers=headers)
        ).status_code == 413
        result = await client.post(
            "/evidence-answer", json={"query": "founded?", "fact": "founding_date"}, headers=headers
        )
        assert result.status_code == 200 and result.json()["supported"] is False
        assert "access-control-allow-origin" not in result.headers


async def test_encoder_contract_and_fixed_requests(settings, snapshot):
    chunks = extract(snapshot, NOW)
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/embed":
            assert json.loads(request.content)["kind"] == "query"
            return httpx.Response(
                200,
                json={"embedding_version": EMBEDDING_VERSION, "vectors": [[1.0] + [0.0] * 1023]},
            )
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "result": {
                    "points": [
                        {
                            "id": chunks[0].point_id,
                            "score": 0.5,
                            "payload": chunks[0].model_dump(mode="json"),
                        }
                    ]
                },
            },
        )

    client = Clients(settings, httpx.MockTransport(handler))
    assert len(await client.search("test", 10)) == 1
    assert "kulturbytes_project_knowledge_jina_v3_v1" in calls[-1].url.path
    assert calls[-1].headers.get("authorization") is None
    await client.close()


@pytest.mark.parametrize("vectors", [[], [[float("nan")] * 1024], [[0.0] * 1024], [[1.0] * 3]])
async def test_bad_encoder_vectors(settings, vectors):
    client = Clients(
        settings,
        httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                content=json.dumps({"embedding_version": EMBEDDING_VERSION, "vectors": vectors}),
                headers={"content-type": "application/json"},
            )
        ),
    )
    with pytest.raises(UpstreamError):
        await client.embed(["text"], "passage")
    await client.close()


async def test_moved_unchanged_text_reuses_vector(snapshot):
    chunks = extract(snapshot, NOW)
    moved = extract(
        snapshot.model_copy(
            update={"files": {**snapshot.files, "README.md": "# Renamed\n\n" + QUOTE + "\n"}}
        ),
        NOW,
    )
    client = Fake(moved)

    async def vector(identity):
        return [1.0] + [0.0] * 1023

    client.vector = vector
    diff = plan(moved, payloads(chunks), repository=REPO, complete=True)
    await reconcile(client, moved, diff, payloads(chunks))
    embedded = [text for kind, texts in client.calls if kind == "embed" for text in texts]
    assert embedded == ["# Renamed\n\n"]


def test_default_registry_semantic_assertion_is_source_code():
    source = REGISTRY[REPO]
    assert any(
        a.fact == "semantic_search_repository"
        for a in source.assertions["backend/app/services/semantic_search.py"]
    )
