import unittest
from pathlib import Path

from healthdelta.worktree_policy import (
    WorktreeRef,
    is_legacy_issue_sibling,
    managed_root,
    parse_worktree_porcelain,
    select_prune_candidates,
)


class TestWorktreePolicy(unittest.TestCase):
    def test_managed_root_default_and_override(self) -> None:
        repo = Path("/home/user/Code/HealthDelta")
        self.assertEqual(managed_root(repo), Path("/home/user/Code/.worktrees/HealthDelta"))
        self.assertEqual(managed_root(repo, "/tmp/hd"), Path("/tmp/hd"))

    def test_parse_worktree_porcelain(self) -> None:
        text = "\n".join(
            [
                "worktree /repo",
                "HEAD abc",
                "branch refs/heads/main",
                "worktree /repo/.worktrees/issue-10",
                "HEAD def",
                "branch refs/heads/issue-10",
            ]
        )
        refs = parse_worktree_porcelain(text)
        self.assertEqual(len(refs), 2)
        self.assertEqual(refs[0].path, Path("/repo"))
        self.assertEqual(refs[0].branch, "main")
        self.assertEqual(refs[1].branch, "issue-10")

    def test_is_legacy_issue_sibling(self) -> None:
        repo = Path("/home/user/Code/HealthDelta")
        self.assertTrue(is_legacy_issue_sibling(Path("/home/user/Code/HealthDelta-issue99"), repo))
        self.assertFalse(is_legacy_issue_sibling(Path("/home/user/Code/.worktrees/HealthDelta/issue-99"), repo))

    def test_select_prune_candidates_closed_and_merged(self) -> None:
        repo = Path("/repo")
        root = Path("/repo/.worktrees")
        refs = [
            WorktreeRef(path=repo, branch="main"),
            WorktreeRef(path=Path("/repo/.worktrees/issue-10"), branch="issue-10"),
            WorktreeRef(path=Path("/repo/.worktrees/issue-11"), branch="issue-11"),
            WorktreeRef(path=Path("/repo/.worktrees/topic"), branch="topic"),
            WorktreeRef(path=Path("/repo/HealthDelta-issue12"), branch="issue-12"),
        ]
        got = select_prune_candidates(
            worktrees=refs,
            repo_root=repo,
            root=root,
            closed_issues={10, 11, 12},
            merged_branches={"issue-10", "issue-12"},
        )
        self.assertEqual([x.branch for x in got], ["issue-10"])


if __name__ == "__main__":
    unittest.main()
