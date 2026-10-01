from .models import AnswerResponse, Fact, Match, Node, QueryResponse
from .vocabulary import NodeType, node_uri


async def query(client, request):
    hits = await client.search(request.query, request.limit)
    return QueryResponse(
        query=request.query,
        matches=[
            Match(
                score=score,
                node=Node(type=NodeType.repository, id=node_uri(NodeType.repository, c.repository)),
                evidence=[c],
            )
            for score, c in hits
        ],
    )


async def answer(client, request):
    found = await query(client, request)
    evidence = [m.evidence[0] for m in found.matches]
    supported = {}
    commits = {}
    for chunk in evidence:
        commits.setdefault(chunk.repository, set()).add(chunk.commit_sha)
        for assertion in chunk.assertions:
            if assertion.fact == request.fact and request.fact != "unknown":
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
