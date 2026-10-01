import json
from pathlib import Path

from uranus_research_knowledge.models import (
    AnswerRequest,
    AnswerResponse,
    Chunk,
    QueryRequest,
    QueryResponse,
)


def test_committed_schemas():
    for model in (QueryRequest, QueryResponse, AnswerRequest, AnswerResponse, Chunk):
        assert (
            json.loads(Path(f"contracts/{model.__name__}.json").read_text())
            == model.model_json_schema()
        )
