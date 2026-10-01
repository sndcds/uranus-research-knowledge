"""Explicit offline indexing and separate network-enabled provisioning."""

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .clients import Clients
from .config import Settings
from .extraction import MAX_SNAPSHOT_BYTES, Snapshot, extract
from .indexer import plan, reconcile
from .models import COLLECTION
from .registry import safe_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    provision = commands.add_parser("provision")
    provision.add_argument("--repository", required=True)
    provision.add_argument("--sha", required=True)
    provision.add_argument("--output", required=True, type=Path)
    index = commands.add_parser("index")
    index.add_argument("action", choices=["plan", "reconcile"])
    index.add_argument("--snapshot", required=True, type=Path)
    index.add_argument("--report", required=True, type=Path)
    graph = commands.add_parser("graph")
    graph.add_argument("action", choices=["export"])
    graph.add_argument("--format", choices=["jsonld"], required=True)
    graph.add_argument("--snapshot", required=True, action="append", type=Path)
    graph.add_argument("--output", required=True, type=Path)
    commands.add_parser("collection-create")
    args = parser.parse_args()

    async def run():
        if args.command == "provision":
            from .provision import fetch

            snapshot = await fetch(args.repository, args.sha)
            args.output.write_text(snapshot.model_dump_json(indent=2) + "\n")
            return
        if args.command == "graph":
            from .graph import export_jsonld

            if len(args.snapshot) > 8:
                raise ValueError("too_many_snapshots")
            chunks = []
            repositories = set()
            for path in args.snapshot:
                with path.open("rb") as stream:
                    data = stream.read(MAX_SNAPSHOT_BYTES + 1)
                if len(data) > MAX_SNAPSHOT_BYTES:
                    raise ValueError("snapshot_too_large")
                snapshot = Snapshot.model_validate_json(data)
                if snapshot.repository in repositories:
                    raise ValueError("duplicate_repository_snapshot")
                repositories.add(snapshot.repository)
                chunks.extend(extract(snapshot, datetime(1970, 1, 1, tzinfo=UTC)))
            args.output.write_text(export_jsonld(chunks))
            return
        client = Clients(Settings())
        try:
            if args.command == "collection-create":
                await client.qdrant("PUT", body={"vectors": {"size": 1024, "distance": "Cosine"}})
                return
            with args.snapshot.open("rb") as stream:
                data = stream.read(MAX_SNAPSHOT_BYTES + 1)
            if len(data) > MAX_SNAPSHOT_BYTES:
                raise ValueError("snapshot_too_large")
            snapshot = Snapshot.model_validate_json(data)
            chunks = extract(snapshot, datetime.now(UTC))
            await client.check_collection()
            old = await client.existing(snapshot.repository)
            diff = plan(chunks, old, repository=snapshot.repository, complete=snapshot.complete)
            report = {
                "collection": COLLECTION,
                "repository": snapshot.repository,
                "commit_sha": snapshot.commit_sha,
                "corpus_hash": snapshot.corpus_hash,
                "complete": snapshot.complete,
                "excluded_paths": sorted(
                    p for p, t in snapshot.files.items() if t is not None and not safe_text(t)
                ),
                "changes": asdict(diff),
                "applied": False,
            }
            args.report.write_text(json.dumps(report, indent=2) + "\n")
            if args.action == "reconcile":
                await reconcile(client, chunks, diff, old)
                report["applied"] = True
                args.report.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps({k: len(v) for k, v in asdict(diff).items()}, sort_keys=True))
        finally:
            await client.close()

    try:
        asyncio.run(run())
    except Exception:
        parser.exit(1, "Operation failed; check source/configuration and upstream availability.\n")


if __name__ == "__main__":
    main()
