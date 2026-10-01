import json
from pathlib import Path

from uranus_research_knowledge.schemas import CONTRACTS


def test_committed_schemas():
    for model in CONTRACTS:
        assert (
            json.loads(Path(f"contracts/{model.__name__}.json").read_text())
            == model.model_json_schema()
        )
