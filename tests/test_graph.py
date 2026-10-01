import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import get_args

import httpx
import pytest
from pydantic import ValidationError

from uranus_research_knowledge.app import create_app
from uranus_research_knowledge.clients import Clients, UpstreamError
from uranus_research_knowledge.config import Settings
from uranus_research_knowledge.evidence import answer, public_evidence
from uranus_research_knowledge.extraction import Snapshot, extract
from uranus_research_knowledge.graph import export_jsonld, graph_query, materialize
from uranus_research_knowledge.indexer import plan, reconcile
from uranus_research_knowledge.models import (
    AnswerRequest,
    Assertion,
    Chunk,
    FactKey,
    GraphAssertion,
    GraphEdge,
    GraphNode,
    GraphQueryRequest,
    GraphQueryResponse,
)
from uranus_research_knowledge.registry import REGISTRY, Source
from uranus_research_knowledge.vocabulary import (
    BASE,
    RELATIONS,
    NodeType,
    Relation,
    edge_id,
    node_uri,
)

NOW = datetime(2026, 10, 1, tzinfo=UTC)
REPO = "sndcds/uranus-admin"
SHA = "a" * 40
QUOTE = "This repository implements semantic search."
ROOT = node_uri(NodeType.repository, REPO)


def assertion(target="semantic-search", quote=QUOTE):
    return GraphAssertion(
        subject_type="repository",
        subject_id=REPO,
        predicate="implements",
        object_type="feature",
        object_id=target,
        quote=quote,
    )


@pytest.fixture
def snapshot(monkeypatch):
    monkeypatch.setitem(
        REGISTRY,
        REPO,
        Source(
            paths=("README.md", "src/search.py"),
            assertions={
                "README.md": (
                    Assertion(fact="semantic_search_repository", value=REPO, quote=QUOTE),
                )
            },
            graph_assertions={"README.md": (assertion(),)},
        ),
    )
    return Snapshot(
        repository=REPO,
        commit_sha=SHA,
        complete=True,
        public_verified_from=f"https://api.github.com/repos/{REPO}",
        files={
            "README.md": "# Research\n\n" + QUOTE + "\n",
            "src/search.py": "def search():\n    return []\n",
        },
    )


class Memory:
    def __init__(self, chunks):
        self.payloads = {c.point_id: c.model_dump(mode="json") for c in chunks}
        self.calls = []
        self.fail = False

    def chunks(self):
        return [Chunk.model_validate(v) for v in self.payloads.values()]

    async def graph_chunks(self, nodes):
        return [c for c in self.chunks() if set(nodes).intersection(c.graph_node_ids)]

    async def search(self, query, limit):
        return [(0.9, c) for c in self.chunks()[:limit]]

    async def embed(self, texts, kind):
        return [[1.0] + [0.0] * 1023 for _ in texts]

    async def qdrant(self, method, path, body):
        self.calls.append(path)
        if self.fail:
            raise UpstreamError()
        if path == "/points?wait=true":
            self.payloads.update({p["id"]: p["payload"] for p in body["points"]})
        elif path == "/points/payload?wait=true":
            for identity in body["points"]:
                self.payloads[identity] = body["payload"]
        elif path == "/points/delete?wait=true":
            for identity in body["points"]:
                del self.payloads[identity]

    async def close(self):
        pass


def reviewed_edges(chunks):
    return [e for e in materialize(chunks)[1] if e.kind == "reviewed"]


def test_stable_uri_edge_and_revision_identity(snapshot):
    assert ROOT == BASE + "repository/sndcds/uranus-admin"
    chunks = extract(snapshot, NOW)
    newer = extract(snapshot.model_copy(update={"commit_sha": "b" * 40}), NOW)
    edge = reviewed_edges(chunks)[0]
    assert edge.id == assertion().id == reviewed_edges(newer)[0].id
    assert edge.evidence_ids != reviewed_edges(newer)[0].evidence_ids
    assert materialize(chunks) == materialize(extract(snapshot, NOW + timedelta(days=1)))


@pytest.mark.parametrize(
    "identifier",
    ["/tmp/file", "../repo", "home/user/repo", "10.0.0.2", "api_key=abc", "ghp_" + "a" * 36],
)
def test_unsafe_node_identifiers(identifier):
    with pytest.raises(ValueError):
        node_uri(NodeType.component, identifier)


