"""Single-writer reconciliation. Never delete before every write succeeds."""

from dataclasses import dataclass, field

from .models import Chunk


@dataclass
class Diff:
    new: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    metadata_updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)


def plan(chunks: list[Chunk], existing: dict, *, repository: str, complete: bool) -> Diff:
    diff = Diff()
    desired = {c.point_id: c for c in chunks}
    if len(desired) != len(chunks) or any(c.repository != repository for c in chunks):
        raise ValueError("invalid_snapshot_scope")
    for identity, chunk in sorted(desired.items()):
        old = existing.get(identity)
        payload = chunk.model_dump(mode="json")
        if old is None:
            diff.new.append(identity)
        elif old["repository"] != repository:
            raise ValueError("point_identity_collision")
        elif (old.get("content_hash"), old.get("embedding_version")) != (
            chunk.content_hash,
            chunk.embedding_version,
        ):
            diff.updated.append(identity)
        elif {k: v for k, v in old.items() if k != "indexed_at"} != {
            k: v for k, v in payload.items() if k != "indexed_at"
        }:
            diff.metadata_updated.append(identity)
        else:
            diff.unchanged.append(identity)
    if complete:
        diff.deleted = sorted(
            k for k, v in existing.items() if v["repository"] == repository and k not in desired
        )
    return diff


async def reconcile(client, chunks, diff, existing=None):
    desired = {c.point_id: c for c in chunks}
    pending = diff.new + diff.updated
    # Read reusable vectors before replacing any source point. A moved unit or
    # identical text in a new unit does not need another embedding.
    reusable = {}
    for identity, old in sorted((existing or {}).items()):
        reusable.setdefault(
            (old.get("content_hash"), old.get("embedding_version"), old.get("chunk_text")), identity
        )
    cached = {}
    for identity in pending:
        c = desired[identity]
        key = (c.content_hash, c.embedding_version, c.chunk_text)
        if key in reusable and key not in cached:
            cached[key] = await client.vector(reusable[key])
    for offset in range(0, len(pending), 64):
        ids = pending[offset : offset + 64]
        batch = [desired[k] for k in ids]
        missing = {}
        for c in batch:
            key = (c.content_hash, c.embedding_version, c.chunk_text)
            if key not in cached:
                missing[key] = c.chunk_text
        if missing:
            encoded = await client.embed(list(missing.values()), "passage")
            cached.update(zip(missing, encoded, strict=True))
        vectors = [cached[(c.content_hash, c.embedding_version, c.chunk_text)] for c in batch]
        await client.qdrant(
            "PUT",
            "/points?wait=true",
            {
                "points": [
                    {"id": k, "vector": vector, "payload": c.model_dump(mode="json")}
                    for k, c, vector in zip(ids, batch, vectors, strict=True)
                ]
            },
        )
    for identity in diff.metadata_updated:
        await client.qdrant(
            "PUT",
            "/points/payload?wait=true",
            {
                "points": [identity],
                "payload": desired[identity].model_dump(mode="json"),
            },
        )
    for offset in range(0, len(diff.deleted), 100):
        await client.qdrant(
            "POST", "/points/delete?wait=true", {"points": diff.deleted[offset : offset + 100]}
        )
