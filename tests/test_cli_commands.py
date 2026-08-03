import json
from pathlib import Path

from most.cli import main


def test_cli_lists_created_sessions(tmp_path: Path, capsys):
    assert main(["--data-root", str(tmp_path), "create-session", "demo"]) == 0
    capsys.readouterr()
    assert main(["--data-root", str(tmp_path), "list-sessions"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output[0]["title"] == "demo"
