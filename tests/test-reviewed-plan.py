import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import textwrap
import unittest
from unittest.mock import patch
import zipfile


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/apply-reviewed-plan.yml"
SOURCE = textwrap.dedent(WORKFLOW.read_text().split("python3 - <<'PY'\n", 1)[1].split("\n          PY", 1)[0])


class ReviewedPlanTests(unittest.TestCase):
    def setUp(self):
        self.repo = "synthetic/repository"
        self.sha = "a" * 40
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as saved:
            saved.writestr("azure.tfplan", b"synthetic-plan-not-real-state")
        self.archive = archive.getvalue()
        self.responses = {
            "environments/dev": {
                "protection_rules": [{"type": "required_reviewers", "reviewers": [{"id": 1}]}],
                "deployment_branch_policy": {"custom_branch_policies": True, "protected_branches": False},
            },
            "environments/dev/deployment-branch-policies": {
                "total_count": 1, "branch_policies": [{"name": "main", "type": "branch"}],
            },
            "actions/runs/123": {
                "repository": {"full_name": self.repo}, "head_repository": {"full_name": self.repo},
                "event": "workflow_dispatch", "path": ".github/workflows/infra.yml",
                "head_branch": "main", "head_sha": self.sha, "run_attempt": 2,
                "status": "completed", "conclusion": "success",
            },
            "actions/runs/123/attempts/2/jobs": {
                "jobs": [{"name": "plan", "conclusion": "success",
                          "started_at": "2026-10-27T18:00:00Z", "completed_at": "2026-10-27T19:00:00Z"}],
            },
            "actions/artifacts/456": {
                "workflow_run": {"id": 123, "head_sha": self.sha},
                "name": "reviewed-infrastructure-plan", "expired": False,
                "created_at": "2026-10-27T18:30:00Z", "expires_at": "2999-01-01T00:00:00Z",
                "digest": "sha256:" + hashlib.sha256(self.archive).hexdigest(),
            },
        }

    def execute(self, changes=None, env_changes=None, archive=None):
        responses = copy.deepcopy(self.responses)
        if changes:
            changes(responses)
        environment = dict(
            GITHUB_REPOSITORY=self.repo, SOURCE_RUN_ID="123", SOURCE_ATTEMPT="2",
            SOURCE_SHA=self.sha, ARTIFACT_ID="456", EXTERNAL_ACCESS_VERIFIED="true",
            TARGET_RG="RG-MMAUG-Bootcamp",
        )
        environment.update(env_changes or {})

        def api(args):
            self.assertEqual(args[:2], ["gh", "api"])
            prefix = f"repos/{self.repo}/"
            self.assertTrue(args[2].startswith(prefix))
            path = args[2][len(prefix):]
            if path == "actions/artifacts/456/zip":
                return self.archive if archive is None else archive
            return json.dumps(responses[path]).encode()

        with tempfile.TemporaryDirectory() as temporary:
            environment["RUNNER_TEMP"] = temporary
            with patch.dict(os.environ, environment), patch("subprocess.check_output", side_effect=api):
                exec(compile(SOURCE, str(WORKFLOW), "exec"), {})
            return (Path(temporary) / "reviewed-plan/azure.tfplan").read_bytes()

    def test_valid_plan(self):
        self.assertEqual(self.execute(), b"synthetic-plan-not-real-state")

    def test_unverified_access(self):
        with self.assertRaises(SystemExit):
            self.execute(env_changes={"EXTERNAL_ACCESS_VERIFIED": "false"})

    def test_invalid_input(self):
        for field in ("SOURCE_RUN_ID", "SOURCE_ATTEMPT", "SOURCE_SHA", "ARTIFACT_ID"):
            with self.subTest(field=field), self.assertRaises(SystemExit):
                self.execute(env_changes={field: "invalid"})

    def test_untrusted_or_failed_source(self):
        for key, value in (("path", ".github/workflows/other.yml"), ("head_sha", "b" * 40),
                           ("run_attempt", 3), ("conclusion", "failure"), ("head_branch", "feature"),
                           ("event", "pull_request"), ("head_repository", {"full_name": "fork/repo"})):
            with self.subTest(key=key), self.assertRaises(SystemExit):
                self.execute(lambda r: r["actions/runs/123"].update({key: value}))

    def test_invalid_artifact(self):
        for key, value in (("expired", True), ("expires_at", "2000-01-01T00:00:00Z"),
                           ("created_at", "2026-10-27T17:00:00Z"), ("digest", ""),
                           ("name", "other-plan"), ("workflow_run", {"id": 999, "head_sha": self.sha})):
            with self.subTest(key=key), self.assertRaises(SystemExit):
                self.execute(lambda r: r["actions/artifacts/456"].update({key: value}))

    def test_corrupted_archive(self):
        with self.assertRaises(SystemExit):
            self.execute(archive=b"tampered")

    def test_missing_protections(self):
        for field, value in (("protection_rules", []), ("deployment_branch_policy", None)):
            with self.subTest(field=field), self.assertRaises(SystemExit):
                self.execute(lambda r: r["environments/dev"].update({field: value}))

    def test_unexpected_archive_member(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as saved:
            saved.writestr("../azure.tfplan", b"synthetic")
        payload = archive.getvalue()
        with self.assertRaises(SystemExit):
            self.execute(
                lambda r: r["actions/artifacts/456"].update(
                    digest="sha256:" + hashlib.sha256(payload).hexdigest()),
                archive=payload,
            )


if __name__ == "__main__":
    unittest.main()