def test_closed_vocabulary_and_types():
    assert set(RELATIONS) == set(Relation)
    for updates in (
        {"predicate": "invented"},
        {"subject_type": "invented"},
        {"object_type": "symbol"},
        {"negative": True},
    ):
        with pytest.raises(ValidationError):
            GraphAssertion.model_validate({**assertion().model_dump(), **updates})
    with pytest.raises(ValueError):
        edge_id(ROOT, "implemented_in", assertion().object)
    with pytest.raises(ValidationError):
        GraphNode(id=ROOT, type="component")


def test_structural_edges_and_reviewed_evidence(snapshot):
    chunks = extract(snapshot, NOW)
    nodes, edges, evidence = materialize(chunks)
    assert {"contains", "defines", "implements"} == {e.predicate for e in edges}
    assert set(e.id for e in edges) == {e for c in chunks for e in c.graph_edge_ids}
    assert all(e.evidence_ids for e in edges)
    refs = {e.id: e for e in evidence}
    for edge in edges:
        assert edge.subject in {n.id for n in nodes}
        for identity in edge.evidence_ids:
            e = refs[identity]
            assert e.commit_sha == SHA and e.repository == REPO
            assert e.source_url == f"https://github.com/{REPO}/blob/{SHA}/{e.path}"
            matching = [c for c in chunks if c.path == e.path and c.content_hash == e.content_hash]
            assert matching and matching[0].line_start == e.line_start
            assert matching[0].line_end == e.line_end
            assert e.content_hash == sha256(matching[0].chunk_text.encode()).hexdigest()


def test_exact_quote_and_registered_path_required(snapshot):
    changed = snapshot.model_copy(
        update={"files": {"README.md": QUOTE.lower(), "src/search.py": None}}
    )
    assert not reviewed_edges(extract(changed, NOW))
    chunks = extract(snapshot, NOW)
    chunk = next(c for c in chunks if c.graph_assertions)
    for update in (
        {"graph_assertions": [assertion(quote=QUOTE.lower())]},
        {"graph_assertions": [assertion("invented-feature")]},
        {"graph_edge_ids": []},
    ):
        with pytest.raises(ValidationError):
            Chunk.model_validate({**chunk.model_dump(), **update})
    moved = snapshot.model_copy(
        update={"files": {"README.md": None, "src/search.py": f'"""{QUOTE}"""'}}
    )
    assert not reviewed_edges(extract(moved, NOW))


async def test_graph_complete_partial_failure_and_unchanged(snapshot):
    chunks = extract(snapshot, NOW)
    db = Memory(chunks)
    unchanged = plan(
        extract(snapshot, NOW + timedelta(days=1)), db.payloads, repository=REPO, complete=True
    )
    assert len(unchanged.unchanged) == len(chunks)
    partial = snapshot.model_copy(
        update={"complete": False, "files": {"src/search.py": snapshot.files["src/search.py"]}}
    )
    desired = extract(partial, NOW)
    diff = plan(desired, db.payloads, repository=REPO, complete=False)
    await reconcile(db, desired, diff)
    assert reviewed_edges(db.chunks())
    removed = snapshot.model_copy(
        update={"files": {"README.md": None, "src/search.py": "def updated():\n    return 1\n"}}
    )
    desired = extract(removed, NOW)
    diff = plan(desired, db.payloads, repository=REPO, complete=True)
    db.fail = True
    with pytest.raises(UpstreamError):
        await reconcile(db, desired, diff)
    assert "/points/delete?wait=true" not in db.calls
    assert reviewed_edges(db.chunks())
    db.fail = False
    await reconcile(db, desired, diff)
    assert not reviewed_edges(db.chunks())


async def test_quote_removal_same_point_updates_graph(snapshot):
    chunks = extract(snapshot, NOW)
    db = Memory(chunks)
    changed = snapshot.model_copy(
        update={
            "files": {**snapshot.files, "README.md": "# Research\n\nNo reviewed relation here.\n"}
        }
    )
    desired = extract(changed, NOW)
    await reconcile(db, desired, plan(desired, db.payloads, repository=REPO, complete=True))
    assert not reviewed_edges(db.chunks())


def test_conflicting_graph_provenance_rejected(snapshot):
    chunks = extract(snapshot, NOW)
    newer = extract(snapshot.model_copy(update={"commit_sha": "b" * 40}), NOW)
    with pytest.raises(ValueError, match="conflicting_point_revisions"):
        materialize(chunks + newer)


