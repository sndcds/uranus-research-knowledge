# Kulturbytes Open Knowledge Research v1

Status: initial design updated for the reviewed graph/license follow-up, 2026-10-01.
No deployment authorized.

## Ownership and trust

The browser submits a question to uranus-admin. Admin calls the authenticated
uranus-research-planner and validates a versioned plan. `domain=data` executes in
Admin against its existing read-only PostgreSQL/PostGIS source connection;
`domain=project_knowledge` calls the new authenticated knowledge service. Admin
owns presentation. Knowledge receives no Uranus database credentials and has no
database driver, ORM, SQL executor, LLM, or runtime GitHub access.

PostgreSQL owns exact cultural data facts. Reviewed public sources own project
facts. Jina supplies representations, Qdrant retrieves candidates, and the planner
interprets questions. None of the latter three establishes truth. Evidence is an
excerpt plus immutable source provenance, never hidden reasoning.

## Versioned migration

Keep planner `/plan` and Admin `/api/v1/research/query` current v3 contracts unchanged. Introduce
planner `/v4/plan` and Admin `/api/v1/research/v4/query`, with schema identifier
`research-query-plan-v4`. V4 uses model-backed natural-language planning with
`interpreter_version=research-domain-planner-v2`, a configured provider/model and
strict closed structured output. The production candidate is `gpt-5.6-terra`.
There is no production catalogue matching or unrestricted fallback. Live v4 Terra
acceptance is still being validated separately, not established by Knowledge tests.

Natural-language question → model-backed closed planner → Admin routes:
`data` → PostgreSQL; `project_knowledge` → Knowledge service. Knowledge has no LLM,
production database access or runtime GitHub crawling.

Data plans contain `domain`, `operation=rank`, `entity_type`, an entity-compatible
`metric`, `ordering`, `limit`, and optional `area_query`. Project plans contain
`domain`, `operation=evidence_answer`, a closed `fact`, `knowledge_query` and
`answer_mode=evidence`. Graph queries are a separate internal Knowledge API;
planner graph selectors are not implemented. SQL, URLs, paths,
collections and executors are never plan fields. The broader operation vocabulary
is lookup/list/count/aggregate/rank/compare/traverse/semantic_search/evidence_answer;
unsupported combinations are reserved for later versions, not silently executed.

## Exact metrics

Closed catalogue (catalogued does not mean executable):

| Entity | Metrics |
| --- | --- |
| event | description_characters, description_words, public_text_characters, occurrence_count, duration_minutes |
| venue | event_count, occurrence_count, organization_count, category_count |
| organization | event_count, occurrence_count, venue_count, area_count, category_count |
| area | event_count, venue_count, organization_count, events_per_capita |
| category | event_count |

Initially execute event description_characters/occurrence_count, organization
event_count/venue_count, venue occurrence_count, and category event_count.
Count distinct source event/occurrence/venue identifiers over the complete shared
eligible Research population; preserve effective occurrence venue inheritance,
public status gates and area resolution. Stable ties use source identifiers.

`description_characters` uses the public event description projected through
Research's existing `semantic_documents.public_clean`: HTML hidden elements removed,
entities decoded, NFC normalization, public-text redaction and whitespace
normalization. Python `len` counts Unicode code points, not UTF-8 bytes or
graphemes. Markdown delimiters remain text under this explicitly chosen existing
projection (it is not a Markdown renderer). NULL projects to empty text. Exact
ranking may perform bounded projection in Admin after PostgreSQL selection; an
overflow fails rather than returning a top result from an incomplete population.
No Qdrant candidate set may establish an exact metric.

Other catalogue metrics need separately reviewed semantics: duration with multiple
occurrences and missing ends; public-text field coverage; population reference
date/source for per-capita measures; area membership and category distinctness.
They must fail closed until implemented.

## Knowledge vocabulary v1

Project node types: project, repository, component, service, document, source_file,
symbol, api_endpoint, feature, model, datastore, deployment_component.
Conceptual data types: event, occurrence, venue, space, organization, category,
genre, area. Data nodes remain in PostgreSQL; there is no bulk graph copy.

Allowed relations and their intended endpoints:

| Subject | Relation | Object |
| --- | --- | --- |
| organization | organizes | event |
| event | has_occurrence | occurrence |
| occurrence | occurs_at | venue |
| occurrence | uses_space | space |
| event | has_category | category |
| event | has_genre | genre |
| venue | located_in | area |
| project / repository | contains | repository / source_file |
| source_file | defines | symbol |
| repository / component / service / deployment_component | implements | feature |
| same actors | calls | component / service / api_endpoint |
| same actors | uses | datastore / component / service / model |
| same actors | uses_model | model |
| same actors | reads_from / writes_to | datastore |
| same actors | exposes | api_endpoint |
| any node type | documented_by | document |
| component / service / deployment_component | part_of | project |
| api_endpoint | implemented_by | symbol |

