"""Bounded wire and payload contracts. Source text is evidence, never instructions."""

from datetime import datetime
from hashlib import sha256
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID, uuid5

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from .vocabulary import NodeType, Relation, edge_id, node_type, node_uri

COLLECTION = "kulturbytes_project_knowledge_jina_v3_v1"
OWNER = "kulturbytes-project-knowledge-v1"
EMBEDDING_VERSION = (
    "d18862d9a48706220815554fac3ebb4dfa46fc28:"
    "native-transformers5.17.0-retrieval-normalized-f32:sections-480-overlap64-v2"
)
NAMESPACE = UUID("d6fa44cd-33ca-48e9-9a15-29b5f0c52229")
FactKey = Literal[
    "uranus_overview",
    "admin_overview",
    "semantic_search_repository",
    "embedding_component",
    "embedding_model",
    "qdrant_usage",
    "encoder_communication",
    "planner_component",
    "geocoding",
    "architecture",
    "founding_date",
]
QueryText = Annotated[str, StringConstraints(min_length=1, max_length=2000, strip_whitespace=True)]


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)


class Assertion(Closed):
    fact: FactKey
    value: str = Field(min_length=1, max_length=500)
    quote: str = Field(min_length=1, max_length=480)


class GraphAssertion(Closed):
    subject_type: NodeType
    subject_id: str = Field(min_length=1, max_length=1000)
    predicate: Relation
    object_type: NodeType
    object_id: str = Field(min_length=1, max_length=1000)
    quote: str = Field(min_length=1, max_length=480)

    @property
    def subject(self) -> str:
        return node_uri(self.subject_type, self.subject_id)

    @property
    def object(self) -> str:
        return node_uri(self.object_type, self.object_id)

    @property
    def id(self) -> str:
        return edge_id(self.subject, self.predicate, self.object)

    @model_validator(mode="after")
    def valid_edge(self):
        edge_id(self.subject, self.predicate, self.object)
        # Structural extraction is the sole authority for these pairs.
        if self.predicate == Relation.defines or (
            self.predicate == Relation.contains and self.subject_type == NodeType.repository
        ):
            raise ValueError("structural_assertion_forbidden")
        return self


def chunk_graph(repository, path, symbol, assertions):
    repo = node_uri(NodeType.repository, repository)
    file = node_uri(NodeType.source_file, f"{repository}/{path}")
    triples = [(repo, Relation.contains, file)]
    if symbol:
        triples.append(
            (file, Relation.defines, node_uri(NodeType.symbol, f"{repository}/{path}/{symbol}"))
        )
    triples.extend((a.subject, a.predicate, a.object) for a in assertions)
    nodes = list(dict.fromkeys(n for s, _, o in triples for n in (s, o)))
    edges = list(dict.fromkeys(edge_id(s, p, o) for s, p, o in triples))
    return nodes, edges, triples


class Chunk(Closed):
    index_owner: Literal["kulturbytes-project-knowledge-v1"] = "kulturbytes-project-knowledge-v1"
    schema_version: Literal["project-chunk-v1"] = "project-chunk-v1"
    knowledge_type: Literal["project_knowledge"] = "project_knowledge"
    repository: str = Field(pattern=r"^sndcds/[a-z0-9-]+$")
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    path: str = Field(min_length=1, max_length=500)
    document_type: Literal["documentation", "source_code", "configuration"]
    heading_or_symbol: str = Field(max_length=500)
    unit: str = Field(max_length=600)
    source_url: str = Field(max_length=1100)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    indexed_at: datetime
    chunk_text: str = Field(min_length=1, max_length=480)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    language: str | None = Field(default=None, max_length=40)
    symbol: str | None = Field(default=None, max_length=500)
    component: str | None = Field(default=None, max_length=100)
    service: str | None = Field(default=None, max_length=100)
    license: str = Field(max_length=100)
    embedding_version: str = EMBEDDING_VERSION
    graph_node_ids: list[str] = Field(max_length=50)
    graph_edge_ids: list[str] = Field(default_factory=list, max_length=100)
    graph_assertions: list[GraphAssertion] = Field(default_factory=list, max_length=20)
    assertions: list[Assertion] = Field(default_factory=list, max_length=12)

    @property
    def point_id(self) -> str:
        return str(uuid5(NAMESPACE, f"{self.repository}\n{self.path}\n{self.unit}"))

    @model_validator(mode="after")
    def provenance(self):
        from .registry import REGISTRY, safe_path, safe_text

        if (
            self.repository not in REGISTRY
            or not safe_path(self.path)
            or not safe_text(self.chunk_text)
        ):
            raise ValueError("invalid_source")
        if self.path not in REGISTRY[self.repository].paths:
            raise ValueError("unreviewed_path")
        nodes, edges, _ = chunk_graph(
            self.repository, self.path, self.symbol, self.graph_assertions
        )
        if self.graph_node_ids != nodes or self.graph_edge_ids != edges:
            raise ValueError("invalid_graph_provenance")
        if self.embedding_version != EMBEDDING_VERSION:
            raise ValueError("invalid_embedding_version")
        expected = (
            f"https://github.com/{self.repository}/blob/{self.commit_sha}/"
            f"{quote(self.path, safe='/')}"
        )
        if self.source_url != expected or self.line_end < self.line_start:
            raise ValueError("invalid_provenance")
        if (
            self.indexed_at.tzinfo is None
            or sha256(self.chunk_text.encode()).hexdigest() != self.content_hash
        ):
            raise ValueError("invalid_content_hash_or_timestamp")
        reviewed = REGISTRY[self.repository].assertions.get(self.path, ())
        if any(a.quote not in self.chunk_text or a not in reviewed for a in self.assertions):
            raise ValueError("unreviewed_assertion")
        graph_reviewed = REGISTRY[self.repository].graph_assertions.get(self.path, ())
        if any(
            a.quote not in self.chunk_text or a not in graph_reviewed for a in self.graph_assertions
        ):
            raise ValueError("unreviewed_graph_assertion")
        return self


