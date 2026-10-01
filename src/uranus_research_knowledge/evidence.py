from .models import AnswerResponse, Chunk, Evidence, Fact, Match, Node, QueryResponse
from .registry import REGISTRY
from .vocabulary import NodeType, node_uri


def public_evidence(chunk: Chunk, model=Evidence):
    # Revalidate at the release boundary. Stored payload license flags never grant access.
    chunk = Chunk.model_validate(chunk.model_dump())
    license_id, allowed, license_url = REGISTRY[chunk.repository].evidence_policy(
        chunk.repository, chunk.commit_sha
    )
    return model(
        id=chunk.point_id,
        repository=chunk.repository,
        path=chunk.path,
        commit_sha=chunk.commit_sha,
        source_url=chunk.source_url,
        content_hash=chunk.content_hash,
        line_start=chunk.line_start,
        line_end=chunk.line_end,
        license=license_id,
        license_source_url=license_url,
        evidence_redistribution_allowed=allowed,
        excerpt_included=allowed,
        chunk_text=chunk.chunk_text if allowed else None,
        graph_edge_ids=chunk.graph_edge_ids,
    )


async def query(client, request):
    hits = await client.search(request.query, request.limit)
    return QueryResponse(
        query=request.query,
        matches=[
            Match(
                score=score,
                node=Node(type=NodeType.repository, id=node_uri(NodeType.repository, c.repository)),
                evidence=[public_evidence(c)],
            )
            for score, c in hits
        ],
    )


async def answer(client, request):
    hits = await client.search(request.query, request.limit)
    evidence = []
    supported = {}
    commits = {}
    for _, chunk in hits:
        evidence.append(public_evidence(chunk))
        commits.setdefault(chunk.repository, set()).add(chunk.commit_sha)
        for assertion in chunk.assertions:
            if assertion.fact == request.fact:
                supported.setdefault(assertion.value, []).append(chunk.point_id)
    facts = (
        [
            Fact(key=request.fact, value=value, evidence_ids=sorted(set(ids)))
            for value, ids in supported.items()
        ]
        if len(supported) == 1
        else []
    )
    return AnswerResponse(
        supported=bool(facts),
        facts=facts,
        evidence=evidence,
        indexed_commits={k: sorted(v) for k, v in sorted(commits.items())},
        reason="supported"
        if facts
        else "conflicting_evidence"
        if supported
        else "no_explicit_evidence",
    )
