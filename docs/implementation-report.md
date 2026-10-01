# Implementation handoff — Kulturbytes Open Knowledge Research v1

## Repositories and review

| Repository | Deliverable |
| --- | --- |
| [uranus-research-knowledge](https://github.com/sndcds/uranus-research-knowledge/pull/1) | New Python service, indexer, vocabulary, evidence contracts and design |
| [uranus-research-planner](https://github.com/sndcds/uranus-research-planner/pull/12) | Model-backed natural-language planning and closed v4 domain contract |
| [uranus-admin](https://github.com/sndcds/uranus-admin/pull/161) | Focused opt-in orchestration and exact metric executor |
| uranus-research-encoder | Reused unchanged through its existing HTTP contract |

All three changes are draft PRs. The knowledge repository already existed with a
license-only initial commit; it was populated through its initial implementation PR.
Companion changes were made in isolated clones, preserving the user's working copies.
The [architecture](architecture.md) was committed before implementation.

## Architecture and trust boundaries

Question -> Admin -> planner -> validated domain. Data stays in Admin's read-only
PostgreSQL/PostGIS executor. Project knowledge goes to the authenticated knowledge
service, which returns license-gated evidence and reviewed facts. PostgreSQL is authoritative
for cultural data; reviewed project sources are authoritative for software/history.
Jina represents text; Qdrant retrieves candidates; the planner interprets questions.
None invents or independently establishes factual answers.

The knowledge runtime has no production database configuration, database driver,
LLM or GitHub fetch path. It is stateless and works with provisioned local encoder
artifacts and Qdrant without internet. Explicit source provisioning is separate.

## Implemented contracts

- **Graph:** `kulturbytes-kg-v1`; closed project/data node types and typed relation
  pairs, stable conceptual `https://kulturbytes.de/kg/` URIs, deterministic edge IDs.
  Source containment/definition links and nine reviewed architecture relations are
  materialized. Bounded authenticated graph queries and offline JSON-LD are implemented;
  public publication and Turtle remain outside scope.
- **Registry:** the eight requested `sndcds` repositories. Exact reviewed paths,
  public-visibility checks, full commit/tree validation and immutable source URLs.
  Additional repositories/paths require explicit review. Source license/attribution
  policy is documented; no automatic relicensing of public content.
- **Collection:** `kulturbytes_project_knowledge_jina_v3_v1`, 1024-D Cosine and pinned
  existing Jina embedding version. Event collections are untouched. Payloads contain
  excerpts, complete provenance, graph IDs and reviewed assertions. Explicit CLI
  plan/reconcile records commits/corpus hashes, reuses unchanged vectors and deletes
  only within complete repository snapshots after successful writes.
- **Planner:** additive `/v4/plan`, `research-query-plan-v4`, model-backed natural-language planning with strict closed structured output,
  interpreter `research-domain-planner-v2`, and configured provider/model (production
  candidate `gpt-5.6-terra`). No production catalogue matching.
  Existing `/plan` v3 is preserved. Only allowlisted rank/evidence_answer combinations
  execute initially. Arbitrary SQL, collections, paths, URLs and executors are absent.
- **Metrics:** complete closed catalogue documented in the architecture and Admin PR.
  Six initial pairs execute: event description_characters/occurrence_count,
  organization event_count/venue_count, venue occurrence_count, category event_count.
  Description length uses Unicode code points after `public_clean`; bounds reject an
  incomplete ranking. Other metrics require explicit semantic/SQL implementation.
- **Evidence:** `/query` returns candidates with license-gated excerpts. `/evidence-answer` supports a fact
  only when a retrieved excerpt contains an exact reviewed assertion. Responses include
  supported, facts, evidence and indexed commits. Missing/conflicting evidence fails
  closed; a founding date is never inferred from repository creation.
- **Security:** authenticated bounded internal requests, no CORS, fixed upstreams and
  collection, strict input field allowlists, no redirects/environment proxies, no
  browser credentials forwarded, safe errors, public-only provisioning, secret/email
  rejection and distinct serving/indexing credential roles.

Full details and per-question coverage: [operations](operations.md).

## Acceptance

| Mandatory question | Verified path |
| --- | --- |
| Welches Event hat den längsten Veranstaltungstext? | Planner -> Admin -> exact PostgreSQL population/public-text ranking |
| Welche Organisation hat die meisten Veranstaltungen? | Planner -> Admin -> PostgreSQL DISTINCT event count |
| Welches Repository implementiert die semantische Suche? | Planner -> knowledge -> supported source evidence for uranus-admin |
| Welche Komponente erzeugt die Embeddings für die Eventsuche? | Planner -> knowledge -> supported README evidence for research-encoder |
| Wann wurde Kulturbytes gegründet? | No explicit founding assertion -> supported=false |

Historical initial implementation validation: 28 knowledge tests, 1,092 planner tests, 298 Admin tests and six
cross-repository checks passed. The 80 optional live-model tests were skipped.
Mypy, Ruff, schema/OpenAPI generation and whitespace checks passed. Acceptance used
real ASGI boundaries and disposable PostgreSQL with synthetic encoder/Qdrant responses;
it does not establish live semantic relevance or production factual coverage. The
disposable test container was removed. See [validation](validation.md).

## Migration and deployment plan

Review the coordinated PRs, provision reviewed snapshots and the dedicated collection,
verify real encoder/Qdrant integration and citations in staging, then opt Admin into v4
with server-only configuration. Existing v3 remains available. A subsequent browser
migration must coordinate Nitro/Zod/evidence presentation; this release is API-only.
Unknown facts remain visibly unsupported. Disable the v4 flag to roll back without
changing existing structured execution. No new database grants or migrations are needed.

No deployment, production indexing, graph publication or PR merge was performed.

## Graph/license follow-up

The Knowledge wire contract now has the same eleven FactKeys as Planner #12/Admin
#161; `unknown` and missing fact intents are rejected. The Knowledge runtime remains
model-independent. No companion repository was modified. Live v4 Terra acceptance
is still being validated separately and was not performed in this task.

Nine exact-quote GraphAssertions activate at reviewed source revisions, alongside
structural contains/defines edges. Graph evidence is commit-qualified and every
edge is materializable from validated chunks. Query traversal and deterministic
JSON-LD use the same closed vocabulary, provenance and source license gate.
`implements` is the canonical direction; no redundant reviewed inverse is added.
See [source review](source-review.md) for every added edge and missing candidate.

Public Evidence replaces direct Chunk serialization. Internal text remains available
for exact validation and embedding, but unreviewed/unapproved revisions return only
metadata, provenance and explicit excerpt-status flags. License approval is pinned
per source revision; no source material inherits the Knowledge code license.
Current test counts, CI and remaining integration limits are in [validation](validation.md).

Merge blocker confirmed at Admin `181bfd39a098e7860bb5eb7b947c4b5dff8fdbc4`:
its copied `project_knowledge` response model still requires raw chunks/quotes.
Admin needs a separately authorized update to consume public Evidence metadata and
validate fact evidence IDs without requiring redistributed text. Its domain FactKeys
already match, but the copied evidence module also retains the stale `unknown` key.
Knowledge must not re-expose source text to accommodate that older client.