def test_multiple_reviewed_targets_are_not_exclusive(snapshot, monkeypatch):
    # Positive implements/uses/calls assertions are multivalued. No inverse,
    # negation or inferred choice between distinct supported edges exists.
    source = REGISTRY[REPO]
    monkeypatch.setitem(
        REGISTRY,
        REPO,
        replace(
            source,
            graph_assertions={"README.md": (assertion(), assertion("search-ui"), assertion())},
        ),
    )
    edges = reviewed_edges(extract(snapshot, NOW))
    assert len(edges) == 2 and all(len(e.evidence_ids) == 1 for e in edges)


async def test_graph_query_depth_direction_filter_integrity(snapshot):
    db = Memory(extract(snapshot, NOW))
    first = await graph_query(db, GraphQueryRequest(node=ROOT, depth=1))
    second = await graph_query(db, GraphQueryRequest(node=ROOT, depth=2))
    assert "defines" not in {e.predicate for e in first.edges}
    assert "defines" in {e.predicate for e in second.edges}
    filtered = await graph_query(
        db, GraphQueryRequest(node=assertion().object, relations=["implements"])
    )
    assert len(filtered.edges) == 1 and filtered.edges[0].subject == ROOT
    assert GraphQueryResponse.model_validate(second.model_dump()) == second
    with pytest.raises(ValidationError):
        GraphQueryResponse.model_validate({**second.model_dump(), "evidence": []})
    with pytest.raises(ValidationError):
        GraphEdge.model_validate({**second.edges[0].model_dump(), "evidence_ids": []})


@pytest.mark.parametrize(
    "body",
    [
        {"relations": ["invented"]},
        {"depth": 3},
        {"depth": 0},
        {"depth": True},
        {"repository": REPO},
        {"path": "README.md"},
        {"url": "https://github.com"},
        {"graph_assertions": []},
        {"node": "file:///tmp/x"},
        {"node": BASE + "component/../x"},
    ],
)
async def test_graph_request_security(snapshot, body):
    app = create_app(
        Settings(api_key="k" * 32, encoder_api_key="e" * 32, qdrant_api_key="q" * 32),
        Memory(extract(snapshot, NOW)),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/graph/query",
            json={"node": ROOT, **body},
            headers={"Authorization": "Bearer " + "k" * 32},
        )
        assert response.status_code == 422


