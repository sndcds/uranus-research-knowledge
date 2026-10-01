"""Explicit public GitHub provisioning; query runtime does not import this module."""

import asyncio
import json

import httpx

from .extraction import MAX_FILE_BYTES, Snapshot
from .registry import REGISTRY


async def fetch(repository: str, sha: str) -> Snapshot:
    if (
        repository not in REGISTRY
        or len(sha) != 40
        or any(c not in "0123456789abcdef" for c in sha)
    ):
        raise ValueError("invalid_source")
    api = f"https://api.github.com/repos/{repository}"
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=20) as http:

        async def get(url, missing=False):
            async with (
                asyncio.timeout(25),
                http.stream("GET", url, headers={"Accept-Encoding": "identity"}) as response,
            ):
                if missing and response.status_code == 404:
                    return None
                response.raise_for_status()
                if (
                    response.status_code != 200
                    or response.headers.get("content-encoding", "identity") != "identity"
                ):
                    raise ValueError("invalid_source_response")
                body = bytearray()
                async for part in response.aiter_bytes():
                    body.extend(part)
                    if len(body) > MAX_FILE_BYTES:
                        raise ValueError("source_too_large")
                return body.decode("utf-8")

        metadata = json.loads(await get(api))
        if (
            metadata.get("private") is not False
            or metadata.get("visibility") != "public"
            or metadata.get("full_name") != repository
        ):
            raise ValueError("public_source_required")
        commit = json.loads(await get(f"{api}/commits/{sha}"))
        if commit.get("sha") != sha:
            raise ValueError("commit_mismatch")
        tree_sha = commit["commit"]["tree"]["sha"]
        tree = json.loads(await get(f"{api}/git/trees/{tree_sha}"))
        if tree.get("truncated"):
            raise ValueError("truncated_source_tree")
        # Walk Git trees, not raw URLs: reject symlinks/submodules before reading blobs.
        files = {}
        trees = {"": tree}
        for path in REGISTRY[repository].paths:
            parts = path.split("/")
            parent = ""
            entry = None
            for i, part in enumerate(parts):
                tree = trees[parent]
                entry = next((e for e in tree["tree"] if e["path"] == part), None)
                if entry is None:
                    break
                if i < len(parts) - 1:
                    if entry["type"] != "tree":
                        raise ValueError("unsafe_source_tree")
                    parent = "/".join(parts[: i + 1])
                    if parent not in trees:
                        trees[parent] = json.loads(await get(f"{api}/git/trees/{entry['sha']}"))
                        if trees[parent].get("truncated"):
                            raise ValueError("truncated_source_tree")
            if entry is None:
                files[path] = None
                continue
            if entry["type"] != "blob" or entry["mode"] not in {"100644", "100755"}:
                raise ValueError("unsafe_source_file")
            files[path] = await get(f"https://raw.githubusercontent.com/{repository}/{sha}/{path}")
        return Snapshot(
            repository=repository,
            commit_sha=sha,
            public_verified_from=api,
            complete=True,
            files=files,
        )
