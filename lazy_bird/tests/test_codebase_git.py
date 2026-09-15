from pathlib import Path

from lazy_bird.tools.codebase_git import (
    DocumentationMetadata,
    GitDocumentationInspector,
    GitInspectionError,
    documentation_metadata,
)


def inspector_for(responses: dict[tuple[str, ...], str]) -> GitDocumentationInspector:
    def runner(arguments):
        return responses[tuple(arguments)]

    return GitDocumentationInspector(Path("/repo"), runner=runner)


def test_repository_at_documented_head_is_current():
    inspector = inspector_for({("rev-parse", "HEAD"): "abc"})

    status = inspector.status(DocumentationMetadata("abc", "2026-09-14T10:00:00+00:00"))

    assert status.current_commit == "abc"
    assert status.is_current is True
    assert status.is_stale is False
    assert status.changed_commit_count == 0


def test_new_commit_is_stale_only_when_watched_paths_changed():
    inspector = inspector_for(
        {
            ("rev-parse", "HEAD"): "def",
            ("diff", "--name-only", "abc..def"): "src/lazy_bird/main.py\nlogs/app.log\n",
            ("rev-list", "--count", "abc..def"): "2",
        }
    )

    status = inspector.status(DocumentationMetadata("abc", "2026-09-14T10:00:00+00:00"))

    assert status.is_stale is True
    assert status.changed_commit_count == 2
    assert status.changed_paths == ("src/lazy_bird/main.py",)


def test_unwatched_change_does_not_mark_documentation_stale():
    inspector = inspector_for(
        {
            ("rev-parse", "HEAD"): "def",
            ("diff", "--name-only", "abc..def"): "logs/app.log\n",
            ("rev-list", "--count", "abc..def"): "1",
        }
    )

    status = inspector.status(DocumentationMetadata("abc", None))

    assert status.is_current is True
    assert status.is_stale is False
    assert status.changed_paths == ()


def test_changes_returns_commits_paths_and_diff():
    inspector = inspector_for(
        {
            ("diff", "--name-only", "abc..def"): "tests/test_main.py\n",
            ("log", "--format=%h %s", "abc..def", "--", "tests/test_main.py"): "def123 test route",
            ("diff", "--no-ext-diff", "abc..def", "--", "tests/test_main.py"): "+new test",
        }
    )

    changes = inspector.changes("abc", "def")

    assert changes == {
        "commits": ["def123 test route"],
        "diff": "+new test",
        "paths": ["tests/test_main.py"],
    }


def test_missing_documented_commit_does_not_run_diff():
    inspector = inspector_for({("rev-parse", "HEAD"): "abc"})

    status = inspector.status(DocumentationMetadata(None, None))

    assert status.current_commit == "abc"
    assert status.documented_commit is None
    assert status.is_stale is False


def test_git_failure_is_reported_in_status():
    def runner(_arguments):
        raise GitInspectionError("git unavailable")

    inspector = GitDocumentationInspector(Path("/missing"), runner=runner)

    status = inspector.status(DocumentationMetadata("abc", None))

    assert status.error == "git unavailable"
    assert status.current_commit is None


def test_metadata_file_without_commit_is_safe(tmp_path):
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text("{}", encoding="utf-8")

    metadata = documentation_metadata(metadata_path)

    assert metadata.documented_commit is None
    assert metadata.updated_at is None