Stable conceptual node URI: `https://kulturbytes.de/kg/{type}/{identifier}`;
repository example: `https://kulturbytes.de/kg/repository/sndcds/uranus-admin`.
Edge identity hashes subject, allowlisted predicate and object. Evidence and source
revision qualify assertions separately. Deterministic source extraction can create
containment/definition edges; other assertions require reviewed annotations with
verbatim source excerpts. No LLM creates arbitrary edges.

Offline JSON-LD export maps the closed vocabulary to stable URIs and reified
statements with revision-qualified evidence IDs. Ordering is deterministic and the
export does not instantiate upstream clients. No triple store or publication is involved.
`implements` is canonical; the redundant `implemented_in` inverse is not retained.
`documented_by` similarly replaces the unused `documents` inverse.
Source licensing is retained per repository; public visibility is not permission
to relicense. Review each source license before distributing excerpts or an export.
The repository license applies to service code, not automatically to indexed works.

## Sources and provisioning

Fixed initial registry: sndcds/uranus, uranus-admin, uranus-research-planner,
uranus-research-encoder, pluto, uranus-dashboard, uranus-widget, kulturbytes-client.
Registry changes are explicit code-review changes. Each source has exact reviewed
paths, pinned license attribution, reviewed fact annotations and separate GraphAssertions. README/docs,
manifests, compose, OpenAPI, unit files and selected code are eligible categories,
not permission to recursively index every file. Provisioning uses committed blobs
at an explicit SHA, never working-tree files, symlinks or submodules. Public GitHub
visibility is verified during explicit fetch; offline reuse requires a recorded
public-source attestation. No private repository support in v1.

Security deny checks supplement the positive path allowlist: dot-env, credentials,
key files, secret-like content, generated configuration, account data and private
email are excluded. Reviewed source paths and annotations are the primary boundary;
heuristic secret detection cannot certify arbitrary content safe.

Deterministic extraction preserves headings/line intervals; selected Python code
uses AST module/class/function units, other selected text uses bounded blocks.
Every chunk includes repository, full commit SHA, path, document_type,
heading_or_symbol, commit-pinned source_url, SHA-256 content_hash, indexed_at,
and line bounds, plus language/symbol/component/service where applicable.

## Index and reconciliation

Dedicated collection: `kulturbytes_project_knowledge_jina_v3_v1`, unnamed 1024-D
Cosine vectors. Reuse encoder `POST /embed`, model `jina-v3`, kind `passage` for
indexing and `query` for search. Pin and validate embedding_version, vector count,
dimension, finiteness and norm. Never write project chunks to event collections.

Payload includes knowledge_type, all provenance, chunk_text, embedding_version,
graph_node_ids, graph_edge_ids, owner/schema version and reviewed assertions.
Logical point IDs are UUIDv5(repository/path/unit). Revision-bound provenance is
replaced as a complete payload and never synthesized from a different revision.
Git history remains the immutable source; this operational collection retains the
latest indexed revision, not a historical archive.

CLI: `python -m uranus_research_knowledge index plan|reconcile`. A snapshot manifest
records source SHAs, corpus hash, reviewed paths and completeness. Diff categories:
new, updated text, metadata_updated, unchanged, deleted. Reuse existing vectors
when text and embedding version match; indexed_at does not cause churn. Complete
snapshots may delete stale points only in their own repository scope, after all
upserts succeed. Partial snapshots never delete unseen points. Abort on extraction
or upstream errors; do not promote an incomplete extraction to complete. One writer
per collection is an operator precondition; no automatic background indexing.

## Evidence API and factual support

`POST /query` accepts only bounded query and limit and returns ranked source
license-gated excerpts/provenance with source nodes. `POST /evidence-answer` accepts a bounded
query and a required closed fact intent (exactly eleven FactKeys; no `unknown`). Both are authenticated internal calls. Responses
identify indexed commits and `authoritative_source=project_sources`.

For v1, supported facts come exclusively from reviewed, typed source annotations
whose exact quotation occurs in a retrieved chunk at that revision. Search
similarity alone cannot establish a fact. A conflicting set of fact values fails
closed. Unsupported answers still expose retrieved evidence about what is known.
General questions can return provenance without claiming a synthesized factual answer.
Public Evidence is distinct from internal Chunk: quote-bearing assertion lists are never
serialized. Unapproved revisions return `evidence_available=true`,
`excerpt_included=false`, and no `chunk_text`. The Source registry alone decides
redistribution; stored payload labels and request fields cannot enable it.
Founding date requires an explicit founding assertion; a GitHub creation date,
first commit or first release is never substituted.

