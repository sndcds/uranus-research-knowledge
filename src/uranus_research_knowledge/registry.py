"""Review this registry before provisioning; no request can extend it."""

import re
from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath

from .models import Assertion, GraphAssertion
from .vocabulary import NodeType, Relation


@dataclass(frozen=True)
class Source:
    paths: tuple[str, ...] = ("README.md",)
    license: str = "UNREVIEWED: no redistribution grant"
    assertions: dict[str, tuple[Assertion, ...]] = field(default_factory=dict)
    graph_assertions: dict[str, tuple[GraphAssertion, ...]] = field(default_factory=dict)
    evidence_redistribution_allowed: bool = False
    license_review_commit: str | None = None
    license_path: str | None = None
    license_content_hash: str | None = None

    def evidence_policy(self, repository: str, commit_sha: str):
        reviewed = self.license_review_commit == commit_sha and self.license_path is not None
        return (
            self.license if reviewed else "UNREVIEWED: no redistribution grant",
            bool(
                reviewed
                and self.evidence_redistribution_allowed
                and not self.license.startswith("UNREVIEWED")
            ),
            f"https://github.com/{repository}/blob/{commit_sha}/{self.license_path}"
            if reviewed
            else None,
        )


REGISTRY = {
    f"sndcds/{name}": Source()
    for name in (
        "uranus",
        "uranus-admin",
        "uranus-research-planner",
        "uranus-research-encoder",
        "pluto",
        "uranus-dashboard",
        "uranus-widget",
        "kulturbytes-client",
    )
}
# Exact excerpts reviewed against repository documentation. If wording changes,
# the assertion disappears until a reviewer updates this registry.
REGISTRY["sndcds/uranus-research-encoder"] = Source(
    assertions={
        "README.md": (
            Assertion(
                fact="embedding_component",
                value="sndcds/uranus-research-encoder",
                quote=(
                    "It turns generic Sections into deterministic contextual chunks and "
                    "produces\n"
                    "normalized 1024-dimensional Jina retrieval embeddings."
                ),
            ),
            Assertion(
                fact="embedding_model",
                value="jinaai/jina-embeddings-v3-hf",
                quote="| Repository | `jinaai/jina-embeddings-v3-hf` |",
            ),
        )
    }
)
REGISTRY["sndcds/uranus-research-planner"] = Source(
    assertions={
        "README.md": (
            Assertion(
                fact="planner_component",
                value="sndcds/uranus-research-planner",
                quote=(
                    "Internal language interpretation service for Kulturbytes. It translates "
                    "German,\n"
                    "Danish and English research questions into a closed, validated "
                    "`ResearchQueryPlan`."
                ),
            ),
        )
    }
)


def safe_path(path: str) -> bool:
    p = PurePosixPath(path)
    if p.is_absolute() or str(p) != path or ".." in p.parts or "\\" in path:
        return False
    forbidden = re.compile(r"(?i)(secret|credential|account|private|\.env|id_rsa|id_ed25519)")
    return not any(
        x.startswith(".") or forbidden.search(x) for x in p.parts
    ) and p.suffix.lower() not in {".pem", ".key", ".p12", ".lock"}


def safe_text(text: str) -> bool:
    # Supplemental rejection, not a substitute for exact reviewed paths.
    return re.search(
        r"-----BEGIN .*PRIVATE KEY|\b(?:gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b"
        r"|[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}"
        r"|(?i:(?:password|api[_-]?key|secret|token)\s*[:=]\s*['\"]?(?!\$|<|\{|None\b|null\b)[A-Za-z0-9_/-]{12,})",
        text,
    ) is None and not any(0xD800 <= ord(c) <= 0xDFFF for c in text)


REGISTRY["sndcds/uranus-admin"] = Source(
    paths=("README.md", "backend/README.md", "backend/app/services/semantic_search.py"),
    assertions={
        "backend/app/services/semantic_search.py": (
            Assertion(
                fact="semantic_search_repository",
                value="sndcds/uranus-admin",
                quote="await qdrant.search(vector, 50, entity_ids=eligible_ids)",
            ),
        ),
        "backend/README.md": (
            Assertion(
                fact="semantic_search_repository",
                value="sndcds/uranus-admin",
                quote=(
                    "Event semantic\n"
                    "search/recommendation first selects the complete hard-eligible UUID "
                    "population in\n"
                    "PostgreSQL/PostGIS, then ranks only those IDs in Qdrant (top 50), and "
                    "finally\n"
                    "rehydrates and validates contextual evidence in a fresh source snapshot."
                ),
            ),
            Assertion(
                fact="qdrant_usage",
                value="sndcds/uranus-admin",
                quote="PostgreSQL/PostGIS, then ranks only those IDs in Qdrant (top 50)",
            ),
        ),
    },
)


