# Provisioning, indexing and migration

## Source review

`registry.py` is the only registry. Initially all eight public repositories allow
`README.md`; Admin additionally allows `backend/README.md` and the semantic search
service module. Add documentation, manifests, compose/OpenAPI descriptions or service
units as **exact reviewed paths**, never a repository-wide wildcard. Python extraction
uses classes/functions and module docstrings. Other reviewed files use headings and
paragraphs, split at 480 characters with exact source line provenance.

Content with email addresses or recognizable secret material is excluded as a whole
file; the report lists excluded paths. This deliberately conservative rule may remove
useful documentation. Do not weaken it to silently index private contact information.
A reviewer can instead approve a separate public document containing the needed facts.
The implementation indexes no working-tree files, symlinks or submodules.

An explicit network-enabled provisioning command checks GitHub's public visibility,
exact commit and Git tree modes, then fetches only registry paths. No GitHub token is
sent. The resulting manifest is a trusted operator artifact: protect it from edits,
review its hash and do not accept snapshot uploads through an API. Offline indexing
trusts this attestation; it cannot independently re-prove historical public visibility.

```sh
uv run python -m uranus_research_knowledge provision \
  --repository sndcds/uranus-admin --sha FULL_40_CHARACTER_COMMIT_SHA \
  --output /operator/snapshots/admin.json
```

No public web pages are enabled in v1. Future public web sources require an explicit
registry entry, reviewed license, content snapshot and equivalent immutable revision
identity. Arbitrary URLs remain forbidden.

## Collection and reconcile

Provision a local encoder using its existing model/artifact instructions. Use Qdrant
collection-scoped read credentials for serving and separate write credentials only
for the explicit indexer process. Set the service variables described in the README;
never supply Uranus production database credentials to either process.

```sh
uv run python -m uranus_research_knowledge collection-create
uv run python -m uranus_research_knowledge index plan \
  --snapshot /operator/snapshots/admin.json --report /operator/reports/admin-plan.json
uv run python -m uranus_research_knowledge index reconcile \
  --snapshot /operator/snapshots/admin.json --report /operator/reports/admin-applied.json
```

These are instructions, not actions performed by this implementation run. Collection
creation is explicit and will fail rather than replace an existing collection.
Plan reads Qdrant but does not call the encoder or mutate points. Reconcile regenerates
the plan against the current inventory. Reports contain commit, corpus hash, completeness,
excluded paths, point IDs by change category and an `applied` flag set only on success.
Retain source manifests/reports for audit. There is no runtime local state.

Run **one index writer per collection**, enforced by your job supervisor. An index
run is not a transaction across the whole corpus; readers may see multiple source
revisions during a reconcile, and responses disclose them. Failed runs are rerunnable.
For an atomic release in a future version, use an explicitly reviewed collection-alias
migration; v1 does not promise atomic corpus switching or retain all historical points.

Diff states are new, updated, metadata_updated, unchanged and deleted. Unchanged text
reuses its vector even if a unit moves. Revision-only changes overwrite complete
payloads without embedding. Deletes are scoped to one manifest repository and happen
only after successful upserts. Complete means every reviewed path is represented,
including explicit missing paths; partial manifests **never delete unseen points**.
A fetch failure cannot be recorded as a missing file. Bounds: 256 KiB/file,
4 MiB/snapshot, 10,000 chunks/repository, 100-point scroll pages and 64-text embed batches.
A snapshot with Python parse errors aborts; excluded unsafe content is explicitly reported.

