"""Closed vocabulary; canonical positive relations, never inferred inverse edges."""

import re
from enum import StrEnum
from hashlib import sha256
from urllib.parse import quote, unquote

BASE = "https://kulturbytes.de/kg/"
VERSION = "kulturbytes-kg-v1"


class NodeType(StrEnum):
    project = "project"
    repository = "repository"
    component = "component"
    service = "service"
    document = "document"
    source_file = "source_file"
    symbol = "symbol"
    api_endpoint = "api_endpoint"
    feature = "feature"
    model = "model"
    datastore = "datastore"
    deployment_component = "deployment_component"
    event = "event"
    occurrence = "occurrence"
    venue = "venue"
    space = "space"
    organization = "organization"
    category = "category"
    genre = "genre"
    area = "area"


class Relation(StrEnum):
    contains = "contains"
    defines = "defines"
    implements = "implements"
    calls = "calls"
    uses = "uses"
    uses_model = "uses_model"
    reads_from = "reads_from"
    writes_to = "writes_to"
    exposes = "exposes"
    documented_by = "documented_by"
    part_of = "part_of"
    organizes = "organizes"
    has_occurrence = "has_occurrence"
    occurs_at = "occurs_at"
    uses_space = "uses_space"
    has_category = "has_category"
    has_genre = "has_genre"
    located_in = "located_in"
    implemented_by = "implemented_by"


ACTORS = ("repository", "component", "service", "deployment_component")
RELATIONS = {
    Relation.organizes: {("organization", "event")},
    Relation.has_occurrence: {("event", "occurrence")},
    Relation.occurs_at: {("occurrence", "venue")},
    Relation.uses_space: {("occurrence", "space")},
    Relation.has_category: {("event", "category")},
    Relation.has_genre: {("event", "genre")},
    Relation.located_in: {("venue", "area")},
    Relation.contains: {("project", "repository"), ("repository", "source_file")},
    Relation.defines: {("source_file", "symbol")},
    Relation.implements: {(s, "feature") for s in ACTORS},
    Relation.calls: {(s, o) for s in ACTORS for o in ("component", "service", "api_endpoint")},
    Relation.uses: {(s, o) for s in ACTORS for o in ("datastore", "component", "service", "model")},
    Relation.uses_model: {(s, "model") for s in ACTORS},
    Relation.reads_from: {(s, "datastore") for s in ACTORS},
    Relation.writes_to: {(s, "datastore") for s in ACTORS},
    Relation.exposes: {(s, "api_endpoint") for s in ACTORS},
    Relation.documented_by: {(s.value, "document") for s in NodeType},
    Relation.part_of: {(s, "project") for s in ("component", "service", "deployment_component")},
    Relation.implemented_by: {("api_endpoint", "symbol")},
}


def node_uri(kind: NodeType, identifier: str) -> str:
    # Reviewed semantic IDs or public repo-relative paths only. Reject URI syntax,
    # traversal, local absolute paths, IPs and recognizable credentials.
    if (
        not identifier
        or len(identifier) > 1000
        or not re.fullmatch(r"[A-Za-z0-9_. /-]+", identifier)
        or any(p in ("", ".", "..") or p.startswith(".") for p in identifier.split("/"))
        or identifier.startswith(("home/", "tmp/", "etc/", "var/", "Users/"))
        or re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", identifier)
        or re.search(r"(?i)(credential|secret|api[_-]?key|gh[pousr]_|AKIA|password)", identifier)
    ):
        raise ValueError("invalid_node_identifier")
    return BASE + kind.value + "/" + quote(identifier, safe="/")


def node_type(uri: str) -> NodeType:
    if not uri.startswith(BASE):
        raise ValueError("invalid_node_uri")
    kind, separator, identifier = uri.removeprefix(BASE).partition("/")
    result = NodeType(kind)
    if not separator or node_uri(result, unquote(identifier)) != uri:
        raise ValueError("invalid_node_uri")
    return result


def edge_id(subject: str, relation: Relation | str, target: str) -> str:
    relation = Relation(relation)
    kinds = (node_type(subject), node_type(target))
    if kinds not in RELATIONS[relation]:
        raise ValueError("invalid_graph_edge")
    return BASE + "edge/" + sha256(f"{subject}\n{relation}\n{target}".encode()).hexdigest()