async def test_graph_unknown_node_auth_and_empty_filter(snapshot):
    db = Memory(extract(snapshot, NOW))
    app = create_app(
        Settings(api_key="k" * 32, encoder_api_key="e" * 32, qdrant_api_key="q" * 32), db
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        assert (await client.post("/graph/query", json={"node": ROOT})).status_code == 401
        headers = {"Authorization": "Bearer " + "k" * 32}
        unknown = await client.post(
            "/graph/query", json={"node": BASE + "component/unknown"}, headers=headers
        )
        assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "unknown_node"
        empty = await client.post(
            "/graph/query", json={"node": ROOT, "relations": ["calls"]}, headers=headers
        )
        assert empty.status_code == 200 and empty.json()["edges"] == []
        assert len(empty.json()["nodes"]) == 1


@pytest.mark.parametrize("size,expected_nodes,expected_edges", [(65, 50, 49), (8, 9, 100)])
async def test_result_caps(monkeypatch, size, expected_nodes, expected_edges):
    # A star exceeds node cap; a dense component graph exceeds edge cap.
    many = []
    if size == 65:
        for i in range(size):
            many.append(
                GraphAssertion(
                    subject_type="component",
                    subject_id="root",
                    predicate="calls",
                    object_type="component",
                    object_id=f"node-{i}",
                    quote=f"Reviewed call {i}.",
                )
            )
    else:
        for i in range(size):
            for j in range(size):
                for predicate in ("calls", "uses"):
                    many.append(
                        GraphAssertion(
                            subject_type="component",
                            subject_id=f"node-{i}",
                            predicate=predicate,
                            object_type="component",
                            object_id=f"node-{j}",
                            quote=f"Reviewed {predicate} {i} {j}.",
                        )
                    )
        many += [
            GraphAssertion(
                subject_type="component",
                subject_id="root",
                predicate="calls",
                object_type="component",
                object_id=f"node-{i}",
                quote=f"Root call {i}.",
            )
            for i in range(size)
        ]
    monkeypatch.setitem(REGISTRY, REPO, Source(graph_assertions={"README.md": tuple(many)}))
    snapshot = Snapshot(
        repository=REPO,
        commit_sha=SHA,
        public_verified_from=f"https://api.github.com/repos/{REPO}",
        files={"README.md": "\n\n".join(a.quote for a in many)},
    )
    result = await graph_query(
        Memory(extract(snapshot, NOW)),
        GraphQueryRequest(node=BASE + "component/root", relations=["calls", "uses"], depth=2),
    )
    assert len(result.nodes) == expected_nodes and len(result.edges) == expected_edges
    assert result.truncated


def test_jsonld_deterministic_order_and_license_gate(snapshot):
    chunks = extract(snapshot, NOW)
    output = export_jsonld(chunks)
    assert output == export_jsonld(list(reversed(chunks)))
    assert output == export_jsonld(extract(snapshot, NOW + timedelta(days=1)))
    assert QUOTE not in output and "chunk_text" not in output
    records = json.loads(output)["@graph"]
    assert [r["@id"] for r in records] == sorted(r["@id"] for r in records)
    assert any(
        r.get("commit_sha") == SHA and r["license"].startswith("UNREVIEWED") for r in records
    )
    assert any(r.get("rdf:predicate", {}).get("@id") == BASE + "implements" for r in records)


def allow_license(monkeypatch, license_id="MIT"):
    monkeypatch.setitem(
        REGISTRY,
        REPO,
        replace(
            REGISTRY[REPO],
            license=license_id,
            license_review_commit=SHA,
            license_path="LICENSE",
            license_content_hash="0" * 64,
            evidence_redistribution_allowed=True,
        ),
    )


async def test_license_gate_all_api_routes(snapshot, monkeypatch):
    for allowed in (False, True):
        if allowed:
            allow_license(monkeypatch)
        chunks = extract(snapshot, NOW)
        app = create_app(
            Settings(api_key="k" * 32, encoder_api_key="e" * 32, qdrant_api_key="q" * 32),
            Memory(chunks),
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            for path, body in (
                ("/query", {"query": "search?"}),
                ("/evidence-answer", {"query": "search?", "fact": "semantic_search_repository"}),
                ("/graph/query", {"node": ROOT}),
            ):
                response = await client.post(
                    path, json=body, headers={"Authorization": "Bearer " + "k" * 32}
                )
                assert response.status_code == 200
                data = response.json()
                evidence = (
                    [m["evidence"][0] for m in data["matches"]]
                    if path == "/query"
                    else data["evidence"]
                )
                assert all(e["excerpt_included"] == allowed for e in evidence)
                assert all(("chunk_text" in e) == allowed for e in evidence)
                assert all(
                    e["commit_sha"] == SHA and e["source_url"] and e["content_hash"]
                    for e in evidence
                )
                assert '"quote"' not in response.text and '"assertions"' not in response.text
                if path == "/evidence-answer":
                    assert data["supported"] and data["facts"][0]["value"] == REPO
                    assert set(data["facts"][0]["evidence_ids"]) <= {e["id"] for e in evidence}
        output = export_jsonld(chunks)
        assert (QUOTE in output) == allowed
        assert "AGPL" not in output  # Service-code license is never assigned to indexed works.


def test_payload_license_never_grants_permission_and_revision_fails_closed(snapshot, monkeypatch):
    chunks = extract(snapshot, NOW)
    assert not public_evidence(chunks[0].model_copy(update={"license": "MIT"})).excerpt_included
    allow_license(monkeypatch)
    assert public_evidence(chunks[0]).excerpt_included
    newer = extract(snapshot.model_copy(update={"commit_sha": "b" * 40}), NOW)
    assert all(not public_evidence(c).excerpt_included for c in newer)
    monkeypatch.setitem(
        REGISTRY, REPO, replace(REGISTRY[REPO], evidence_redistribution_allowed=False)
    )
    assert not public_evidence(chunks[0]).excerpt_included


def test_exact_eleven_fact_keys():
    expected = {
        "uranus_overview",
        "admin_overview",
        "semantic_search_repository",
        "embedding_component",
        "embedding_model",
        "qdrant_usage",
        "encoder_communication",
        "planner_component",
        "geocoding",
        "architecture",
        "founding_date",
    }
    assert set(get_args(FactKey)) == expected and len(get_args(FactKey)) == 11
    for body in (
        {"query": "test"},
        {"query": "test", "fact": "unknown"},
        {"query": "test", "fact": "arbitrary"},
    ):
        with pytest.raises(ValidationError):
            AnswerRequest.model_validate(body)


async def test_founding_date_and_conflicting_fact_remain_unsupported(snapshot, monkeypatch):
    source = REGISTRY[REPO]
    monkeypatch.setitem(
        REGISTRY,
        REPO,
        replace(
            source,
            assertions={
                "README.md": (
                    *source.assertions["README.md"],
                    Assertion(fact="semantic_search_repository", value="conflicting", quote=QUOTE),
                )
            },
        ),
    )
    db = Memory(extract(snapshot, NOW))
    result = await answer(db, AnswerRequest(query="search?", fact="semantic_search_repository"))
    assert not result.supported and result.reason == "conflicting_evidence"
    result = await answer(db, AnswerRequest(query="founded?", fact="founding_date"))
    assert not result.supported and result.reason == "no_explicit_evidence"


async def test_runtime_graph_only_uses_fixed_qdrant(snapshot):
    chunks = extract(snapshot, NOW)
    calls = []

    def handler(request):
        calls.append(request)
        body = json.loads(request.content)
        assert request.url.host == "127.0.0.1" and request.url.port == 6333
        assert request.url.path.endswith("/points/scroll")
        assert body["filter"]["must"][-1] == {"key": "graph_node_ids", "match": {"any": [ROOT]}}
        assert request.headers.get("authorization") is None
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "result": {
                    "points": [
                        {"id": c.point_id, "payload": c.model_dump(mode="json")} for c in chunks
                    ],
                    "next_page_offset": None,
                },
            },
        )

    settings = Settings(api_key="k" * 32, encoder_api_key="e" * 32, qdrant_api_key="q" * 32)
    client = Clients(settings, httpx.MockTransport(handler))
    assert await client.graph_chunks([ROOT])
    assert len(calls) == 1
    await client.close()


