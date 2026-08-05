import sys
from pathlib import Path

import pytest

from most.cli_adapter import CLIAdapter
from most.journal import JournalService, validate_operation_id
from most.redaction import redact_text


def test_redaction_removes_exact_secrets_and_common_patterns():
    value = "token=top-secret Bearer abc123"
    result = redact_text(value, ("top-secret",))
    assert "top-secret" not in result
    assert "abc123" not in result


def test_cli_output_is_redacted_before_return(tmp_path: Path):
    adapter = CLIAdapter()
    execution = adapter.start(sys.executable, ["-c", "print('secret-value')"], tmp_path)
    stdout, _, _ = adapter.collect(execution, ("secret-value",))
    assert "secret-value" not in stdout


def test_journal_response_is_redacted(tmp_path: Path):
    JournalService(tmp_path).record_response("session", "response", {"text": "api_key=secret"})
    assert "secret" not in (tmp_path / "sessions/session/structured/response-response.json").read_text()


def test_journal_response_redacts_exact_secret_value(tmp_path: Path):
    JournalService(tmp_path).record_response("session", "response", {"text": "raw-token"}, ("raw-token",))
    assert "raw-token" not in (tmp_path / "sessions/session/structured/response-response.json").read_text()


def test_operation_id_rejects_header_control_characters():
    with pytest.raises(ValueError, match="control characters"):
        validate_operation_id("stage-0\r\nInjected: yes")
