"""Offline extraction from a bounded, provisioned committed source snapshot."""

import ast
import json
from datetime import datetime
from hashlib import sha256
from urllib.parse import quote

from pydantic import Field, model_validator

from .models import Chunk, Closed
from .registry import REGISTRY, safe_path, safe_text
from .vocabulary import NodeType, edge_id, node_uri

MAX_FILE_BYTES = 256 * 1024
MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024


class Snapshot(Closed):
    repository: str
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    public_verified_from: str
    complete: bool = False
    # Missing files are explicit nulls, not failed downloads disguised as absence.
    files: dict[str, str | None] = Field(max_length=200)

    @model_validator(mode="after")
    def reviewed(self):
        source = REGISTRY.get(self.repository)
        if (
            source is None
            or self.public_verified_from != f"https://api.github.com/repos/{self.repository}"
        ):
            raise ValueError("unverified_public_repository")
        if not set(self.files).issubset(source.paths) or not all(safe_path(p) for p in self.files):
            raise ValueError("unreviewed_path")
        if self.complete and set(self.files) != set(source.paths):
            raise ValueError("incomplete_snapshot")
        if any(len(t.encode()) > MAX_FILE_BYTES for t in self.files.values() if t is not None):
            raise ValueError("file_too_large")
        return self

    @property
    def corpus_hash(self) -> str:
        return sha256(json.dumps(self.model_dump(), sort_keys=True).encode()).hexdigest()


def units(path: str, text: str):
    lines = text.splitlines(keepends=True)
    if path.endswith(".py"):
        tree = ast.parse(text)
        yield "module", 1, len(lines), ""  # Module docstring only, never whole repository.

        def walk(body, prefix=""):
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = prefix + node.name
                    yield (
                        name,
                        node.lineno,
                        node.end_lineno,
                        "".join(lines[node.lineno - 1 : node.end_lineno]),
                    )
                    if isinstance(node, ast.ClassDef):
                        yield from walk(node.body, name + ".")

        yield from walk(tree.body)
        doc = ast.get_docstring(tree, clean=False)
        if doc:
            node = tree.body[0]
            yield (
                "module_doc",
                node.lineno,
                node.end_lineno,
                "".join(lines[node.lineno - 1 : node.end_lineno]),
            )
        return
    heading = path
    start = 1
    block = []
    serial = 0
    for n, line in enumerate(lines, 1):
        if line.startswith("#") and path.lower().endswith((".md", ".rst")):
            if block:
                yield f"{heading}:{serial}", start, n - 1, "".join(block)
                serial += 1
                block = []
            heading = line.strip("# \r\n")[:400]
        if not block:
            start = n
        block.append(line)
        if not line.strip():
            yield f"{heading}:{serial}", start, n, "".join(block)
            serial += 1
            block = []
    if block:
        yield f"{heading}:{serial}", start, len(lines), "".join(block)


def extract(snapshot: Snapshot, indexed_at: datetime) -> list[Chunk]:
    source = REGISTRY[snapshot.repository]
    result = []
    repo_node = node_uri(NodeType.repository, snapshot.repository)
    for path, content in sorted(snapshot.files.items()):
        if content is None or not safe_text(content):
            continue
        file_node = node_uri(NodeType.source_file, f"{snapshot.repository}/{path}")
        for name, start, _end, raw in units(path, content):
            # Small character windows keep encoder inputs bounded even for non-Latin text.
            # Exact substrings retain line provenance; no normalization invents a quote.
            for part, offset in enumerate(range(0, len(raw), 480)):
                value = raw[offset : offset + 480]
                if not value.strip():
                    continue
                line_start = start + raw[:offset].count("\n")
                line_end = line_start + value.removesuffix("\n").count("\n")
                nodes = [repo_node, file_node]
                edges = [edge_id(repo_node, "contains", file_node)]
                symbol = name if path.endswith(".py") else None
                if symbol:
                    symbol_node = node_uri(
                        NodeType.symbol, f"{snapshot.repository}/{path}/{symbol}"
                    )
                    nodes.append(symbol_node)
                    edges.append(edge_id(file_node, "defines", symbol_node))
                result.append(
                    Chunk(
                        repository=snapshot.repository,
                        commit_sha=snapshot.commit_sha,
                        path=path,
                        document_type="source_code"
                        if symbol
                        else "documentation"
                        if path.endswith((".md", ".rst", ".txt"))
                        else "configuration",
                        heading_or_symbol=name,
                        unit=f"{name}/{part}",
                        source_url=(
                            f"https://github.com/{snapshot.repository}/blob/"
                            f"{snapshot.commit_sha}/{quote(path, safe='/')}"
                        ),
                        content_hash=sha256(value.encode()).hexdigest(),
                        indexed_at=indexed_at,
                        chunk_text=value,
                        line_start=line_start,
                        line_end=line_end,
                        language="python" if symbol else None,
                        symbol=symbol,
                        license=source.license,
                        graph_node_ids=nodes,
                        graph_edge_ids=edges,
                        assertions=[a for a in source.assertions.get(path, ()) if a.quote in value],
                    )
                )
    if len(result) > 10000 or len({c.point_id for c in result}) != len(result):
        raise ValueError("invalid_corpus_size_or_identity")
    return result
