"""Review this registry before provisioning; no request can extend it."""

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .models import Assertion


@dataclass(frozen=True)
class Source:
    paths: tuple[str, ...] = ("README.md",)
    license: str = "UNREVIEWED: no redistribution grant"
    assertions: dict[str, tuple[Assertion, ...]] = field(default_factory=dict)


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
