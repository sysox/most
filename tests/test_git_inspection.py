from pathlib import Path

from most.git_service import GitService


def test_git_compatibility_inspection_is_conservative(tmp_path: Path):
    service = GitService(tmp_path)
    lfs = service.inspect_lfs()
    assert "available" in lfs
    paths = service.check_path_length_support(tmp_path)
    assert "supported" in paths
