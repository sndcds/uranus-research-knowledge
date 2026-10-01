# Validation record — 2026-10-01

The architecture was committed as `63df4d4` before implementation. Fresh companion
main revisions and migration boundaries are recorded in [operations](operations.md).
The target knowledge repository already existed with its license commit; this work
populates it. Encoder code and semantic contracts were not changed.

Historical initial implementation checks (before this follow-up), using Python 3.13:

| Check | Result |
| --- | --- |
| Knowledge service tests | 28 passed |
| Planner full suite | 1,092 passed; 80 optional live-model evaluations skipped |
| Admin affected research/auth suites | 298 passed, with disposable PostgreSQL/PostGIS |
| Cross-repository acceptance | 6 passed (five questions plus planner/Admin schema parity) |
| Planner mypy | 17 source files passed |
| Admin mypy | 192 source files passed |
| Ruff checks/format and git diff whitespace | Passed |
| Generated service schemas and companion OpenAPI | Regenerated and checked |

Knowledge tests cover deterministic chunks/IDs/line provenance, SHA changes, unchanged
and metadata-only vectors, moved-text reuse, complete/partial deletion, failure before
delete, path and secret rejection, source/assertion matching, unsupported facts, auth,
body bounds, fixed collection/encoder routes and embedding validation.

Admin tests include the actual PostgreSQL queries, DISTINCT counts, effective locations,
Unicode/HTML projection, population overflow, question-only request boundaries, source
routing and unchanged v3/auth behavior. PostgreSQL ran in a dedicated local test
container using synthetic fixtures and test-only credentials; no production connection
or migration was used.

Cross-repository tests are in `integration/`. They exercise real ASGI endpoints and
Admin's real PostgreSQL executor. Encoder and Qdrant responses are synthetic, normalized
1024-D fixtures. The five assertions are:

1. Longest event text -> PostgreSQL exact metric (empty fixture descriptions tie at 0;
   a separate SQL regression proves markup/Unicode ordering with nonempty text).
2. Organization with most events -> PostgreSQL count of 2 eligible distinct events.
3. Semantic-search repository -> supported repository fact with matching source code.
4. Event embedding producer -> supported encoder fact with matching README evidence.
5. Founding date -> supported=false, no invented date, retrieved evidence retained.

To rerun cross-repository tests, use an environment containing the dependencies of all
three repositories, put their source roots on PYTHONPATH, and run from the Admin
`backend/` directory (its fixture uses relative paths):

```sh
TEST_DATABASE_URL=postgresql+asyncpg://TEST_USER:TEST_PASSWORD@127.0.0.1:TEST_PORT/knowledge_test \
PYTHONPATH=/checkout/knowledge/src:/checkout/planner/src:/checkout/admin/backend \
pytest -q /checkout/knowledge/integration --override-ini asyncio_mode=auto
```

Use an empty disposable database whose name ends `_test`. The fixture refuses an
existing Uranus schema. It creates and removes synthetic schemas; never use production.

These checks establish orchestration and evidence contracts, not production factual
coverage, live model language quality, real Jina relevance or live Qdrant compatibility.
No production indexing, deployment, publication, browser migration or GitHub PR merge
was performed. Those steps need their own staged validation and authorization.

## Reviewed graph/license follow-up — 2026-10-01

The current planner architecture is model-backed natural-language planning with
`research-query-plan-v4`, `research-domain-planner-v2`, strict closed structured
output and the configured provider/model (production candidate `gpt-5.6-terra`).
There is no production question catalogue. Live v4 Terra acceptance is still being
validated separately and was not run here.

| Current check | Result |
| --- | --- |
| Knowledge `uv run pytest -q` | 70 passed (28 existing + 42 added cases) |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed |
| `git diff --check` | Passed |
| Contract generation/reproducibility | Seven schemas regenerated; exact schema tests passed |
| Configured mypy | Not configured in this repository |
| Offline reviewed-source extraction | 267 chunks; 25 nodes; 20 edges including nine reviewed architecture edges |
| Offline JSON-LD | Deterministic ordering and revision-qualified evidence; redistribution gate tested |
| Current companion acceptance | 4 passed, 4 failed due to Admin's old evidence response schema |

Tests cover stable nodes/logical edges, closed types/predicates, structural
contains/defines, exact reviewed quotes and path scoping, quote removal, no churn,
complete/partial reconciliation and failed writes before deletion. Graph checks cover
incoming/outgoing traversal, unknown nodes/relations, strict depth, node/edge caps,
scan overflow, malformed upstream provenance, evidence integrity and deterministic
JSON-LD. Conflicting point revisions fail closed; positive multivalued relations
coalesce identical edges without inventing exclusivity or inverse edges.

License checks exercise every API route and export: reviewed excerpts are included,
unreviewed sources withhold text/quotes while preserving provenance and supported
facts, payload license labels cannot grant access, unreviewed revisions fail closed,
and indexed works never inherit the service-code license. Existing private-path,
secret-content, encoder-contract, authentication and reconciliation tests remain green.
The eleven FactKeys match the companion domain schemas; `unknown` and missing fact
intents are rejected. Founding date still returns `supported=false` in Knowledge.

The source review used explicit GitHub reads outside tests. Ordinary tests use
synthetic sources/transports and contact no GitHub, real encoder or Qdrant. The
full-source review and eight-snapshot CLI export were local and did not index Qdrant.

### Cross-repository acceptance and merge blocker

Read-only source archives were pinned to Admin
`181bfd39a098e7860bb5eb7b947c4b5dff8fdbc4` and Planner
`c47321f8b3e048cddca2eabbe634974b1f6ca951`. The existing Knowledge-owned harness
now injects synthetic v4 model decisions instead of relying on the removed planner
catalogue. No provider network call or production credential was used.

A disposable `postgis/postgis:17-3.5` container on a dynamically assigned loopback
port ran the guarded synthetic `_test` database. It was stopped and removed after
validation. Two PostgreSQL acceptance questions, full planner/Admin plan-schema
parity and eleven-FactKey parity passed. Three project-answer scenarios returned
502 from Admin, and a new metadata-only Evidence acceptance check failed validation.

Cause: Admin's copied `app/schemas/project_knowledge.py` still requires internal
Chunk fields, including nonempty `chunk_text` and quote-bearing assertions, and
rejects new public Evidence fields. Its copied evidence FactKey also still has
`unknown`, despite the corrected eleven-key domain schema. No compatibility mode
was added and no companion source was modified. These four failures remain visible
in the optional integration harness; they are not skipped or marked expected failure.
The default CI suite remains Knowledge-only, as before this follow-up.

Before coordinated merge, separately update Admin's evidence contract to this PR's
generated `AnswerResponse.json`, validate evidence references/provenance without
requiring redistributed quotes, and rerun all eight integration checks. Separate
live planner acceptance and staged real encoder/Qdrant validation also remain pending.
No deployment, production indexing, merge or source-license relicensing was performed.
