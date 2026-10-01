# Validation record — 2026-10-01

The architecture was committed as `63df4d4` before implementation. Fresh companion
main revisions and migration boundaries are recorded in [operations](operations.md).
The target knowledge repository already existed with its license commit; this work
populates it. Encoder code and semantic contracts were not changed.

Executed locally with Python 3.13:

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
