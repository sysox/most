import subprocess
from pathlib import Path

from most.models import AIIteration
from most.workspace import WorkspaceService


def test_iteration_checkpoint_links_commit_after_creation(tmp_path: Path):
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True, stdin=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repository), "config", "user.name", "test"], check=True, stdin=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repository), "config", "user.email", "test@example.invalid"], check=True, stdin=subprocess.DEVNULL)
    (repository / "file.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "file.txt"], check=True, stdin=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repository), "-c", "commit.gpgSign=false", "commit", "-qm", "initial"], check=True, stdin=subprocess.DEVNULL)
    (repository / "file.txt").write_text("changed\n", encoding="utf-8")
    service = WorkspaceService(tmp_path / "data", repository)
    iteration = service.create_iteration_checkpoint(
        AIIteration(session_id="s", execution_id="e", sequence_number=1), ["file.txt"], "AI iteration 1",
    )
    assert iteration.status == "completed"
    assert iteration.resulting_commit == service.git.current_commit()
    events = (tmp_path / "data" / "sessions" / "s" / "events.jsonl").read_text(encoding="utf-8")
    assert iteration.resulting_commit in events
