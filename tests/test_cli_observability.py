import sys
from pathlib import Path

from most.cli_adapter import CLIAdapter, redact_command


def test_cli_command_observation_redacts_secret_arguments():
    assert redact_command(("agent", "--token", "secret", "--mode=edit")) == ("agent", "--token", "<redacted>", "--mode=edit")


def test_cli_cancellation_records_workspace_scan(tmp_path: Path):
    adapter = CLIAdapter()
    execution = adapter.start(sys.executable, ["-c", "import time; time.sleep(30)"], tmp_path)
    report = adapter.cancel(execution, grace_seconds=0.01, workspace_scanner=lambda: "after", expected_workspace_state="before")
    assert report.workspace_changed is True
