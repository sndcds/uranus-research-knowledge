"""Cross-repository acceptance: real ASGI boundaries + PostgreSQL, fake embeddings/index."""

from datetime import UTC, datetime

import httpx
import pytest
from app.services.research_domain_client import ResearchDomainClient
from pydantic import SecretStr
from research_planner.app import create_app as planner_app
from research_planner.config import Settings as PlannerSettings

from uranus_research_knowledge.app import create_app as knowledge_app
from uranus_research_knowledge.clients import Clients
from uranus_research_knowledge.config import Settings as KnowledgeSettings
from uranus_research_knowledge.extraction import Snapshot, extract
from uranus_research_knowledge.models import EMBEDDING_VERSION
from uranus_research_knowledge.registry import REGISTRY


@pytest.fixture
async def pipeline(db_client):
    # Explicit synthetic revisions. Never claim these fixtures are live repository evidence.
    fixtures = {
        "sndcds/uranus-admin": {
            "README.md": "# Synthetic Admin fixture\n",
            "backend/README.md": None,
            "backend/app/services/semantic_search.py": (
                "async def semantic_research():\n"
                "    return await qdrant.search(vector, 50, entity_ids=eligible_ids)\n"
            ),
        },
        "sndcds/uranus-research-encoder": {
            "README.md": "# Synthetic Encoder fixture\n\n"
            + REGISTRY["sndcds/uranus-research-encoder"].assertions["README.md"][0].quote
            + "\n",
        },
    }
    chunks = []
    for repository, files in fixtures.items():
        snapshot = Snapshot(
            repository=repository,
            commit_sha="a" * 40,
            public_verified_from=f"https://api.github.com/repos/{repository}",
            complete=True,
            files=files,
        )
        chunks.extend(extract(snapshot, datetime.now(UTC)))

    def retrieval(request):
        if request.url.path == "/embed":
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
                        {"id": c.point_id, "score": 0.9, "payload": c.model_dump(mode="json")}
                        for c in chunks
                    ]
                },
            },
        )

    settings = KnowledgeSettings(
        api_key="k" * 32, encoder_api_key="e" * 32, qdrant_api_key="q" * 32
    )
    knowledge_client = Clients(settings, httpx.MockTransport(retrieval))
    transports = {
        8090: httpx.ASGITransport(planner_app(PlannerSettings(service_api_key="p" * 32))),
        6336: httpx.ASGITransport(knowledge_app(settings, knowledge_client)),
    }

    class InternalTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return await transports[request.url.port].handle_async_request(request)

    app = db_client._transport.app
    config = app.state.settings
    config.research_domain_enabled = True
    config.research_planner_url = "http://127.0.0.1:8090"
    config.research_planner_api_key = SecretStr("p" * 32)
    config.research_knowledge_url = "http://127.0.0.1:6336"
    config.research_knowledge_api_key = SecretStr("k" * 32)
    client = ResearchDomainClient(config, transport=InternalTransport())
    app.state.research_domain = client
    yield db_client
    await client.close()
    await knowledge_client.close()


@pytest.mark.parametrize(
    "question,source,value",
    [
        ("Welches Event hat den längsten Veranstaltungstext?", "postgresql", 0),
        ("Welche Organisation hat die meisten Veranstaltungen?", "postgresql", 2),
        (
            "Welches Repository implementiert die semantische Suche?",
            "project_sources",
            "sndcds/uranus-admin",
        ),
        (
            "Welche Komponente erzeugt die Embeddings für die Eventsuche?",
            "project_sources",
            "sndcds/uranus-research-encoder",
        ),
        ("Wann wurde Kulturbytes gegründet?", "project_sources", None),
    ],
)
async def test_acceptance(pipeline, headers, question, source, value):
    result = await pipeline.post(
        "/api/v1/research/v4/query", json={"query": question}, headers=headers
    )
    assert result.status_code == 200, result.text
    answer = result.json()
    assert answer["authoritative_source"] == source
    if source == "postgresql":
        assert answer["records"][0]["value"] == value
    elif value is None:
        assert answer["supported"] is False and answer["facts"] == []
        assert answer["evidence"]
    else:
        assert answer["supported"] is True and answer["facts"][0]["value"] == value
        assert all(c["commit_sha"] == "a" * 40 for c in answer["evidence"])


def test_planner_and_admin_schema_identical():
    from app.schemas.research_domain import PlanEnvelopeV4 as AdminPlan
    from research_planner.domain_schema import PlanEnvelopeV4 as PlannerPlan

    assert AdminPlan.model_json_schema() == PlannerPlan.model_json_schema()