# Source review on 2026-10-01, pinned default-branch revisions. This grants no
# policy to earlier/later revisions. See docs/source-review.md for scope/ambiguity.
REGISTRY["sndcds/pluto"] = replace(
    REGISTRY["sndcds/pluto"],
    license="CC0-1.0",
    evidence_redistribution_allowed=True,
    license_review_commit="f89c20d0695cf60e8c9dd31a5fa48462fb7bcbe1",
    license_path="LICENSE",
    license_content_hash="a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499",
)
REGISTRY["sndcds/uranus-admin"] = replace(
    REGISTRY["sndcds/uranus-admin"],
    license="AGPL-3.0",
    evidence_redistribution_allowed=True,
    license_review_commit="2f0f6349a94d90e613dd1728371fedcec3ac4fb7",
    license_path="LICENSE",
    license_content_hash="8486a10c4393cee1c25392769ddd3b2d6c242d6ec7928e1414efff7dfb2f07ef",
)
REGISTRY["sndcds/uranus-dashboard"] = replace(
    REGISTRY["sndcds/uranus-dashboard"],
    license="CC0-1.0",
    evidence_redistribution_allowed=True,
    license_review_commit="87658dc2ff8d1492c6e0158afd57e59d428c6451",
    license_path="LICENSE",
    license_content_hash="a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499",
)
REGISTRY["sndcds/uranus-research-encoder"] = replace(
    REGISTRY["sndcds/uranus-research-encoder"],
    license="AGPL-3.0-only",
    evidence_redistribution_allowed=True,
    license_review_commit="48ce71550d5dad8c697facd3767aef8b4be97cc1",
    license_path="LICENSE",
    license_content_hash="8486a10c4393cee1c25392769ddd3b2d6c242d6ec7928e1414efff7dfb2f07ef",
)
REGISTRY["sndcds/uranus-research-planner"] = replace(
    REGISTRY["sndcds/uranus-research-planner"],
    license="AGPL-3.0",
    evidence_redistribution_allowed=True,
    license_review_commit="c10b1920c3a4af67a60b9d4ce5a807dbf11fe1f4",
    license_path="LICENSE",
    license_content_hash="8486a10c4393cee1c25392769ddd3b2d6c242d6ec7928e1414efff7dfb2f07ef",
)
REGISTRY["sndcds/uranus-widget"] = replace(
    REGISTRY["sndcds/uranus-widget"],
    license="CC0-1.0",
    evidence_redistribution_allowed=True,
    license_review_commit="c42f265cb549c31647800d6e6f1df39908c00f7f",
    license_path="LICENSE",
    license_content_hash="a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499",
)
REGISTRY["sndcds/uranus"] = replace(
    REGISTRY["sndcds/uranus"],
    license="CC0-1.0",
    evidence_redistribution_allowed=True,
    license_review_commit="ce426a0f9b2d4c79f81a0ccd291999406cddfa11",
    license_path="LICENSE",
    license_content_hash="a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499",
)


def graph(subject_type, subject_id, predicate, object_type, object_id, quote):
    return GraphAssertion(
        subject_type=subject_type,
        subject_id=subject_id,
        predicate=predicate,
        object_type=object_type,
        object_id=object_id,
        quote=quote,
    )


ADMIN_INTRO = (
    "**Kulturbytes Admin** ist das Open-Source-Administrations-, "
    "Datenqualitäts- und Operations-Dashboard\n"
    "für [Kulturbytes](https://kulturbytes.de/) und das Uranus-Backend."
)
PLANNER_INTRO = REGISTRY["sndcds/uranus-research-planner"].assertions["README.md"][0].quote
ENCODER_INTRO = (
    "A standalone, stateless internal HTTP service for the Kulturbytes / Uranus research\nstack."
)
SEMANTIC_CALL = "await qdrant.search(vector, 50, entity_ids=eligible_ids)"
REGISTRY["sndcds/uranus-admin"] = replace(
    REGISTRY["sndcds/uranus-admin"],
    graph_assertions={
        "README.md": (
            graph(
                NodeType.project,
                "kulturbytes",
                Relation.contains,
                NodeType.repository,
                "sndcds/uranus-admin",
                ADMIN_INTRO,
            ),
        ),
        "backend/app/services/semantic_search.py": (
            graph(
                NodeType.repository,
                "sndcds/uranus-admin",
                Relation.implements,
                NodeType.feature,
                "semantic-search",
                SEMANTIC_CALL,
            ),
            graph(
                NodeType.repository,
                "sndcds/uranus-admin",
                Relation.uses,
                NodeType.datastore,
                "qdrant",
                SEMANTIC_CALL,
            ),
        ),
    },
)
REGISTRY["sndcds/uranus-research-planner"] = replace(
    REGISTRY["sndcds/uranus-research-planner"],
    graph_assertions={
        "README.md": (
            graph(
                NodeType.project,
                "kulturbytes",
                Relation.contains,
                NodeType.repository,
                "sndcds/uranus-research-planner",
                PLANNER_INTRO,
            ),
            graph(
                NodeType.component,
                "research-planner",
                Relation.implements,
                NodeType.feature,
                "natural-language-research-planning",
                PLANNER_INTRO,
            ),
            graph(
                NodeType.component,
                "research-planner",
                Relation.part_of,
                NodeType.project,
                "kulturbytes",
                PLANNER_INTRO,
            ),
        )
    },
)
REGISTRY["sndcds/uranus-research-encoder"] = replace(
    REGISTRY["sndcds/uranus-research-encoder"],
    graph_assertions={
        "README.md": (
            graph(
                NodeType.project,
                "kulturbytes",
                Relation.contains,
                NodeType.repository,
                "sndcds/uranus-research-encoder",
                ENCODER_INTRO,
            ),
            graph(
                NodeType.component,
                "research-encoder",
                Relation.part_of,
                NodeType.project,
                "kulturbytes",
                ENCODER_INTRO,
            ),
            graph(
                NodeType.component,
                "research-encoder",
                Relation.uses_model,
                NodeType.model,
                "jinaai/jina-embeddings-v3-hf",
                "| Repository | `jinaai/jina-embeddings-v3-hf` |",
            ),
        )
    },
)
