"""Fixed upstreams, bounded responses, no proxies, redirects, or credential forwarding."""

import asyncio
import json
import math

import httpx

from .config import Settings
from .models import COLLECTION, EMBEDDING_VERSION, OWNER, Chunk

MAX_EMBEDDING_BATCH_SIZE = 2


class UpstreamError(Exception):
    pass


class Clients:
    def __init__(self, settings: Settings, transport=None):
        self.settings = settings
        self.http = httpx.AsyncClient(
            timeout=settings.timeout_seconds,
            trust_env=False,
            follow_redirects=False,
            transport=transport,
        )

    async def close(self):
        await self.http.aclose()

    async def request(self, target, method, path, body=None):
        origin, key, header = (
            (self.settings.encoder_url, self.settings.encoder_api_key, "Authorization")
            if target == "encoder"
            else (self.settings.qdrant_url, self.settings.qdrant_api_key, "api-key")
        )
        value = key.get_secret_value()
        if target == "encoder":
            value = "Bearer " + value
        request = httpx.Request(
            method,
            origin + path,
            json=body,
            headers={
                header: value,
                "Accept-Encoding": "identity",
                "Accept": "application/json",
            },
        )
        try:
            async with asyncio.timeout(self.settings.timeout_seconds):
                response = await self.http.send(request, stream=True)
                try:
                    if (
                        response.status_code != 200
                        or response.headers.get("content-encoding", "identity") != "identity"
                        or response.headers.get("content-type", "").split(";")[0]
                        != "application/json"
                    ):
                        raise UpstreamError("invalid_upstream_response")
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > 4 * 1024 * 1024:
                            raise UpstreamError("upstream_response_too_large")
                    return json.loads(data)
                finally:
                    await response.aclose()
        except (httpx.HTTPError, TimeoutError, ValueError, RecursionError):
            raise UpstreamError("upstream_unavailable") from None

    async def embed(self, texts, kind):
        if not 1 <= len(texts) <= MAX_EMBEDDING_BATCH_SIZE:
            raise ValueError("invalid_embedding_batch")
        data = await self.request(
            "encoder",
            "POST",
            "/embed",
            {
                "model": "jina-v3",
                "kind": kind,
                "texts": texts,
            },
        )
        try:
            vectors = data["vectors"]
            if data["embedding_version"] != EMBEDDING_VERSION or len(vectors) != len(texts):
                raise ValueError
            for vector in vectors:
                if (
                    len(vector) != 1024
                    or any(
                        isinstance(x, bool)
                        or not isinstance(x, (int, float))
                        or not math.isfinite(x)
                        for x in vector
                    )
                    or abs(math.sqrt(math.fsum(x * x for x in vector)) - 1) > 1e-5
                ):
                    raise ValueError
            return vectors
        except (KeyError, TypeError, ValueError, OverflowError):
            raise UpstreamError("embedding_contract_mismatch") from None

    async def qdrant(self, method, suffix="", body=None):
        data = await self.request("qdrant", method, f"/collections/{COLLECTION}" + suffix, body)
        if not isinstance(data, dict) or data.get("status") != "ok" or "result" not in data:
            raise UpstreamError("invalid_qdrant_response")
        return data["result"]

    async def check_collection(self):
        result = await self.qdrant("GET")
        try:
            vectors = result["config"]["params"]["vectors"]
            if vectors["size"] != 1024 or vectors["distance"] != "Cosine":
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise UpstreamError("collection_contract_mismatch") from None

    async def search(self, query, limit):
        vector = (await self.embed([query], "query"))[0]
        result = await self.qdrant(
            "POST",
            "/points/query",
            {
                "query": vector,
                "limit": limit,
                "with_payload": True,
                "with_vector": False,
                "filter": {
                    "must": [
                        {"key": "index_owner", "match": {"value": OWNER}},
                        {"key": "embedding_version", "match": {"value": EMBEDDING_VERSION}},
                    ]
                },
            },
        )
        try:
            points = result["points"]
            if not isinstance(points, list) or len(points) > limit:
                raise ValueError
            found = []
            for p in points:
                chunk = Chunk.model_validate(p["payload"])
                score = float(p["score"])
                if str(p["id"]) != chunk.point_id or not math.isfinite(score):
                    raise ValueError
                found.append((score, chunk))
            return sorted(found, key=lambda x: (-x[0], x[1].point_id))
        except (ValueError, TypeError, KeyError):
            raise UpstreamError("invalid_evidence_payload") from None

    async def graph_chunks(self, nodes):
        from .graph import MAX_QUERY_CHUNKS
        from .vocabulary import node_type

        if not 1 <= len(nodes) <= 50:
            raise ValueError("invalid_graph_frontier")
        for node in nodes:
            node_type(node)
        chunks = {}
        offset = None
        seen = set()
        for _ in range(MAX_QUERY_CHUNKS // 100 + 1):
            page = await self.qdrant(
                "POST",
                "/points/scroll",
                {
                    "limit": 100,
                    "offset": offset,
                    "with_payload": True,
                    "with_vector": False,
                    "filter": {
                        "must": [
                            {"key": "index_owner", "match": {"value": OWNER}},
                            {"key": "embedding_version", "match": {"value": EMBEDDING_VERSION}},
                            {"key": "graph_node_ids", "match": {"any": nodes}},
                        ]
                    },
                },
            )
            try:
                points = page["points"]
                if not isinstance(points, list) or len(points) > 100:
                    raise ValueError
                for point in points:
                    chunk = Chunk.model_validate(point["payload"])
                    if (
                        str(point["id"]) != chunk.point_id
                        or chunk.point_id in chunks
                        or not set(nodes).intersection(chunk.graph_node_ids)
                    ):
                        raise ValueError
                    chunks[chunk.point_id] = chunk
                offset = page["next_page_offset"]
                if len(chunks) > MAX_QUERY_CHUNKS or offset in seen:
                    raise ValueError
                if offset is None:
                    return [chunks[k] for k in sorted(chunks)]
                seen.add(offset)
            except (KeyError, ValueError, TypeError):
                raise UpstreamError("invalid_graph_inventory") from None
        raise UpstreamError("graph_scan_limit")

    async def existing(self, repository):
        result = {}
        offset = None
        seen = set()
        for _ in range(101):
            page = await self.qdrant(
                "POST",
                "/points/scroll",
                {
                    "limit": 100,
                    "offset": offset,
                    "with_payload": True,
                    "with_vector": False,
                    "filter": {
                        "must": [
                            {"key": "index_owner", "match": {"value": OWNER}},
                            {"key": "repository", "match": {"value": repository}},
                        ]
                    },
                },
            )
            try:
                for p in page["points"]:
                    # Validate ownership and identity; old payload can contain removed annotations.
                    payload = p["payload"]
                    if payload["repository"] != repository or payload["index_owner"] != OWNER:
                        raise ValueError
                    result[str(p["id"])] = payload
                offset = page["next_page_offset"]
                if len(result) > 10000 or offset in seen:
                    raise ValueError
                if offset is None:
                    return result
                seen.add(offset)
            except (KeyError, ValueError, TypeError):
                raise UpstreamError("invalid_index_inventory") from None
        raise UpstreamError("index_inventory_too_large")

    async def vector(self, identity):
        result = await self.qdrant(
            "POST",
            "/points",
            {
                "ids": [identity],
                "with_payload": False,
                "with_vector": True,
            },
        )
        try:
            if len(result) != 1 or str(result[0]["id"]) != identity:
                raise ValueError
            vector = result[0]["vector"]
            if (
                len(vector) != 1024
                or any(
                    isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
                    for x in vector
                )
                or abs(math.sqrt(math.fsum(x * x for x in vector)) - 1) > 1e-5
            ):
                raise ValueError
            return vector
        except (KeyError, TypeError, ValueError, OverflowError):
            raise UpstreamError("invalid_reusable_vector") from None
