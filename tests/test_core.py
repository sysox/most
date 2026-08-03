from pathlib import Path

import pytest

from most.context import assemble_context, resolve_lineage
from most.models import AIConfiguration, IntermediateResult, OverflowPolicy, record_payload
from most.persistence import PersistenceCoordinator
from most.policies import evaluate_exposure, resolve_overflow_policy


def test_record_payload_has_flattened_header():
    payload = record_payload(AIConfiguration(name="local"), record_type="AI_CONFIGURATION")
    assert payload["schema_version"] == 1
    assert payload["record_type"] == "AI_CONFIGURATION"
    assert payload["record_id"] == payload["id"]


def test_lineage_is_root_to_active_and_excludes_siblings():
    root = IntermediateResult(id="root", session_id="s", interaction_id="i")
    child = IntermediateResult(id="child", session_id="s", interaction_id="i", parent_result_id="root")
    sibling = IntermediateResult(id="sibling", session_id="s", interaction_id="i", parent_result_id="root")
    result = assemble_context("child", {r.id: r for r in (root, child, sibling)})
    assert result.lineage_result_ids == ("root", "child")
    assert result.excluded_result_ids == ("sibling",)


def test_lineage_rejects_cycles():
    a = IntermediateResult(id="a", session_id="s", interaction_id="i", parent_result_id="b")
    b = IntermediateResult(id="b", session_id="s", interaction_id="i", parent_result_id="a")
    with pytest.raises(ValueError):
        resolve_lineage("a", {"a": a, "b": b})


def test_policy_precedence_and_exposure_failure():
    assert resolve_overflow_policy(None, OverflowPolicy.TRIM_OLDEST) is OverflowPolicy.TRIM_OLDEST
    result = evaluate_exposure("local", "localhost", "remote-public", "public-internet")
    assert result.action.value == "FAIL"


def test_jsonl_recovery_ignores_incomplete_final_line(tmp_path: Path):
    store = PersistenceCoordinator(tmp_path)
    store.append_jsonl("events.jsonl", [{"record": 1}])
    (tmp_path / "events.jsonl").open("a", encoding="utf-8").write('{"incomplete"')
    assert store.read_jsonl("events.jsonl") == [{"record": 1}]


def test_atomic_yaml_write(tmp_path: Path):
    store = PersistenceCoordinator(tmp_path)
    target = store.write_yaml("config.yaml", {"ok": True})
    assert target.read_text(encoding="utf-8")