Data answers contain records/value, metric, filters, observed_at and
`authoritative_source=postgresql`. Project answers contain supported, typed facts,
evidence and indexed_commits. Do not return unrestricted generated prose.

## Runtime security and availability

Service-token authentication with constant-time comparison, no CORS, strict
extra-forbid schemas, bounded streaming request/response bodies, deadlines and
concurrency. Query service can access only configured encoder and Qdrant origins;
no request can change origin, collection or repository. Disable environment
proxies and redirects, never forward browser credentials. No request/source text
or secrets in logs or errors. Separate read-only Qdrant runtime credentials from
indexer write credentials. No production database configuration is accepted.

Offline means operation using preprovisioned local encoder/model and Qdrant, with
no internet required by this service. First-time model provisioning belongs to
the existing encoder. Infrastructure failure is an error, not supported=false.

## Acceptance and rollout

Synthetic source fixtures and HTTP transports verify reproducibility, provenance,
complete/partial deletion, metadata-only reuse, source rejection and unsupported
facts. Planner fixtures cover DE/EN/DA; Admin tests verify server-side domain
routing and exact PostgreSQL metrics using a disposable test database.

1. Longest event description -> data/rank/event/description_characters/desc/1.
2. Most events by organization -> data/rank/organization/event_count/desc/1.
3. Semantic-search repository -> project_knowledge/evidence_answer; a repository
   fact is supported only by a retrieved reviewed assertion.
4. Event embedding producer -> project_knowledge/evidence_answer; same rule for
   the encoder component. Unknown founding date -> supported=false.

Review and merge separate service/planner/Admin changes. Provision public source
snapshots and reviewed assertions, provision the isolated collection and encoder,
run plan then reconcile, test authenticated internal endpoints, then opt clients
into v4. Keep v3 available during migration. Browser presentation can migrate
after contract review; no existing UI is silently switched. Rollback disables v4
configuration without affecting existing data Research. Deployments, real indexing,
publication and production credential access are outside this implementation run.

## Reviewed graph API

GraphAssertion is a separate closed model registered by repository/path. It contains
closed subject/object node types, stable identifiers, a Relation enum and an exact
reviewed quote. Only matching indexed chunks activate an assertion. Structural
repository→source_file `contains` and source_file→symbol `defines` are exclusively
extraction-derived. Location, names, similarity and models cannot add project edges.

GraphNode carries URI/type; GraphEdge carries deterministic subject/predicate/object
identity, structural/reviewed kind and nonempty evidence IDs. GraphEvidence retains
commit/path/hash/line provenance under the same license gate. Logical edge IDs omit
commit SHA; graph evidence IDs include revision, content and line bounds. Identical
positive assertions coalesce and combine provenance. Relations are multivalued: two
reviewed `uses_model` targets do not assert exclusivity. Negative assertions and
free-form predicates are unsupported. Conflicting payloads for one point/revision
fail closed; unlike single-valued Fact assertions, the graph never picks a winner
between distinct positive relations. A reviewer must resolve any semantic contradiction
before registering it; this positive vocabulary cannot encode negation or exclusivity.

`POST /graph/query` accepts only `node`, `relations` and `depth` (1–2). It traverses
incoming and outgoing neighbours while preserving canonical edge direction. Omitted
or empty relations mean all closed predicates. Malformed/unsafe URIs and unknown
predicates return 422; a syntactically valid URI absent from the active index returns
404 `unknown_node`. An indexed node with no matching relation returns itself and no edges.
No request-controlled repository/path/URL or graph mutations are accepted.

Each response contains at most 50 nodes, 100 edges and 1,000 evidence records.
Deterministic edge-ID ordering selects a bounded subgraph; `truncated=true` discloses
output truncation. Qdrant adjacency scans use owner/version/node filters, 100-point
pages and a 1,000-chunk scan budget; overflow or invalid upstream data is 503, never
a falsely complete graph. There is no encoder call for graph queries.

Edges are views over validated chunk payloads, with no independent graph store to
reconcile. Quote removal updates/removes corresponding edges, unchanged facts retain
IDs, partial snapshots do not delete unseen facts, and deletions follow successful
writes. A reconcile is not atomic: existing single-writer/mixed-revision caveats apply.
See [source review](source-review.md) for the nine initially activated architecture
relations and explicitly missing evidence. The German architecture question can be
presented from these structured facts; absent links remain absent.
