"""Export bounded API and payload schemas without environment or network access."""

import json
from pathlib import Path

from .models import AnswerRequest, AnswerResponse, Chunk, QueryRequest, QueryResponse


def main():
    target = Path("contracts")
    target.mkdir(exist_ok=True)
    for model in (QueryRequest, QueryResponse, AnswerRequest, AnswerResponse, Chunk):
        (target / f"{model.__name__}.json").write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        )


if __name__ == "__main__":
    main()
