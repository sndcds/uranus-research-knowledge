# Uranus Research Knowledge

Authenticated, evidence-first project knowledge for Kulturbytes. Exact event,
organization and geography questions remain in **uranus-admin PostgreSQL/PostGIS**.
This service has no production database credentials, ORM, LLM or runtime web crawler.

Read the [architecture](docs/architecture.md), recorded before implementation, and
[operations and contracts](docs/operations.md). Nothing has been deployed.

```text
natural-language question → model-backed closed planner /v4/plan → Admin routes
                                      ├─ data → local read-only PostgreSQL
                                      └─ project_knowledge → knowledge /evidence-answer
                                                            └─ encoder + Qdrant
```

Python 3.13:

```sh
uv sync --locked --group dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Set `KNOWLEDGE_API_KEY`, `KNOWLEDGE_ENCODER_API_KEY`, and `KNOWLEDGE_QDRANT_API_KEY`
through your service supervisor, each at least 32 printable non-whitespace ASCII
characters. No dotenv files are loaded. Encoder and Qdrant default to loopback
ports 6335 and 6333; remote origins require HTTPS. The service never provisions
itself or downloads a model when answering a question.

```sh
uv run uvicorn uranus_research_knowledge.app:create_app --factory \
  --host 127.0.0.1 --port 6336 --no-access-log
```

Authenticated endpoints: `GET /health`, `GET /ready`, `POST /query`,
`POST /evidence-answer`, `POST /graph/query`. Readiness checks the collection contract, not corpus
completeness or factual coverage. JSON Schemas are in [contracts/](contracts/).

```json
{"query":"Welches Repository implementiert die semantische Suche?","limit":10}
```

`/query` returns candidates with license-gated excerpts, hashes, line bounds and immutable
commit links. `/evidence-answer` additionally takes a closed `fact` intent, such as
`semantic_search_repository`, and returns `supported`, facts, evidence and revisions.
Only a reviewed assertion whose exact quotation occurs in a retrieved chunk may
support a fact. An absent founding date produces `supported=false`; repository
creation dates are never used as a substitute.

The fixed collection is `kulturbytes_project_knowledge_jina_v3_v1` (1024-D Cosine).
The existing research encoder supplies `jina-v3` query/passage embeddings unchanged.
Its model license and provisioning requirements remain applicable.

The initial registry contains the eight requested public repositories, with exact
reviewed paths. Extending it requires a code review. The default reviewed assertions
cover the semantic-search repository, embedding component/model, and planner
component. Other questions route to evidence retrieval but may remain unsupported
until explicit source assertions are reviewed.

See [validation](docs/validation.md) for executed checks and limitations.

[Implementation handoff and coordinated PRs](docs/implementation-report.md).

The planner uses `research-query-plan-v4`, interpreter
`research-domain-planner-v2`, and its configured provider/model (production candidate
`gpt-5.6-terra`). Production does not match a question catalogue. Live v4 Terra
acceptance is being validated separately; this service remains independent of the model.

`/evidence-answer` requires one of exactly eleven FactKeys; `unknown` is rejected.
Exploratory `/query` has no fact field. The public Evidence schema is separate from
internal Chunk payloads: `evidence_available=true`, `excerpt_included=false` and
provenance remain available when source redistribution is not approved. Neither
`chunk_text` nor internal assertion quotes are returned in that case. Approval is
server-controlled and pinned to the reviewed source revision.

Reviewed graph assertions add nine architecture edges to the deterministic
repository/file/symbol graph. `/graph/query` accepts a stable indexed node URI,
closed `relations`, and depth 1–2; responses contain at most 50 nodes and 100 edges,
with evidence for every edge. No prose generation, inference or triple store is involved.
See [source and license review](docs/source-review.md) for supported and missing links.

Offline deterministic export uses existing provisioned snapshots, without credentials
or network access:

```sh
uv run python -m uranus_research_knowledge graph export --format jsonld \
  --snapshot /operator/snapshots/admin.json --output /operator/graph.jsonld
```

Repeat `--snapshot` for other repositories. JSON-LD preserves per-source licensing,
commit-pinned attribution and the same excerpt gate as the API.
