from pathlib import Path

from most.task_journal import estimate_cost, record_task


def test_estimate_cost_uses_catalog_rates():
    assert estimate_cost(
        {"prompt_tokens": 1000, "completion_tokens": 500},
        {"per_1m_tokens": {"input": 2, "output": 10}},
    ) == 0.007


def test_one_shot_task_is_journaled(tmp_path: Path):
    session_id = record_task(
        tmp_path, provider="google", model="embedding-model", operation="embedding",
        input_summary="text file: sample.txt", output_summary="embedding with 3 dimensions",
        metadata={"dimensions": 3},
    )
    session_root = tmp_path / "sessions" / session_id
    assert (session_root / "session.yaml").exists()
    assert list((session_root / "structured").glob("request-*.json"))
    assert list((session_root / "results").glob("*.md"))
    assert list((session_root / "structured").glob("response-*.json"))
