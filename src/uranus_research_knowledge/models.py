"""Bounded wire and payload contracts. Source text is evidence, never instructions."""

from datetime import datetime
from hashlib import sha256
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .vocabulary import NodeType, edge_id, node_uri

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
    "unknown",
]
QueryText = Annotated[str, StringConstraints(min_length=1, max_length=2000, strip_whitespace=True)]


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)


class Assertion(Closed):
    fact: FactKey
    value: str = Field(min_length=1, max_length=500)
    quote: str = Field(min_length=1, max_length=480)


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
    graph_node_ids: list[str] = Field(max_length=10)
    graph_edge_ids: list[str] = Field(default_factory=list, max_length=10)
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
        repo_node = node_uri(NodeType.repository, self.repository)
        file_node = node_uri(NodeType.source_file, f"{self.repository}/{self.path}")
        nodes = [repo_node, file_node]
        edges = [edge_id(repo_node, "contains", file_node)]
        if self.symbol:
            symbol_node = node_uri(NodeType.symbol, f"{self.repository}/{self.path}/{self.symbol}")
            nodes.append(symbol_node)
            edges.append(edge_id(file_node, "defines", symbol_node))
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
        return self


class QueryRequest(Closed):
    query: QueryText
    limit: int = Field(default=10, ge=1, le=20, strict=True)


class AnswerRequest(QueryRequest):
    fact: FactKey = "unknown"


class Node(Closed):
    id: str
    type: NodeType


class Match(Closed):
    score: float
    node: Node
    evidence: list[Chunk] = Field(min_length=1, max_length=1)


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
    evidence: list[Chunk] = Field(max_length=20)
    indexed_commits: dict[str, list[str]]
    reason: Literal["supported", "no_explicit_evidence", "conflicting_evidence"]
