# Reviewed sources, graph assertions and redistribution — 2026-10-01

Review used the public default branches at the exact commits below, fetched explicitly
as an operator review. No runtime fetching, production indexing, or companion edits
were performed. Source annotations apply only when their exact quote survives the
indexed file/chunk content gate. The current source review predates merging the
companion v4 PRs; current v4 architecture wording follows those PRs, not an invented
v4 source graph edge.

## License review

| Repository | Reviewed commit | Recorded license | Excerpts allowed at this commit | Evidence |
| --- | --- | --- | --- | --- |
| sndcds/kulturbytes-client | `887e45ef953682461fc773327763d8e8581f5fec` | UNREVIEWED: no redistribution grant | no | [tree](https://github.com/sndcds/kulturbytes-client/tree/887e45ef953682461fc773327763d8e8581f5fec), [package.json](https://github.com/sndcds/kulturbytes-client/blob/887e45ef953682461fc773327763d8e8581f5fec/package.json) |
| sndcds/pluto | `f89c20d0695cf60e8c9dd31a5fa48462fb7bcbe1` | CC0-1.0 | yes | [LICENSE](https://github.com/sndcds/pluto/blob/f89c20d0695cf60e8c9dd31a5fa48462fb7bcbe1/LICENSE) |
| sndcds/uranus-admin | `2f0f6349a94d90e613dd1728371fedcec3ac4fb7` | AGPL-3.0 | yes | [LICENSE](https://github.com/sndcds/uranus-admin/blob/2f0f6349a94d90e613dd1728371fedcec3ac4fb7/LICENSE) |
| sndcds/uranus-dashboard | `87658dc2ff8d1492c6e0158afd57e59d428c6451` | CC0-1.0 | yes | [LICENSE](https://github.com/sndcds/uranus-dashboard/blob/87658dc2ff8d1492c6e0158afd57e59d428c6451/LICENSE) |
| sndcds/uranus-research-encoder | `48ce71550d5dad8c697facd3767aef8b4be97cc1` | AGPL-3.0-only | yes | [LICENSE](https://github.com/sndcds/uranus-research-encoder/blob/48ce71550d5dad8c697facd3767aef8b4be97cc1/LICENSE) |
| sndcds/uranus-research-planner | `c10b1920c3a4af67a60b9d4ce5a807dbf11fe1f4` | AGPL-3.0 | yes | [LICENSE](https://github.com/sndcds/uranus-research-planner/blob/c10b1920c3a4af67a60b9d4ce5a807dbf11fe1f4/LICENSE) |
| sndcds/uranus-widget | `c42f265cb549c31647800d6e6f1df39908c00f7f` | CC0-1.0 | yes | [LICENSE](https://github.com/sndcds/uranus-widget/blob/c42f265cb549c31647800d6e6f1df39908c00f7f/LICENSE) |
| sndcds/uranus | `ce426a0f9b2d4c79f81a0ccd291999406cddfa11` | CC0-1.0 | yes | [LICENSE](https://github.com/sndcds/uranus/blob/ce426a0f9b2d4c79f81a0ccd291999406cddfa11/LICENSE) |

The four CC0 files contain the CC0 1.0 Universal legal text. Admin and planner
contain the GNU Affero GPL version 3 text, with no reviewed project-specific
only/or-later declaration; `AGPL-3.0` records that legacy identifier without inventing
its modifier. Encoder explicitly sets `AGPL-3.0-only` in its
[package metadata](https://github.com/sndcds/uranus-research-encoder/blob/48ce71550d5dad8c697facd3767aef8b4be97cc1/pyproject.toml).
The presence of “or later” in the license's application example is not a separate
project grant. Redistribution approval is for the reviewed, allowlisted source
excerpts under the recorded license, not for model weights or arbitrary repository
content. Existing attribution/license terms continue to apply.

`kulturbytes-client` has no root license file or package license declaration, so it
remains unreviewed and its excerpts are withheld. Organization membership and public
visibility confer no policy. Root license file hashes, paths and revisions are recorded
in Source metadata. No fetched source corpus is committed in this PR.

Every other revision defaults to no redistribution until reviewed, even if it uses
the same source path or a valid unchanged graph quote. API and JSON-LD still expose
fact/graph metadata, commit-pinned source URL, hashes and line ranges. Internal source
quotes may establish support without appearing in public evidence. The service's
own code license is never assigned to source excerpts or the entire graph export.

## Activated reviewed edges

All identifiers below expand under `https://kulturbytes.de/kg/`. Source ranges refer
to the indexed chunk containing the exact registered quote; the registry contains
the exact quotes and tests independently validate inclusion/removal behavior.

| Subject | Predicate | Object | Reviewed evidence |
| --- | --- | --- | --- |
| project/kulturbytes | contains | repository/sndcds/uranus-admin | Admin README lines 3–8: describes Admin as the dashboard for Kulturbytes/Uranus |
| repository/sndcds/uranus-admin | implements | feature/semantic-search | Admin semantic_search.py lines 83–94: actual awaited vector search in semantic_research |
| repository/sndcds/uranus-admin | uses | datastore/qdrant | Same actual Qdrant search call |
| project/kulturbytes | contains | repository/sndcds/uranus-research-planner | Planner README lines 3–6: language interpretation service for Kulturbytes |
| component/research-planner | implements | feature/natural-language-research-planning | Same explicit translation to a closed, validated ResearchQueryPlan |
| component/research-planner | part_of | project/kulturbytes | Same explicit service-for-Kulturbytes statement |
| project/kulturbytes | contains | repository/sndcds/uranus-research-encoder | Encoder README lines 3–7: standalone internal service for the Kulturbytes/Uranus research stack |
| component/research-encoder | part_of | project/kulturbytes | Same explicit stack membership statement |
| component/research-encoder | uses_model | model/jinaai/jina-embeddings-v3-hf | Encoder README lines 28–38: model repository table entry |

Pinned graph source links:

- [Admin README](https://github.com/sndcds/uranus-admin/blob/2f0f6349a94d90e613dd1728371fedcec3ac4fb7/README.md#L3-L8)
- [Admin semantic search](https://github.com/sndcds/uranus-admin/blob/2f0f6349a94d90e613dd1728371fedcec3ac4fb7/backend/app/services/semantic_search.py#L83-L94)
- [Planner README](https://github.com/sndcds/uranus-research-planner/blob/c10b1920c3a4af67a60b9d4ce5a807dbf11fe1f4/README.md#L3-L6)
- [Encoder README introduction](https://github.com/sndcds/uranus-research-encoder/blob/48ce71550d5dad8c697facd3767aef8b4be97cc1/README.md#L3-L7)
- [Encoder model entry](https://github.com/sndcds/uranus-research-encoder/blob/48ce71550d5dad8c697facd3767aef8b4be97cc1/README.md#L28-L38)

No relation comes solely from naming or location: the project membership quotes
explicitly identify Kulturbytes and the components' roles. The semantic-search edge
uses the same reviewed implementation evidence as the existing Fact assertion.
There is no reviewed inverse `implemented_in`; `implements` is canonical.

Offline extraction of these eight snapshots produced 267 chunks, 25 nodes and 20
edges (11 structural, nine reviewed). These counts describe local source review,
not a deployed index. Uranus README and Admin backend README are excluded as whole
files by the existing secret/contact-content gate. Their text cannot activate edges.

## Missing candidates

| Candidate relation | State | Needed evidence/documentation |
| --- | --- | --- |
| Admin/semantic search calls research-encoder | missing_reviewed_evidence | Indexed semantic code calls an Encoder abstraction but does not identify research-encoder; add explicit service identity/transport documentation in a safe allowlisted file, or separately review transport implementation |
| Admin calls research-planner in v4 | missing_reviewed_evidence | Current default-branch backend README fails the content gate; review a safe explicit v4 architecture document after companion changes |
| Direct planner↔encoder relation | missing_reviewed_evidence | No explicit call/dependency; encoder README says it does not know the planner. Do not assume a direct link |
| Project contains the other five repositories | missing_reviewed_evidence | No reviewed indexed quote registered establishing project membership; review explicit membership documentation in each source |
| Components part_of a distinct named research-architecture node | missing_reviewed_evidence | Sources support membership in Kulturbytes, not a separately defined architecture entity; review explicit architecture identity before adding it |
| Founding date | missing_reviewed_evidence | Explicit reviewed historical source required; repository creation/commit dates do not qualify |

The architecture question “Wie hängen uranus-admin, research-planner und
research-encoder zusammen?” can use project membership and supported roles from the
structured graph. It must not invent direct service links or call order. Presentation
and any later prose rendering belong to Admin, outside this task.