def test_export_cli_offline(snapshot, monkeypatch, tmp_path):
    import sys

    from uranus_research_knowledge.__main__ import main

    def forbidden(*args, **kwargs):
        raise AssertionError("offline export must not create an upstream client")

    monkeypatch.setattr("uranus_research_knowledge.__main__.Clients", forbidden)
    snapshot_path = tmp_path / "snapshot.json"
    output = tmp_path / "graph.jsonld"
    snapshot_path.write_text(snapshot.model_dump_json())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "knowledge",
            "graph",
            "export",
            "--format",
            "jsonld",
            "--snapshot",
            str(snapshot_path),
            "--output",
            str(output),
        ],
    )
    main()
    assert output.read_text() == export_jsonld(extract(snapshot, NOW))


async def test_graph_scan_budget_fails_closed(snapshot, monkeypatch):
    import uranus_research_knowledge.graph as graph_module

    monkeypatch.setattr(graph_module, "MAX_QUERY_CHUNKS", 1)
    with pytest.raises(UpstreamError, match="graph_scan_limit"):
        await graph_query(Memory(extract(snapshot, NOW)), GraphQueryRequest(node=ROOT))


@pytest.mark.parametrize("fault", ["identity", "unrelated", "quote", "offset"])
async def test_graph_upstream_validation(snapshot, fault):
    chunks = extract(snapshot, NOW)
    chunk = next(c for c in chunks if c.graph_assertions)
    point = {"id": chunk.point_id, "payload": chunk.model_dump(mode="json")}
    if fault == "identity":
        point["id"] = "wrong"
    if fault == "quote":
        point["payload"]["graph_assertions"][0]["quote"] = "forged quote"
    page = {"points": [point], "next_page_offset": "repeated" if fault == "offset" else None}
    settings = Settings(api_key="k" * 32, encoder_api_key="e" * 32, qdrant_api_key="q" * 32)
    client = Clients(
        settings,
        httpx.MockTransport(lambda r: httpx.Response(200, json={"status": "ok", "result": page})),
    )
    with pytest.raises(UpstreamError):
        await client.graph_chunks([BASE + "component/unrelated" if fault == "unrelated" else ROOT])
    await client.close()


def test_graph_evidence_denies_false_excerpt_state(snapshot):
    from uranus_research_knowledge.models import Evidence

    evidence = public_evidence(extract(snapshot, NOW)[0])
    for update in (
        {"excerpt_included": True},
        {"chunk_text": "text"},
        {"excerpt_included": True, "chunk_text": "text"},
    ):
        with pytest.raises(ValidationError):
            Evidence.model_validate({**evidence.model_dump(), **update})


def test_redundant_inverse_and_structural_assertion_rejected():
    for update in (
        {"predicate": "implemented_in"},
        {"subject_type": "source_file", "predicate": "defines", "object_type": "symbol"},
        {"predicate": "contains", "object_type": "source_file"},
    ):
        with pytest.raises(ValidationError):
            GraphAssertion.model_validate({**assertion().model_dump(), **update})