class Evidence(Closed):
    """Public provenance projection: never serialize internal assertion quotes."""

    id: str
    repository: str
    path: str
    commit_sha: str
    source_url: str
    content_hash: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    license: str
    license_source_url: str | None = None
    evidence_available: Literal[True] = True
    evidence_redistribution_allowed: bool
    excerpt_included: bool
    chunk_text: str | None = Field(default=None, min_length=1, max_length=480)
    graph_edge_ids: list[str] = Field(max_length=100)

    @model_validator(mode="after")
    def excerpt_policy(self):
        if self.excerpt_included != (self.chunk_text is not None):
            raise ValueError("invalid_excerpt_status")
        if self.excerpt_included and not self.evidence_redistribution_allowed:
            raise ValueError("excerpt_redistribution_forbidden")
        return self


class GraphEvidence(Evidence):
    pass


class QueryRequest(Closed):
    query: QueryText
    limit: int = Field(default=10, ge=1, le=20, strict=True)


class AnswerRequest(QueryRequest):
    fact: FactKey


class GraphNode(Closed):
    id: str
    type: NodeType

    @model_validator(mode="after")
    def valid_uri(self):
        if node_type(self.id) != self.type:
            raise ValueError("node_type_mismatch")
        return self


Node = GraphNode


class GraphEdge(Closed):
    id: str
    subject: str
    predicate: Relation
    object: str
    evidence_ids: list[str] = Field(min_length=1, max_length=10000)
    kind: Literal["structural", "reviewed"]

    @model_validator(mode="after")
    def identity(self):
        if self.id != edge_id(self.subject, self.predicate, self.object):
            raise ValueError("invalid_edge_id")
        structural = self.predicate == Relation.defines or (
            self.predicate == Relation.contains and node_type(self.subject) == NodeType.repository
        )
        if (self.kind == "structural") != structural:
            raise ValueError("invalid_edge_kind")
        return self


class GraphQueryRequest(Closed):
    node: str = Field(min_length=1, max_length=3200)
    relations: list[Relation] = Field(default_factory=list, max_length=len(Relation))
    depth: int = Field(default=1, ge=1, le=2, strict=True)

    @field_validator("node")
    @classmethod
    def valid_node(cls, value):
        node_type(value)
        return value


class GraphQueryResponse(Closed):
    nodes: list[GraphNode] = Field(max_length=50)
    edges: list[GraphEdge] = Field(max_length=100)
    evidence: list[GraphEvidence] = Field(max_length=1000)
    truncated: bool = False

    @model_validator(mode="after")
    def integrity(self):
        nodes = {n.id for n in self.nodes}
        evidence = {e.id: e for e in self.evidence}
        if len(nodes) != len(self.nodes) or len(evidence) != len(self.evidence):
            raise ValueError("duplicate_graph_identity")
        if len({e.id for e in self.edges}) != len(self.edges):
            raise ValueError("duplicate_graph_edge")
        for edge in self.edges:
            if edge.subject not in nodes or edge.object not in nodes:
                raise ValueError("missing_edge_node")
            if any(
                i not in evidence or edge.id not in evidence[i].graph_edge_ids
                for i in edge.evidence_ids
            ):
                raise ValueError("missing_edge_evidence")
        return self


class Match(Closed):
    score: float
    node: Node
    evidence: list[Evidence] = Field(min_length=1, max_length=1)


class QueryResponse(Closed):
    query: QueryText
    authoritative_source: Literal["project_sources"] = "project_sources"
    matches: list[Match] = Field(max_length=20)


class Fact(Closed):
    key: FactKey
    value: str = Field(max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)


class AnswerResponse(Closed):
    supported: bool
    authoritative_source: Literal["project_sources"] = "project_sources"
    facts: list[Fact] = Field(max_length=1)
    evidence: list[Evidence] = Field(max_length=20)
    indexed_commits: dict[str, list[str]]
    reason: Literal["supported", "no_explicit_evidence", "conflicting_evidence"]
