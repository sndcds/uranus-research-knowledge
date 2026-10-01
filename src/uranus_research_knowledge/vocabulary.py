"""Closed graph vocabulary v1; export does not require a graph database."""

from enum import StrEnum
from hashlib import sha256
from urllib.parse import quote

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


RELATIONS = {
    "organizes": {("organization", "event")},
    "has_occurrence": {("event", "occurrence")},
    "occurs_at": {("occurrence", "venue")},
    "uses_space": {("occurrence", "space")},
    "has_category": {("event", "category")},
    "has_genre": {("event", "genre")},
    "located_in": {("venue", "area")},
    "contains": {("project", "repository"), ("repository", "source_file")},
    "defines": {("source_file", "symbol")},
    "implements": {("repository", "feature")},
    "calls": {("component", "component")},
    "uses": {("service", "model")},
    "reads_from": {("service", "datastore")},
    "writes_to": {("service", "datastore")},
    "implemented_by": {("api_endpoint", "symbol")},
    "implemented_in": {("feature", "repository")},
    "documents": {("document", "component")},
}


def node_uri(kind: NodeType, identifier: str) -> str:
    return BASE + kind.value + "/" + quote(identifier, safe="/")


def edge_id(subject: str, relation: str, target: str) -> str:
    kinds = tuple(x.removeprefix(BASE).split("/", 1)[0] for x in (subject, target))
    if not all(x.startswith(BASE) for x in (subject, target)) or kinds not in RELATIONS.get(
        relation, set()
    ):
        raise ValueError("invalid_graph_edge")
    return BASE + "edge/" + sha256(f"{subject}\n{relation}\n{target}".encode()).hexdigest()