Qdrant calls follow its [query API](https://api.qdrant.tech/api-reference/search/query-points),
[scroll API](https://api.qdrant.tech/api-reference/points/scroll-points) and
[payload overwrite API](https://api.qdrant.tech/api-reference/points/overwrite-payload).
No event collection is selected or modified by this service.

## Evidence and source attribution

Each chunk carries source repository, full commit SHA, path, type, heading/symbol,
line interval, content SHA-256, UTC indexed timestamp, source URL, embedding version,
license review status and graph identifiers. URLs pin the revision; line intervals
identify the excerpt. Point IDs are UUIDv5 of repository/path/unit, separate from
revision identity. A payload always represents one revision, not a blend of commits.

A supported fact is a closed intent/value/quote annotation reviewed in `registry.py`.
The exact quote must occur in the retrieved chunk; service validation rejects forged
or removed annotations. Conflicting retrieved values return unsupported. Exactly eleven fact keys are accepted;
`unknown` and an omitted fact are rejected by `/evidence-answer`. Exploratory `/query`
has no fact field. Provenance can be returned without a supported answer.
Infrastructure errors are 503, not an empty successful evidence response.

All knowledge text is untrusted data, including apparent instructions in source files.
No LLM consumes it in v1. Future summarizers must cite excerpts, preserve unsupported
status and never treat retrieval scores as authoritative facts.

The code is AGPL-3.0 under the root LICENSE. Indexed works retain their own licenses.
Source licenses were reviewed at pinned commits in [source-review.md](source-review.md).
The default remains unreviewed/no redistribution. Source policy requires an explicit
redistribution flag and the reviewed commit. New revisions need license review even
when their quotes still validate; facts can remain supported with provenance only.
Stored Chunk `license` fields cannot grant permission. The API never exposes internal
Assertion/GraphAssertion quotes. It includes `chunk_text` only with
`excerpt_included=true`; otherwise that field is absent, not an empty evidence string.

Offline JSON-LD uses the same gate and preserves per-source license identifiers,
license-file links, commit/path/hash/line attribution, ordinary triples and reified
statements linking evidence. Graph evidence identity is revision-qualified; conceptual
node/edge IDs are revision-independent. No global service license is assigned to sources.

```sh
uv run python -m uranus_research_knowledge graph export --format jsonld \
  --snapshot /operator/snapshots/admin.json \
  --snapshot /operator/snapshots/encoder.json \
  --output /operator/graph.jsonld
```

Export accepts at most eight snapshots, one per repository, in any order; partial
snapshots export only available evidence. It reads no live GitHub, encoder or Qdrant
state and needs no service settings/credentials. Repeated identical input yields
identical bytes, independent of clock and snapshot argument order. Unsafe source
files remain excluded by extraction. Retain the original manifests alongside exports.

Authenticated `POST /graph/query` accepts, for example:

```json
{"node":"https://kulturbytes.de/kg/repository/sndcds/uranus-admin","relations":["implements","calls","uses"],"depth":1}
```

Only indexed nodes are known; a canonical absent URI returns 404. Depth is 1–2,
results cap at 50 nodes/100 edges and mark `truncated`; adjacency scan overflow is
503. Provision/reconcile updated payloads before expecting new reviewed graph edges:
old structural-only chunks remain valid but do not acquire reviewed edges at query time.
Serving still uses only read credentials for the dedicated collection.

## Versioned Admin/planner migration

Planner [PR #12](https://github.com/sndcds/uranus-research-planner/pull/12) now uses
model-backed natural-language planning on `/v4/plan`, schema `research-query-plan-v4`,
interpreter `research-domain-planner-v2`, and a configured provider/model (production
candidate `gpt-5.6-terra`). Strict closed structured output is validated before Admin
routing. There is no production catalogue matcher or fallback. Live v4 Terra acceptance
is being validated separately; this Knowledge follow-up makes no live acceptance claim.
Existing `/plan` uses v3.

The first v4 schema executes rank/evidence_answer only. Other operations and optional
node/relation selectors in the architecture are proposals for later versions. Metrics
are allowlisted by entity; catalogued but unimplemented metrics fail validation.

Admin exposes `/api/v1/research/v4/query` behind `RESEARCH_DOMAIN_ENABLED=false` by
default. Opt-in requires its existing planner URL/key. Project answers additionally
require `RESEARCH_KNOWLEDGE_URL=http://127.0.0.1:6336` and a separate
`RESEARCH_KNOWLEDGE_API_KEY`. Existing auth, cookie Origin/CSRF and source read-only
transactions apply. No new migrations/grants are needed. Browser input accepts only
`query`; service routes, collection, model and repository are server-controlled.

Review/merge the companion PRs before any separately authorized rollout. Provision
sources, collection and local encoder; run the four acceptance questions plus unknown
founding date against the staged corpus; check source citations and test failures.
Then opt in server clients. The existing browser UI and v3 endpoint stay available;
a future UI migration must update Nitro allowlists/Zod rendering together and display
unsupported evidence states. Rollback disables v4 without changing v3 execution.
No deployment, browser switch, production indexing or source-data migration was run.

## Initial question coverage

| Project question | Fact intent | Initial support policy |
| --- | --- | --- |
| Was ist Uranus? | uranus_overview | Evidence retrieval; explicit overview assertion review pending |
| Was ist uranus-admin? | admin_overview | Evidence retrieval; overview annotation pending |
| Welches Repository implementiert die semantische Suche? | semantic_search_repository | Reviewed vector retrieval call in Admin semantic_research |
| Welche Komponente erzeugt die Embeddings? | embedding_component | Reviewed encoder README assertion |
| Welches Modell wird für die Embeddings verwendet? | embedding_model | Reviewed encoder README model entry |
| Wo wird Qdrant verwendet? | qdrant_usage | Reviewed Admin documentation, if the document passes the content gate |
| Wie kommuniziert uranus-admin mit dem research-encoder? | encoder_communication | Evidence retrieval; transport annotation pending |
| Welche Komponente interpretiert natürliche Recherchefragen? | planner_component | Reviewed planner README assertion |
| Wo ist das Geocoding implementiert? | geocoding | Evidence retrieval; selected source/annotation review pending |
| Welche Services gehören zur Kulturbytes-Recherchearchitektur? | architecture | Separate graph API provides nine reviewed relations; scalar fact annotation pending |
| Wann wurde Kulturbytes gegründet? | founding_date | No reviewed founding assertion; unsupported |

All these questions have explicit planner routes; an annotation is never manufactured
to make a test or question appear supported. New assertions need their exact source
quote and an assessment that it supports the proposed value.

## Updating license and graph reviews

For a new source revision, inspect the committed license and applicable notices,
then update Source `license`, `license_review_commit`, `license_path`,
`license_content_hash` and `evidence_redistribution_allowed` through code review.
An absent/unclear grant keeps the flag false. Visibility and organization membership
never substitute for a license. The legacy `AGPL-3.0` identifiers for Admin/planner
record the root v3 text without guessing an only/or-later modifier; the encoder's
package explicitly specifies `AGPL-3.0-only`. Model weights keep their own license.

Review graph claims separately from Fact assertions. Register the exact source quote
at an allowlisted repository/path, then verify extraction activates it and materialized
edges reference valid provenance. Quotes spanning extraction windows fail closed.
No request, embedding similarity or LLM can supply these annotations. `implements`
is canonical; do not register its inverse as a second reviewed fact.
