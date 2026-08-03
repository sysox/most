import sys
from pathlib import Path

from most.cli_adapter import CLIAdapter


def test_cli_adapter_cancels_process_group(tmp_path: Path):
    adapter = CLIAdapter()
    execution = adapter.start(sys.executable, ["-c", "import time; time.sleep(30)"], tmp_path)
    report = adapter.cancel(execution, grace_seconds=0.01)
    assert report.requested
    assert execution.process.poll() is not None
