"""FR-223: scripts/deploy_api.sh gates, against a real temporary git repo and stand-ins for fly, gh, curl and date."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy_api.sh"
IMAGE = "registry.fly.io/filmrunner-api:deployment-previous"


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


def _stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(f"#!/bin/bash\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


class World:
    def __init__(self, root: Path) -> None:
        self.repo = root / "repo"
        self.bin = root / "bin"
        self.log = root / "calls.log"
        self.bin.mkdir()
        origin = root / "origin.git"
        subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
        subprocess.run(["git", "clone", str(origin), str(self.repo)], check=True, capture_output=True)
        (self.repo / "scripts").mkdir()
        (self.repo / "backend").mkdir()
        shutil.copy(SCRIPT, self.repo / "scripts" / "deploy_api.sh")
        (self.repo / "backend" / "fly.toml").write_text("app = 'x'\n")
        _git(self.repo, "checkout", "-q", "-b", "main")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-qm", "init")
        _git(self.repo, "push", "-q", "origin", "main")
        self.sha = _git(self.repo, "rev-parse", "HEAD")
        self.set_ci("success")
        self.set_hour("12")
        self.set_served(self.sha)
        _stub(self.bin, "sleep", "exit 0")
        _stub(self.bin, "fly", f"""
echo "fly $* [cwd=$(basename "$PWD")]" >> "{self.log}"
if [ "$1" = releases ]; then echo '[{{"Status":"complete","ImageRef":"{IMAGE}"}}]'; exit 0; fi
exit ${{FAKE_FLY_EXIT:-0}}""")

    def set_ci(self, conclusions: str) -> None:
        _stub(self.bin, "gh", f'[ "$FAKE_GH_FAIL" = 1 ] && exit 1\nprintf "{conclusions}"\n')

    def set_hour(self, hour: str) -> None:
        _stub(self.bin, "date", f'echo "date TZ=$TZ" >> "{self.log}"\necho {hour}')

    def set_served(self, sha: str, readyz_sha: str | None = None) -> None:
        readyz_sha = sha if readyz_sha is None else readyz_sha
        _stub(self.bin, "curl", f"""
case "$*" in
  *readyz*) echo '{{"status":"ok","git_sha":"{readyz_sha}"}}' ;;
  *) echo '{{"status":"ok","git_sha":"{sha}"}}' ;;
esac""")

    def run(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", "scripts/deploy_api.sh", *args], cwd=self.repo, text=True, capture_output=True,
            env={**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", **env},
        )

    def calls(self) -> str:
        return self.log.read_text() if self.log.exists() else ""


@pytest.fixture()
def world(tmp_path) -> World:
    return World(tmp_path)


def test_dry_run_passes_the_gates_and_deploys_nothing(world):
    result = world.run("--dry-run")
    assert result.returncode == 0, result.stderr
    assert "fly deploy" not in world.calls()
    assert f"FILMRUNNER_GIT_SHA={world.sha}" in result.stdout
    assert f"fly deploy --image {IMAGE} --skip-release-command" in result.stdout


def test_refuses_outside_main(world):
    _git(world.repo, "checkout", "-q", "-b", "other")
    result = world.run("--dry-run")
    assert result.returncode == 1 and "not main" in result.stderr


@pytest.mark.parametrize("dirt", ["untracked.txt", "backend/fly.toml"])
def test_refuses_a_dirty_tree(world, dirt):
    (world.repo / dirt).write_text("changed\n")
    result = world.run("--dry-run")
    assert result.returncode == 1 and "not clean" in result.stderr


def test_refuses_a_head_that_is_not_origin_main(world):
    _git(world.repo, "commit", "-q", "--allow-empty", "-m", "local only")
    result = world.run("--dry-run")
    assert result.returncode == 1 and "is not origin/main" in result.stderr


@pytest.mark.parametrize("conclusions,message", [
    ("failure", "not green"),
    ("success\\nfailure", "not green"),
    ("success\\nunfinished", "not green"),
    ("", "has no result"),
])
def test_refuses_unless_ci_is_green(world, conclusions, message):
    world.set_ci(conclusions)
    result = world.run("--dry-run")
    assert result.returncode == 1 and message in result.stderr


def test_refuses_when_ci_cannot_be_read(world):
    result = world.run("--dry-run", FAKE_GH_FAIL="1")
    assert result.returncode == 1 and "could not read" in result.stderr


@pytest.mark.parametrize("hour,allowed", [("21", True), ("22", False), ("00", False), ("06", False), ("07", True), ("08", True), ("09", True)])
def test_the_window_is_prague_time(world, hour, allowed):
    world.set_hour(hour)
    result = world.run("--dry-run")
    assert (result.returncode == 0) is allowed, result.stderr
    assert "date TZ=Europe/Prague" in world.calls()


def test_force_window_overrides_only_the_window(world):
    world.set_hour("03")
    assert world.run("--dry-run", "--force-window").returncode == 0
    world.set_ci("failure")
    assert world.run("--dry-run", "--force-window").returncode == 1


def test_unknown_argument_does_not_deploy(world):
    assert world.run("--dryrun").returncode == 2
    assert "fly" not in world.calls()


def test_a_real_run_deploys_from_backend_with_the_sha_and_waits_for_both_endpoints(world):
    result = world.run()
    assert result.returncode == 0, result.stderr
    assert f"fly deploy --build-arg FILMRUNNER_GIT_SHA={world.sha} [cwd=backend]" in world.calls()
    assert "/healthz serves" in result.stdout and "/readyz serves" in result.stdout
    assert IMAGE in result.stdout


def test_a_commit_that_never_serves_exits_nonzero_with_the_rollback(world):
    world.set_served(world.sha, readyz_sha="0" * 40)
    result = world.run()
    assert result.returncode == 1
    assert "/readyz did not report" in result.stderr
    assert f"fly deploy --image {IMAGE} --skip-release-command" in result.stderr


def test_a_failed_fly_deploy_stops_and_shows_the_rollback(world):
    result = world.run(FAKE_FLY_EXIT="1")
    assert result.returncode == 1
    assert "/healthz serves" not in result.stdout
    assert IMAGE in result.stderr
