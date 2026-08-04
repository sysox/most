from pathlib import Path

from most.workspace_context import WorkspaceContextSelector


def test_workspace_context_defaults_to_explicit_and_excludes_secrets(tmp_path: Path):
    (tmp_path / "source.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=value\n", encoding="utf-8")
    selection = WorkspaceContextSelector(tmp_path).select("EXPLICIT_SELECTION", ("source.py", ".env"))
    assert [item.path for item in selection.files] == ["source.py"]
    assert ".env" in selection.excluded_paths


def test_adapter_native_context_requires_approved_scope(tmp_path: Path):
    import pytest

    with pytest.raises(PermissionError):
        WorkspaceContextSelector(tmp_path).select("ADAPTER_NATIVE")


def test_workspace_context_records_hash_and_applies_limits(tmp_path: Path):
    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    (tmp_path / "b.py").write_text("bb", encoding="utf-8")
    selection = WorkspaceContextSelector(tmp_path).select("EXPLICIT_SELECTION", ("a.py", "b.py"), max_files=1)
    assert selection.files[0].sha256
    assert selection.files[0].size == 1
    assert selection.excluded_paths == ("b.py",)


def test_changed_files_uses_rename_destination(tmp_path: Path):
    from most.git_service import GitService

    git = GitService(tmp_path)
    git.run("init")
    git.run("config", "user.email", "most@example.invalid")
    git.run("config", "user.name", "MOST")
    (tmp_path / "old.py").write_text("print('ok')\n", encoding="utf-8")
    git.run("add", "old.py")
    git.run("commit", "-m", "initial")
    (tmp_path / "old.py").rename(tmp_path / "new.py")
    selection = WorkspaceContextSelector(tmp_path).select("CHANGED_FILES")
    assert [item.path for item in selection.files] == ["new.py"]
