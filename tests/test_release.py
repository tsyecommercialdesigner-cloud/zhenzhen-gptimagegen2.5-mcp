import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "release", Path(__file__).resolve().parents[1] / "scripts/release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseGateTests(unittest.TestCase):
    def test_only_exact_default_branch_completed_push_can_release(self):
        good = dict(
            headSha="target", headBranch="trunk", event="push", status="completed", conclusion="success"
        )
        self.assertEqual(release.successful_default_branch_runs([good], "target", "trunk"), [good])
        for field, value in (
            ("headSha", "old"),
            ("headBranch", "dev"),
            ("event", "pull_request"),
            ("status", "in_progress"),
            ("conclusion", "failure"),
            ("conclusion", "cancelled"),
        ):
            with self.subTest(field=field, value=value):
                self.assertEqual(
                    release.successful_default_branch_runs([good | {field: value}], "target", "trunk"),
                    [],
                )
        self.assertEqual(release.successful_default_branch_runs([{}], "target", "trunk"), [])


if __name__ == "__main__":
    unittest.main()
