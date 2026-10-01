"""Evidence-only materialization, bounded adjacency traversal and offline JSON-LD."""

import json
from hashlib import sha256

from .clients import UpstreamError
from .evidence import public_evidence
from .models import (
    Chunk,
    GraphEdge,
    GraphEvidence,
    GraphNode,
    GraphQueryResponse,
    chunk_graph,
)
from .vocabulary import BASE, VERSION, Relation, edge_id, node_type

MAX_QUERY_CHUNKS = 1000


class UnknownNode(Exception):
    pass


def materialize(chunks):
    nodes, edges, evidence, points = {}, {}, {}, {}
    for raw in chunks:
        chunk = Chunk.model_validate(raw.model_dump())
        if chunk.point_id in points and points[chunk.point_id] != chunk:
            raise ValueError("conflicting_point_revisions")
        points[chunk.point_id] = chunk
        item = public_evidence(chunk, GraphEvidence)
        identity = sha256(
            f"{chunk.point_id}\n{chunk.commit_sha}\n{chunk.content_hash}\n"
            f"{chunk.line_start}\n{chunk.line_end}".encode()
        ).hexdigest()
        item = item.model_copy(update={"id": identity})
        if item.id in evidence and evidence[item.id] != item:
            raise ValueError("conflicting_point_revisions")
        evidence[item.id] = item
        ids, _, triples = chunk_graph(
            chunk.repository, chunk.path, chunk.symbol, chunk.graph_assertions
        )
        for uri in ids:
            nodes[uri] = GraphNode(id=uri, type=node_type(uri))
        for subject, predicate, target in triples:
            identity = edge_id(subject, predicate, target)
            structural = predicate == Relation.defines or (
                predicate == Relation.contains and node_type(subject) == "repository"
            )
            previous = edges.get(identity)
            refs = sorted(set((previous.evidence_ids if previous else []) + [item.id]))
            edges[identity] = GraphEdge(
                id=identity,
                subject=subject,
                predicate=predicate,
                object=target,
                evidence_ids=refs,
                kind="structural" if structural else "reviewed",
            )
    return (
        [nodes[k] for k in sorted(nodes)],
        [edges[k] for k in sorted(edges)],
        [evidence[k] for k in sorted(evidence)],
    )


async def graph_query(client, request):
    # Undirected neighbourhood traversal preserves the canonical edge direction.
    frontier = {request.node}
    visited = set()
    selected_nodes = {request.node}
    selected_edges = set()
    chunks = {}
    truncated = False
    for _ in range(request.depth):
        incoming = await client.graph_chunks(sorted(frontier))
        for chunk in incoming:
            if chunk.point_id in chunks and chunks[chunk.point_id] != chunk:
                raise UpstreamError("graph_revision_changed")
            chunks[chunk.point_id] = chunk
        if len(chunks) > MAX_QUERY_CHUNKS:
            raise UpstreamError("graph_scan_limit")
        nodes, edges, evidence = materialize(chunks.values())
        if not visited and request.node not in {n.id for n in nodes}:
            raise UnknownNode()
        visited.update(frontier)
        for edge in edges:
            if request.relations and edge.predicate not in request.relations:
                continue
            endpoints = {edge.subject, edge.object}
            if not endpoints & frontier:
                continue
            if edge.id not in selected_edges and (
                len(selected_edges) >= 100 or len(selected_nodes | endpoints) > 50
            ):
                truncated = True
                continue
            selected_edges.add(edge.id)
            selected_nodes.update(endpoints)
        frontier = selected_nodes - visited
        if not frontier:
            break
    result_edges = [e for e in edges if e.id in selected_edges]
    refs = {i for e in result_edges for i in e.evidence_ids}
    return GraphQueryResponse(
        nodes=[n for n in nodes if n.id in selected_nodes],
        edges=result_edges,
        evidence=[e for e in evidence if e.id in refs],
        truncated=truncated,
    )


def export_jsonld(chunks) -> str:
    nodes, edges, evidence = materialize(chunks)

    def evidence_uri(identity):
        return BASE + "evidence/" + identity

    records = {n.id: {"@id": n.id, "@type": BASE + n.type.value} for n in nodes}
    for edge in edges:
        # Both ordinary RDF links and reified statements with explicit provenance.
        records[edge.subject].setdefault(edge.predicate.value, []).append({"@id": edge.object})
        records[edge.id] = {
            "@id": edge.id,
            "@type": "rdf:Statement",
            "rdf:subject": {"@id": edge.subject},
            "rdf:predicate": {"@id": BASE + edge.predicate.value},
            "rdf:object": {"@id": edge.object},
            "kind": edge.kind,
            "evidence": [{"@id": evidence_uri(i)} for i in edge.evidence_ids],
        }
    for item in evidence:
        data = item.model_dump(exclude={"id", "graph_edge_ids"}, exclude_none=True)
        records[evidence_uri(item.id)] = {
            "@id": evidence_uri(item.id),
            "@type": BASE + "Evidence",
            **data,
        }
    for record in records.values():
        for key, value in record.items():
            if isinstance(value, list):
                record[key] = sorted(value, key=lambda x: json.dumps(x, sort_keys=True))
    return (
        json.dumps(
            {
                "@context": {
                    "@vocab": BASE,
                    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                    "source_url": {
                        "@id": "http://www.w3.org/ns/prov#wasDerivedFrom",
                        "@type": "@id",
                    },
                    "license_source_url": {
                        "@id": "http://purl.org/dc/terms/license",
                        "@type": "@id",
                    },
                },
                "@id": BASE + "export/" + VERSION,
                "@graph": [records[k] for k in sorted(records)],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
